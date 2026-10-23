"""Reusable agent tool: read live Amazon GuardDuty findings, compact and redacted, for an LLM agent.

Drop it into any Bedrock Converse / Strands agent:
  TOOL                      name, description and JSON schema for the tool
  get_guardduty_findings()  the tool itself: list recent findings, or fetch one by id
  finding_summary()         turns a raw finding into the short, redacted facts a model needs

finding_summary() accepts a finding from the GuardDuty API (PascalCase keys) or the `detail` of an
Amazon EventBridge "GuardDuty Finding" event (camelCase keys), so the same code serves an agent that
asks for findings and one that is woken up by them.

Redaction: 12-digit AWS account IDs become <account> and access key IDs keep only their last four
characters, before anything reaches the model, the browser or the case log.

IAM: guardduty:ListDetectors, guardduty:ListFindings, guardduty:GetFindings.
"""
import json
import os
import re

import boto3
from botocore.exceptions import BotoCoreError, ClientError

PREFIX = "GD-"  # finding ids are shown to the model and the UI as GD-<finding id>

TOOL = {
    "name": "get_guardduty_findings",
    "description": "Read live security findings from Amazon GuardDuty in this AWS account. With no "
                   "finding_id, list the most recent active findings. With a finding_id (GD-...), get "
                   "that finding's facts: what happened, the affected resource, the remote IP and where "
                   "it is, how often it was seen, and GuardDuty's severity. Account IDs are redacted.",
    "schema": {"type": "object",
               "properties": {"finding_id": {"type": "string", "description": "A GD-... id, or omit to list."},
                              "max_results": {"type": "integer", "description": "How many to list (1-10)."}}},
}

_client = None
_detector = os.environ.get("GUARDDUTY_DETECTOR_ID") or None

ACCOUNT_ID = re.compile(r"(?<!\d)\d{12}(?!\d)")
ACCESS_KEY = re.compile(r"\b(AKIA|ASIA)[A-Z0-9]{12}([A-Z0-9]{4})\b")


def _gd():
    global _client
    if _client is None:
        _client = boto3.client("guardduty")
    return _client


def _detector_id():
    global _detector
    if _detector is None:
        ids = _gd().list_detectors().get("DetectorIds", [])
        _detector = ids[0] if ids else ""
    return _detector


def _lower(obj):
    """Lower-case every key, so API (PascalCase) and EventBridge (camelCase) findings read the same."""
    if isinstance(obj, dict):
        return {str(k).lower(): _lower(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_lower(v) for v in obj]
    return obj


def _find(obj, key):
    """First value stored under `key` anywhere inside obj (findings nest the remote IP differently per type)."""
    if isinstance(obj, dict):
        if obj.get(key):
            return obj[key]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            found = _find(v, key)
            if found:
                return found
    return None


def redact(obj):
    text = ACCOUNT_ID.sub("<account>", json.dumps(obj, default=str))
    return json.loads(ACCESS_KEY.sub(r"\1…\2", text))


def severity_label(score):
    return "critical" if score >= 9 else "high" if score >= 7 else "medium" if score >= 4 else "low"


def finding_summary(finding):
    f = _lower(finding)
    svc, res = f.get("service") or {}, f.get("resource") or {}
    action = svc.get("action") or {}
    score = float(f.get("severity") or 0)
    extra = json.dumps(svc.get("additionalinfo") or {}).lower().replace(" ", "").replace("\\", "")
    out = {"alert_id": PREFIX + str(f.get("id", "")).lower(), "source": "Amazon GuardDuty",
           "finding_type": f.get("type"), "title": f.get("title"), "description": f.get("description"),
           "severity": f"{severity_label(score)} ({score:g} of 10)", "region": f.get("region"),
           "first_seen": svc.get("eventfirstseen"), "last_seen": svc.get("eventlastseen"),
           "times_seen": svc.get("count"), "activity": action.get("actiontype"),
           "sample_finding": '"sample":true' in extra}

    resource = {"type": res.get("resourcetype")}
    inst = res.get("instancedetails") or {}
    if inst:
        nics = inst.get("networkinterfaces") or [{}]
        resource.update(instance_id=inst.get("instanceid"), instance_type=inst.get("instancetype"),
                        public_ip=nics[0].get("publicip"),
                        tags=[f"{t.get('key')}={t.get('value')}" for t in (inst.get("tags") or [])[:5]])
    key = res.get("accesskeydetails") or {}
    if key:
        resource.update(user=key.get("username"), user_type=key.get("usertype"), access_key=key.get("accesskeyid"))
    buckets = [b.get("name") for b in res.get("s3bucketdetails") or []]
    if buckets:
        resource["buckets"] = buckets
    out["resource"] = {k: v for k, v in resource.items() if v}

    remote = _find(action, "remoteipdetails")
    if remote:
        org = remote.get("organization") or {}
        out["remote_ip"] = {"ip": remote.get("ipaddressv4") or remote.get("ipaddressv6"),
                            "country": (remote.get("country") or {}).get("countryname"),
                            "city": (remote.get("city") or {}).get("cityname"),
                            "network_owner": org.get("asnorg") or org.get("isp")}
    network = action.get("networkconnectionaction") or {}
    if network:
        out["connection"] = {"direction": network.get("connectiondirection"), "protocol": network.get("protocol"),
                             "blocked": network.get("blocked")}
    port = _find(action, "localportdetails")
    if port:
        out["local_port"] = f"{port.get('port')} ({port.get('portname', 'unknown')})"
    api = action.get("awsapicallaction") or {}
    if api:
        out["api_call"] = {"api": api.get("api"), "service": api.get("servicename"), "error": api.get("errorcode")}
    dns = action.get("dnsrequestaction") or {}
    if dns.get("domain"):
        out["dns_domain"] = dns["domain"]
    intel = _find(svc.get("evidence") or {}, "threatintelligencedetails") or []
    names = sorted({n for t in intel for n in (t.get("threatnames") or [])} | {t.get("threatlistname") for t in intel} - {None})
    if names:
        out["threat_intel"] = names
    return redact({k: v for k, v in out.items() if v not in (None, "", [], {})})


def get_guardduty_findings(args):
    """The tool: list recent active findings, or return one finding's summary by id."""
    finding_id = str(args.get("finding_id") or "").strip()
    try:
        detector = _detector_id()
        if not detector:
            return {"error": "Amazon GuardDuty is not enabled in this AWS Region, so there are no findings."}
        if finding_id:
            raw = finding_id[len(PREFIX):] if finding_id.upper().startswith(PREFIX) else finding_id
            found = _gd().get_findings(DetectorId=detector, FindingIds=[raw.lower()]).get("Findings", [])
            return finding_summary(found[0]) if found else {"error": f"No GuardDuty finding {finding_id}."}
        try:
            limit = min(max(int(args.get("max_results") or 5), 1), 10)
        except (TypeError, ValueError):
            limit = 5
        ids = _gd().list_findings(DetectorId=detector,
                                  FindingCriteria={"Criterion": {"service.archived": {"Equals": ["false"]}}},
                                  SortCriteria={"AttributeName": "updatedAt", "OrderBy": "DESC"},
                                  MaxResults=limit).get("FindingIds", [])
        if not ids:
            return {"findings": [], "note": "No active GuardDuty findings right now."}
        found = _gd().get_findings(DetectorId=detector, FindingIds=ids).get("Findings", [])
        found.sort(key=lambda f: f.get("UpdatedAt", ""), reverse=True)
        brief = ("alert_id", "finding_type", "title", "severity", "last_seen", "sample_finding")
        return {"findings": [{k: s[k] for k in brief if k in s} for s in map(finding_summary, found)]}
    except ClientError as exc:
        return {"error": f"Amazon GuardDuty request failed ({exc.response['Error']['Code']})."}
    except BotoCoreError as exc:
        return {"error": f"Amazon GuardDuty request failed ({exc.__class__.__name__})."}
