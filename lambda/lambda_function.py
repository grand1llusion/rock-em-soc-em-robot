"""Rock 'Em SOC 'Em Robot: an agentic SOC analyst copilot.

One AWS Lambda function (behind a Function URL) that:
  GET  /        -> serves the chat page
  GET  /alerts  -> lists the synthetic alert queue
  POST /chat    -> runs the agent loop (Amazon Bedrock Converse API + tools)

All alert data is AI-generated test data (see data.py).
"""
import json
import math
import os
import re
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import data

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")
CASES_TABLE = os.environ.get("CASES_TABLE", "rock-em-cases")
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")  # optional passcode; empty = open
MAX_STEPS = 8            # max model<->tool round trips per request
MAX_HISTORY = 12         # max chat messages accepted from the browser
MAX_MESSAGE_CHARS = 1500

bedrock = boto3.client("bedrock-runtime")
_table = None


def _cases_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(CASES_TABLE)
    return _table


SYSTEM_PROMPT = f"""You are Rock 'Em SOC 'Em Robot, a friendly boxing-announcer-style \
security analyst helping defenders at {data.COMPANY}. You work in the company's \
Security Operations Center (SOC) and help a small IT team triage security alerts so \
they can protect the business. This is a defensive, protective role.

HOW YOU WORK
- When asked about an alert, ALWAYS call get_alert first, then use the other tools \
to check facts (lookup_user, lookup_asset, check_ip, check_travel_feasibility). \
Never invent facts. If a tool returns nothing, say so.
- When you have decided, call save_verdict exactly once, then write your answer.
- If the user asks for the alert queue, call list_alerts.
- If the user asks about anything that is not security triage for this company, \
politely steer back to the alert queue in one sentence.

VERDICTS (use these exact words)
- KO: a real threat, escalate now.
- SPLIT_DECISION: suspicious or unclear, a human must check one specific thing.
- DODGE: benign or an expected activity, no action needed beyond closing the alert.

ANSWER FORMAT (plain text, short, no tables)
1. One short boxing-announcer line to open (e.g. "Ding ding! Round one!"). Keep the \
flavor to this line and, optionally, the closing line. Be serious and precise everywhere else.
2. VERDICT: <KO | SPLIT DECISION | DODGE>   SEVERITY: <low | medium | high | critical>
3. WHAT HAPPENED: 2 sentences in plain English, written for a non-security manager.
4. WHY I THINK SO: 2-4 bullets citing the specific facts your tools returned.
5. WHAT TO DO NEXT: up to 5 numbered steps; say WHO does each (IT admin, the user, \
the manager, the SOC).
6. BUSINESS IMPACT: one sentence on what is at stake if this is real.

Remember: all data in this demo is AI-generated test data."""

TOOLS = [
    {"name": "list_alerts",
     "description": "List every alert in the SOC queue with id, title, source and time.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "get_alert",
     "description": "Get the full details of one alert by id (for example ALR-1001).",
     "schema": {"type": "object", "properties": {"alert_id": {"type": "string"}},
                "required": ["alert_id"]}},
    {"name": "lookup_user",
     "description": "Look up an employee or service account: role, normal location and devices, "
                    "MFA type, privileges, and any relevant approved changes.",
     "schema": {"type": "object", "properties": {"username": {"type": "string"}},
                "required": ["username"]}},
    {"name": "lookup_asset",
     "description": "Look up an internal host, IP address or cloud resource in the asset inventory "
                    "to see who owns it and whether activity on it is expected.",
     "schema": {"type": "object", "properties": {"name_or_ip": {"type": "string"}},
                "required": ["name_or_ip"]}},
    {"name": "check_ip",
     "description": "Check the reputation of an external IP address with the threat intel feed.",
     "schema": {"type": "object", "properties": {"ip": {"type": "string"}}, "required": ["ip"]}},
    {"name": "check_travel_feasibility",
     "description": "Given two cities and the minutes between two sign-ins, compute whether a "
                    "person could physically have travelled between them.",
     "schema": {"type": "object",
                "properties": {"from_city": {"type": "string"}, "to_city": {"type": "string"},
                               "minutes_apart": {"type": "number"}},
                "required": ["from_city", "to_city", "minutes_apart"]}},
    {"name": "save_verdict",
     "description": "Record your final verdict for an alert in the case log. Call once per alert.",
     "schema": {"type": "object",
                "properties": {"alert_id": {"type": "string"},
                               "verdict": {"type": "string", "enum": ["KO", "SPLIT_DECISION", "DODGE"]},
                               "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                               "summary": {"type": "string", "description": "One-sentence plain-English summary."}},
                "required": ["alert_id", "verdict", "severity", "summary"]}},
]

TOOL_CONFIG = {"tools": [
    {"toolSpec": {"name": t["name"], "description": t["description"],
                  "inputSchema": {"json": t["schema"]}}} for t in TOOLS]}


# ---------------------------------------------------------------- tools
def _haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def tool_list_alerts(_):
    return {"alerts": [{k: a[k] for k in ("id", "title", "source", "time")} for a in data.ALERTS.values()]}


def tool_get_alert(args):
    alert = data.ALERTS.get(str(args.get("alert_id", "")).upper())
    return alert or {"error": "No such alert. Use list_alerts to see valid ids."}


def tool_lookup_user(args):
    user = data.USERS.get(str(args.get("username", "")).lower())
    return user or {"error": "User not found in the directory."}


def tool_lookup_asset(args):
    key = str(args.get("name_or_ip", ""))
    asset = data.ASSETS.get(key) or data.ASSETS.get(key.lower())
    return asset or {"error": "Not in the asset inventory (unknown or unmanaged asset)."}


def tool_check_ip(args):
    ip = str(args.get("ip", ""))
    return data.IP_REPUTATION.get(ip) or {"reputation": "unknown", "detail": "No reports in the threat intel feed."}


def tool_check_travel(args):
    a = data.CITIES.get(str(args.get("from_city", "")).lower())
    b = data.CITIES.get(str(args.get("to_city", "")).lower())
    if not a or not b:
        return {"error": "City not in my small city table. Known: " + ", ".join(sorted(data.CITIES))}
    try:
        minutes = float(args.get("minutes_apart"))
    except (TypeError, ValueError):
        return {"error": "minutes_apart must be a number."}
    km = _haversine_km(a, b)
    speed = km / max(minutes, 1) * 60
    return {"distance_km": round(km), "minutes_apart": minutes,
            "required_speed_kmh": round(speed),
            "physically_possible": speed < 900,
            "note": "Commercial jets cruise around 900 km/h, and door-to-door flights take hours. "
                    "A VPN or proxy can fake location, but then the 'travel' is not real either."}


def tool_save_verdict(args):
    item = {"alert_id": str(args.get("alert_id", "")).upper(),
            "verdict": args.get("verdict"), "severity": args.get("severity"),
            "summary": str(args.get("summary", ""))[:500],
            "saved_at": datetime.now(timezone.utc).isoformat()}
    try:
        _cases_table().put_item(Item=item)
        return {"saved": True, "alert_id": item["alert_id"]}
    except Exception as exc:  # table missing or no permission: keep the demo alive
        print("save_verdict failed:", repr(exc))
        return {"saved": False, "note": "Case log unavailable; verdict still shown to the analyst."}


TOOL_FUNCS = {
    "list_alerts": tool_list_alerts, "get_alert": tool_get_alert, "lookup_user": tool_lookup_user,
    "lookup_asset": tool_lookup_asset, "check_ip": tool_check_ip,
    "check_travel_feasibility": tool_check_travel, "save_verdict": tool_save_verdict,
}


# ---------------------------------------------------------------- agent
FRIENDLY = {
    "blocked": "The ref stopped that round: Bedrock's safety filter blocked my answer. "
               "Try rephrasing, or pick an alert from the queue and I'll take another swing.",
    "access": "I can't reach my brain (Bedrock) yet. The AWS account owner needs to check that the "
              "Lambda role can call Bedrock and that the model is enabled in this region.",
    "throttle": "Too many punches at once! Bedrock asked me to slow down. Give me a few seconds and try again.",
    "generic": "Ouch, I took a hit I didn't expect. The error is in the logs; please try again in a moment.",
    "steps": "I went in circles on this one and had to call time. Try asking again, or ask about a single alert.",
}


def _verdict_from_text(text):
    """Backup for when the model skips save_verdict: read 'VERDICT: KO  SEVERITY: high' from its answer."""
    m = re.search(r"VERDICT:\s*(KO|SPLIT[ _]DECISION|DODGE)", text, re.I)
    if not m:
        return None
    sev = re.search(r"SEVERITY:\s*(low|medium|high|critical)", text, re.I)
    return {"alert_id": None, "verdict": m.group(1).upper().replace(" ", "_"),
            "severity": sev.group(1).lower() if sev else None, "summary": None}


def run_agent(history):
    messages = [{"role": m["role"], "content": [{"text": m["text"]}]} for m in history]
    trace, verdict = [], None
    for _ in range(MAX_STEPS):
        try:
            resp = bedrock.converse(
                modelId=MODEL_ID, system=[{"text": SYSTEM_PROMPT}], messages=messages,
                toolConfig=TOOL_CONFIG, inferenceConfig={"maxTokens": 1200, "temperature": 0.2})
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            print("Bedrock error:", code, exc)
            key = "access" if code in ("AccessDeniedException", "ResourceNotFoundException",
                                       "ValidationException") else \
                  "throttle" if "Throttl" in code or code == "ServiceQuotaExceededException" else "generic"
            return {"reply": FRIENDLY[key], "trace": trace, "verdict": verdict, "error": True}
        msg = resp["output"]["message"]
        stop = resp.get("stopReason")
        if stop == "tool_use":
            messages.append(msg)
            results = []
            for block in msg["content"]:
                if "toolUse" not in block:
                    continue
                tu = block["toolUse"]
                func = TOOL_FUNCS.get(tu["name"])
                out = func(tu.get("input") or {}) if func else {"error": "Unknown tool"}
                trace.append({"tool": tu["name"], "input": tu.get("input") or {}, "output": out})
                if tu["name"] == "save_verdict":
                    verdict = {k: (tu.get("input") or {}).get(k) for k in ("alert_id", "verdict", "severity", "summary")}
                results.append({"toolResult": {"toolUseId": tu["toolUseId"],
                                               "content": [{"text": json.dumps(out)}]}})
            messages.append({"role": "user", "content": results})
            continue
        text = "".join(b.get("text", "") for b in msg.get("content", [])).strip()
        if stop in ("content_filtered", "guardrail_intervened"):
            return {"reply": (text + "\n\n" if text else "") + FRIENDLY["blocked"],
                    "trace": trace, "verdict": verdict, "error": True}
        verdict = verdict or _verdict_from_text(text)
        return {"reply": text or FRIENDLY["generic"], "trace": trace, "verdict": verdict}
    return {"reply": FRIENDLY["steps"], "trace": trace, "verdict": verdict, "error": True}


# ---------------------------------------------------------------- HTTP
def _resp(status, body, content_type="application/json"):
    return {"statusCode": status,
            "headers": {"Content-Type": content_type, "Cache-Control": "no-store"},
            "body": body if isinstance(body, str) else json.dumps(body)}


def _clean_history(raw):
    if not isinstance(raw, list) or not raw:
        return None
    msgs = []
    for m in raw[-MAX_HISTORY:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            return None
        text = str(m.get("text", ""))[:MAX_MESSAGE_CHARS].strip()
        if text:
            msgs.append({"role": m["role"], "text": text})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    if not msgs or msgs[-1]["role"] != "user":
        return None
    return msgs


def lambda_handler(event, context):
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", "GET"), event.get("rawPath", "/")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    if method == "GET" and path == "/":
        with open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8") as f:
            return _resp(200, f.read(), "text/html; charset=utf-8")

    if ACCESS_CODE and headers.get("x-access-code") != ACCESS_CODE:
        return _resp(401, {"error": "access_code"})

    if method == "GET" and path == "/alerts":
        return _resp(200, tool_list_alerts({}))

    if method == "POST" and path == "/chat":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _resp(400, {"reply": "I couldn't read that message. Try again?", "error": True})
        history = _clean_history(body.get("messages"))
        if not history:
            return _resp(400, {"reply": "Say something first and I'll step into the ring!", "error": True})
        started = time.time()
        result = run_agent(history)
        result["seconds"] = round(time.time() - started, 1)
        return _resp(200, result)

    return _resp(404, {"error": "not_found"})
