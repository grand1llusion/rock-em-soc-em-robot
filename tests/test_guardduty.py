"""Offline tests for the GuardDuty tool and the live-bout path: fake GuardDuty, Bedrock and DynamoDB."""
import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import guardduty_tool as gd  # noqa: E402
import lambda_function as lf  # noqa: E402
from test_agent import FakeBedrock, text, tool_use  # noqa: E402

FID = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
ACCOUNT = "123456789012"

# Shaped like a GuardDuty sample finding as the GetFindings API returns it (PascalCase).
API_FINDING = {
    "AccountId": ACCOUNT, "Arn": f"arn:aws:guardduty:us-east-1:{ACCOUNT}:detector/d1/finding/{FID}",
    "Id": FID, "Region": "us-east-1", "Severity": 8, "Type": "UnauthorizedAccess:EC2/SSHBruteForce",
    "Title": "198.51.100.7 is performing SSH brute force attacks against i-0abc12345.",
    "Description": "198.51.100.7 is performing SSH brute force attacks against i-0abc12345.",
    "UpdatedAt": "2026-10-24T15:02:00.000Z",
    "Resource": {"ResourceType": "Instance", "InstanceDetails": {
        "InstanceId": "i-0abc12345", "InstanceType": "t3.micro",
        "IamInstanceProfile": {"Arn": f"arn:aws:iam::{ACCOUNT}:instance-profile/web"},
        "NetworkInterfaces": [{"PublicIp": "203.0.113.10"}],
        "Tags": [{"Key": "Name", "Value": "web-01"}]},
        "AccessKeyDetails": {"AccessKeyId": "AKIAABCDEFGHIJKL1234", "UserName": "deploy-bot", "UserType": "IAMUser"}},
    "Service": {"Count": 41, "EventFirstSeen": "2026-10-24T14:40:00.000Z", "EventLastSeen": "2026-10-24T15:01:00.000Z",
                "AdditionalInfo": {"Value": "{\"sample\":true}", "Type": "default"},
                "Action": {"ActionType": "NETWORK_CONNECTION", "NetworkConnectionAction": {
                    "ConnectionDirection": "INBOUND", "Protocol": "TCP", "Blocked": False,
                    "LocalPortDetails": {"Port": 22, "PortName": "SSH"},
                    "RemoteIpDetails": {"IpAddressV4": "198.51.100.7", "Country": {"CountryName": "Exampleland"},
                                        "City": {"CityName": "Sample City"},
                                        "Organization": {"AsnOrg": "Example Hosting Ltd"}}}},
                "Evidence": {"ThreatIntelligenceDetails": [{"ThreatListName": "ProofPoint", "ThreatNames": ["ssh-scanner"]}]}},
}


def camel(obj):
    """The same finding as an EventBridge event's `detail` (camelCase keys)."""
    if isinstance(obj, dict):
        return {k[:1].lower() + k[1:]: camel(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [camel(v) for v in obj]
    return obj


EVENT = {"source": "aws.guardduty", "detail-type": "GuardDuty Finding", "detail": camel(API_FINDING)}


class FakeGuardDuty:
    def __init__(self, findings=(API_FINDING,), detectors=("d1",), error=None):
        self.findings, self.detectors, self.error, self.calls = list(findings), list(detectors), error, []

    def list_detectors(self):
        return {"DetectorIds": self.detectors}

    def list_findings(self, **kw):
        self.calls.append(("list", kw))
        if self.error:
            raise self.error
        return {"FindingIds": [f["Id"] for f in self.findings][:kw["MaxResults"]]}

    def get_findings(self, DetectorId, FindingIds):
        self.calls.append(("get", FindingIds))
        if self.error:
            raise self.error
        return {"Findings": [copy.deepcopy(f) for f in self.findings if f["Id"] in FindingIds]}


class FakeTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key):
        item = self.items.get(Key["alert_id"])
        return {"Item": item} if item else {}

    def put_item(self, Item):
        self.items[Item["alert_id"]] = dict(Item)

    def scan(self, FilterExpression):
        return {"Items": [dict(i) for i in self.items.values() if i.get("live")]}


def use(fake_gd):
    """Point the tool at a fake GuardDuty client with a fresh detector lookup."""
    return mock.patch.multiple(gd, _client=fake_gd, _detector=None)


class SummaryTests(unittest.TestCase):
    def test_summary_has_the_facts(self):
        s = gd.finding_summary(API_FINDING)
        self.assertEqual(s["alert_id"], "GD-" + FID)
        self.assertEqual(s["severity"], "high (8 of 10)")
        self.assertTrue(s["sample_finding"])
        self.assertEqual(s["remote_ip"], {"ip": "198.51.100.7", "country": "Exampleland", "city": "Sample City",
                                          "network_owner": "Example Hosting Ltd"})
        self.assertEqual(s["local_port"], "22 (SSH)")
        self.assertEqual(s["times_seen"], 41)
        self.assertEqual(s["resource"]["tags"], ["Name=web-01"])
        self.assertEqual(s["threat_intel"], ["ProofPoint", "ssh-scanner"])

    def test_account_id_and_access_key_are_redacted(self):
        s = json.dumps(gd.finding_summary(API_FINDING), ensure_ascii=False)
        self.assertNotIn(ACCOUNT, s)
        self.assertNotIn("AKIAABCDEFGHIJKL1234", s)
        self.assertIn("AKIA…1234", s)

    def test_eventbridge_and_api_shapes_give_the_same_summary(self):
        self.assertEqual(gd.finding_summary(EVENT["detail"]), gd.finding_summary(API_FINDING))

    def test_real_finding_is_not_marked_sample(self):
        real = copy.deepcopy(API_FINDING)
        del real["Service"]["AdditionalInfo"]
        self.assertFalse(gd.finding_summary(real)["sample_finding"])

    def test_severity_labels(self):
        self.assertEqual([gd.severity_label(x) for x in (2, 5, 7.5, 9)], ["low", "medium", "high", "critical"])


class ToolTests(unittest.TestCase):
    def test_list_recent_findings(self):
        fake = FakeGuardDuty()
        with use(fake):
            out = gd.get_guardduty_findings({"max_results": 50})
        self.assertEqual(out["findings"][0]["alert_id"], "GD-" + FID)
        self.assertEqual(fake.calls[0][1]["MaxResults"], 10)  # capped
        self.assertEqual(fake.calls[0][1]["FindingCriteria"]["Criterion"]["service.archived"], {"Equals": ["false"]})

    def test_get_one_finding_by_id_any_case(self):
        fake = FakeGuardDuty()
        with use(fake):
            out = gd.get_guardduty_findings({"finding_id": "gd-" + FID.upper()})
        self.assertEqual(out["finding_type"], "UnauthorizedAccess:EC2/SSHBruteForce")
        self.assertEqual(fake.calls, [("get", [FID])])

    def test_errors_are_reported_not_guessed(self):
        with use(FakeGuardDuty(detectors=())):
            self.assertIn("not enabled", gd.get_guardduty_findings({})["error"])
        boom = lf.ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "ListFindings")
        with use(FakeGuardDuty(error=boom)):
            self.assertIn("AccessDeniedException", gd.get_guardduty_findings({})["error"])
        with use(FakeGuardDuty(findings=())):
            self.assertIn("error", gd.get_guardduty_findings({"finding_id": "GD-0000"}))
            self.assertEqual(gd.get_guardduty_findings({})["findings"], [])

    def test_get_alert_redirects_guardduty_ids(self):
        with use(FakeGuardDuty()):
            self.assertEqual(lf.tool_get_alert({"alert_id": "GD-" + FID})["source"], "Amazon GuardDuty")


class AgentTests(unittest.TestCase):
    def test_triage_request_prefetches_the_finding(self):
        bedrock = FakeBedrock([tool_use("save_verdict", {"alert_id": "GD-" + FID.upper(), "verdict": "KO",
                                                         "severity": "high", "summary": "SSH brute force."}),
                               text("VERDICT: KO  SEVERITY: high\nWHY I THINK SO: 41 attempts.")])
        table = FakeTable()
        with use(FakeGuardDuty()), mock.patch.object(lf, "bedrock", bedrock), \
                mock.patch.object(lf, "_cases_table", lambda: table):
            out = lf.run_agent([{"role": "user", "text": f"Triage GuardDuty finding GD-{FID}"}])
        first = bedrock.calls[0]["messages"]
        self.assertEqual(first[1]["content"][0]["toolUse"]["name"], "get_guardduty_findings")
        self.assertIn("Exampleland", first[2]["content"][0]["toolResult"]["content"][0]["text"])
        self.assertEqual(out["verdict"]["verdict"], "KO")
        self.assertIn("GD-" + FID, table.items)  # saved under the lower-case id
        self.assertIn("get_guardduty_findings", [t["name"] for t in [c["toolSpec"] for c in lf.TOOL_CONFIG["tools"]]])


class LiveBoutTests(unittest.TestCase):
    def run_event(self, table, bedrock):
        with use(FakeGuardDuty()), mock.patch.object(lf, "bedrock", bedrock), \
                mock.patch.object(lf, "_cases_table", lambda: table):
            return lf.lambda_handler(copy.deepcopy(EVENT), None)

    def test_new_finding_is_triaged_and_saved_once(self):
        table = FakeTable()
        out = self.run_event(table, FakeBedrock([text("VERDICT: KO  SEVERITY: high\nWHY I THINK SO: brute force.")]))
        self.assertEqual(out["verdict"], "KO")
        item = table.items["GD-" + FID]
        self.assertTrue(item["live"] and item["sample"])
        self.assertEqual(item["gd_severity"], "high (8 of 10)")
        self.assertNotIn(ACCOUNT, json.dumps(item))
        again = self.run_event(table, FakeBedrock([]))  # GuardDuty re-sends updates: no second triage
        self.assertEqual(again["skipped"], "already triaged")

    def test_bouts_route_lists_live_findings_only(self):
        table = FakeTable()
        table.put_item({"alert_id": "ALR-1001", "verdict": "KO"})  # a chat verdict, not a live bout
        self.run_event(table, FakeBedrock([text("VERDICT: DODGE  SEVERITY: low\nWHY I THINK SO: sample.")]))
        event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/bouts"}
        with mock.patch.object(lf, "_cases_table", lambda: table):
            body = json.loads(lf.lambda_handler(event, None)["body"])
        self.assertEqual([b["alert_id"] for b in body["bouts"]], ["GD-" + FID])
        self.assertEqual(body["bouts"][0]["trace"][0]["tool"], "get_guardduty_findings")

    def test_event_without_id_is_ignored(self):
        self.assertIn("skipped", lf.lambda_handler({"source": "aws.guardduty", "detail": {}}, None))


if __name__ == "__main__":
    unittest.main()
