# Live bouts: wiring Amazon GuardDuty to the robot

The robot's new tool, `get_guardduty_findings` ([`lambda/guardduty_tool.py`](../lambda/guardduty_tool.py)),
reads real findings from Amazon GuardDuty. An Amazon EventBridge rule wakes the robot for every new
finding, so it triages it on its own and the verdict appears under **Live bouts** on the page.

```
GuardDuty finding ──► EventBridge rule ──► Lambda (rock-em-soc-em-robot)
                                              ├─ get_guardduty_findings  (redacted facts)
                                              ├─ Amazon Bedrock (Nova Lite) decides KO / SPLIT / DODGE
                                              └─ DynamoDB case log ──► GET /bouts ──► "Live bouts" panel
```

## Set up (AWS console, us-east-1)

1. **Turn on GuardDuty**: GuardDuty > Get started > **Enable GuardDuty**. New accounts get a 30-day
   free trial. After it, a quiet personal account costs very little, but you can **suspend** GuardDuty
   (Settings > Suspend GuardDuty) when you are done.
2. **Permissions**: IAM > Roles > `rock-em-soc-em-robot-role` > Add permissions > Create inline
   policy > JSON. Paste [`iam-guardduty-policy.json`](iam-guardduty-policy.json), name it
   `guardduty-read-and-case-log`. It can read findings, but it cannot change or archive anything in GuardDuty.
3. **Code**: Lambda > `rock-em-soc-em-robot` > Code > Upload from > .zip file >
   `dist/rock-em-soc-em-robot.zip`. Then Configuration > General > Edit: timeout **90 seconds**.
4. **The live wire**: Amazon EventBridge > Rules > **Create rule**
   - Name `rock-em-guardduty-findings`, event bus `default`, rule type **Rule with an event pattern**.
   - Event source **AWS events**. Event pattern: AWS services > **GuardDuty** > **GuardDuty Finding**.
   - Target: AWS service > **Lambda function** > `rock-em-soc-em-robot`. Create.

## Ring the bell (for the demo)

Generate three specific sample findings from **CloudShell** (the `>_` icon in the console's top bar).
Do not use the console's "Generate sample findings" button: it creates one of every finding type
(hundreds), and the robot would triage every one of them.

```bash
DET=$(aws guardduty list-detectors --query 'DetectorIds[0]' --output text)
aws guardduty create-sample-findings --detector-id "$DET" --finding-types \
  'UnauthorizedAccess:EC2/SSHBruteForce' 'CryptoCurrency:EC2/BitcoinTool.B!DNS' 'Recon:EC2/PortProbeUnprotectedPort'
```

GuardDuty sends new findings to EventBridge within a few minutes; the page checks for new bouts every
15 seconds and flashes each new one. Sample findings are marked as samples by GuardDuty, and the robot
says so in its answer.

## Reusing the tool in your own agent

`guardduty_tool.py` has no dependency on the rest of the robot:

- `TOOL`: name, description and JSON schema (Bedrock Converse `toolSpec` or a Strands `@tool` wrapper).
- `get_guardduty_findings(args)`: list recent active findings, or get one by id.
- `finding_summary(finding)`: works on API findings and on EventBridge event `detail`, keeps the facts
  a model needs (type, resource, remote IP and owner, counts, threat intel) and redacts account IDs
  and access keys.
