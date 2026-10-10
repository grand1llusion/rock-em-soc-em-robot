"""Offline tests: a fake Bedrock client scripts the model so no AWS account is needed.

Run:  python -m unittest discover -s tests -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import lambda_function as lf  # noqa: E402


def tool_use(name, args, tid="t1"):
    return {"stopReason": "tool_use", "output": {"message": {"role": "assistant", "content": [
        {"toolUse": {"toolUseId": tid, "name": name, "input": args}}]}}}


def text(msg, stop="end_turn"):
    return {"stopReason": stop, "output": {"message": {"role": "assistant", "content": [{"text": msg}]}}}


class FakeBedrock:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def converse(self, **kw):
        self.calls.append(kw)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def post(history):
    event = {"requestContext": {"http": {"method": "POST"}}, "rawPath": "/chat",
             "body": json.dumps({"messages": history})}
    return lf.lambda_handler(event, None)


class ToolTests(unittest.TestCase):
    def test_impossible_travel(self):
        out = lf.tool_check_travel({"from_city": "Chicago", "to_city": "Lagos", "minutes_apart": 18})
        self.assertFalse(out["physically_possible"])
        self.assertGreater(out["distance_km"], 9000)

    def test_possible_travel(self):
        out = lf.tool_check_travel({"from_city": "Chicago", "to_city": "New York", "minutes_apart": 600})
        self.assertTrue(out["physically_possible"])

    def test_unknown_city_and_alert(self):
        self.assertIn("error", lf.tool_check_travel({"from_city": "Atlantis", "to_city": "Lagos", "minutes_apart": 5}))
        self.assertIn("error", lf.tool_get_alert({"alert_id": "NOPE"}))

    def test_every_alert_entity_resolves(self):
        for a in lf.data.ALERTS.values():
            user = a["entities"].get("user")
            if user:
                self.assertIn(user, lf.data.USERS)

    def test_save_verdict_survives_missing_table(self):
        with mock.patch.object(lf, "_cases_table", side_effect=RuntimeError("no table")):
            out = lf.tool_save_verdict({"alert_id": "alr-1001", "verdict": "KO", "severity": "high", "summary": "x"})
        self.assertFalse(out["saved"])


class AgentTests(unittest.TestCase):
    def test_tool_loop_returns_verdict_and_trace(self):
        fake = FakeBedrock([
            tool_use("get_alert", {"alert_id": "ALR-1001"}, "a"),
            tool_use("save_verdict", {"alert_id": "ALR-1001", "verdict": "KO", "severity": "high",
                                      "summary": "Impossible travel"}, "b"),
            text("Ding ding! VERDICT: KO"),
        ])
        with mock.patch.object(lf, "bedrock", fake), \
             mock.patch.object(lf, "_cases_table", side_effect=RuntimeError("offline")):
            res = post([{"role": "user", "text": "Triage alert ALR-1001"}])
        body = json.loads(res["body"])
        self.assertEqual(res["statusCode"], 200)
        self.assertEqual(body["verdict"]["verdict"], "KO")
        self.assertEqual([t["tool"] for t in body["trace"]], ["get_alert", "save_verdict"])
        self.assertIn("KO", body["reply"])
        # the tool result was fed back to the model as a toolResult block
        last_user = fake.calls[1]["messages"][-1]
        self.assertIn("toolResult", last_user["content"][0])

    def test_content_filter_gives_friendly_message(self):
        fake = FakeBedrock([text("partial answer", stop="content_filtered")])
        with mock.patch.object(lf, "bedrock", fake):
            body = json.loads(post([{"role": "user", "text": "hi"}])["body"])
        self.assertTrue(body["error"])
        self.assertIn("ref stopped", body["reply"])

    def test_access_denied_gives_friendly_message(self):
        err = lf.ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "Converse")
        with mock.patch.object(lf, "bedrock", FakeBedrock([err])):
            body = json.loads(post([{"role": "user", "text": "hi"}])["body"])
        self.assertIn("Bedrock", body["reply"])

    def test_runaway_tool_loop_is_capped(self):
        fake = FakeBedrock([tool_use("list_alerts", {}, str(i)) for i in range(lf.MAX_STEPS)])
        with mock.patch.object(lf, "bedrock", fake):
            body = json.loads(post([{"role": "user", "text": "hi"}])["body"])
        self.assertIn("call time", body["reply"])


class HttpTests(unittest.TestCase):
    def get(self, path):
        return lf.lambda_handler({"requestContext": {"http": {"method": "GET"}}, "rawPath": path}, None)

    def test_page_and_alerts(self):
        page = self.get("/")
        self.assertEqual(page["statusCode"], 200)
        self.assertIn("Rock 'Em SOC 'Em Robot", page["body"])
        self.assertEqual(len(json.loads(self.get("/alerts")["body"])["alerts"]), 6)
        self.assertEqual(self.get("/nope")["statusCode"], 404)

    def test_bad_requests(self):
        self.assertEqual(post([])["statusCode"], 400)
        self.assertEqual(post([{"role": "assistant", "text": "hi"}])["statusCode"], 400)

    def test_access_code(self):
        with mock.patch.object(lf, "ACCESS_CODE", "secret"):
            self.assertEqual(self.get("/alerts")["statusCode"], 401)
            self.assertEqual(self.get("/")["statusCode"], 200)  # page itself stays public


if __name__ == "__main__":
    unittest.main()
