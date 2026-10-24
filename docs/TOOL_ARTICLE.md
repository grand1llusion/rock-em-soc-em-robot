# SOC It To 'Em gets a live wire: giving an AI SOC agent a GuardDuty tool

*Description (1–2 sentences):* My AI security-triage agent used to spar only with six practice alerts.
One new tool, an Amazon GuardDuty reader wired up with Amazon EventBridge, now lets it triage real
findings from my AWS account the moment they happen, with nobody at the keyboard.

**Demo video:** https://www.youtube.com/watch?v=u9MZofCVn0s  
**Code:** https://github.com/grand1llusion/rock-em-soc-em-robot  
**Notebook:** https://github.com/grand1llusion/rock-em-soc-em-robot/blob/main/notebooks/guardduty_tool_quickstart.ipynb

## The agent I started with

SOC It To 'Em is a security-alert triage agent for a small IT team. A Security Operations Center (SOC)
is the group that decides which alerts are real; at a small company that "group" is often one tired
person. You pick an alert and the robot investigates like a junior analyst: it looks up the user, the
asset and the IP reputation, checks whether "impossible travel" is really impossible, and makes a
call in plain English:

- **KO**: a real threat, escalate now.
- **SPLIT DECISION**: a human needs to check one specific thing.
- **DODGE**: benign or approved, close it.

Every answer shows a severity, what happened, why, who should do what next, and the business impact,
plus a "Corner-man's notes" panel listing every tool call so a human can check its work.

It runs on **AWS Lambda** (one function behind a Function URL), **Amazon Bedrock** (Amazon Nova Lite,
through the Converse API with tool use) and **Amazon DynamoDB** for the case log.

**What it could not do:** everything it knew came from six AI-generated practice alerts about a
fictional company. Ask it about the real AWS account it lives in and it was blind. It also only ever
worked when someone opened the page and clicked.

## The one new tool, and why I picked it

The new tool is **`get_guardduty_findings`**, which reads findings from **Amazon GuardDuty**, AWS's
own threat-detection service. I picked it because it closes the biggest gap: a SOC agent that can
only see made-up alerts is a demo, and one that sees the real account's threat feed is a teammate.

The tool does two things:

- With no id, it lists the most recent active findings. With a `GD-…` id, it returns one finding's
  facts: the finding type, the affected resource, the remote IP with its country and network owner,
  how many times it was seen, threat-intel matches and GuardDuty's severity.
- Before anything reaches the model, the browser or the case log, it **redacts the AWS account ID and
  access key IDs**. The robot's IAM permissions only allow it to *read* GuardDuty, never change or
  archive anything.

Then I wired GuardDuty to the robot with an **Amazon EventBridge** rule: every new "GuardDuty Finding"
event invokes the same Lambda function. The robot opens the finding with its new tool, makes the
call, saves it to the case log, and the page shows it under a new **Live bouts** panel.

## The new behaviour

- **It triages on its own.** When GuardDuty raises a finding, a verdict appears on the page a few
  moments later, before anyone opens it. In my test, a crypto-mining DNS lookup arrived as a
  **KO, high**, and a port probe and an SSH brute-force attempt as **SPLIT DECISION**.
- **You can still talk to it.** Open a live bout and ask "Explain that for my boss", or press "Ask me
  to check GuardDuty now" and it pulls the latest findings and picks the one to handle first.
- **Its first real finding was me.** Besides GuardDuty's test samples, it found a genuine finding:
  my AWS root login had been used, 168 times, while I built this. The robot sent it to a human
  (SPLIT DECISION) and explained why it should be looked at first even though GuardDuty scores it
  low. Lesson learned: lock down root and use an everyday admin login.

## What I learned building it

1. **Findings arrive in two shapes.** The GuardDuty API returns PascalCase keys and EventBridge events
   use camelCase. The tool normalises both, so one function serves the chat path and the live path.
2. **Models judge from what you hand them.** In my first live run, Nova Lite asked for a list of
   findings, got short summaries, and judged from those even though its instructions said to fetch
   the details. Rather than hope it listens, I changed the tool: short lists now carry the full facts.
3. **GuardDuty re-sends updates.** The same finding can arrive many times as its count grows, so the
   robot triages each finding once and skips repeats. That also keeps the cost predictable.
4. **Sample findings are reused.** Generating the same sample type again updates the old finding
   instead of creating a new one, so for demos I generate new sample types from CloudShell (never the
   console button, which creates one of every type).
5. **One switch for before and after.** A `GUARDDUTY_TOOL=off` environment variable runs the robot
   exactly as it was before the tool, which made the before/after demo honest and easy to film.

## Reuse the pattern

`lambda/guardduty_tool.py` has no dependency on the rest of the robot:

- `TOOL`: the name, description and JSON schema, ready for a Bedrock Converse `toolSpec` (or wrap it
  in a Strands `@tool`).
- `get_guardduty_findings(args)`: the tool itself.
- `finding_summary(finding)`: works on API findings and on EventBridge event `detail`, keeps the facts
  a model needs, and redacts account IDs and access keys.

A [quickstart notebook](https://github.com/grand1llusion/rock-em-soc-em-robot/blob/main/notebooks/guardduty_tool_quickstart.ipynb)
walks through the tool step by step and runs without AWS. The repo also has a read-only IAM policy, the EventBridge setup steps, and offline tests with a fake
GuardDuty, so you can try it without an AWS account
([docs/GUARDDUTY.md](https://github.com/grand1llusion/rock-em-soc-em-robot/blob/main/docs/GUARDDUTY.md)).

## Honest notes

- The fight-card alerts are AI-generated test data. Live bouts are real GuardDuty findings from my
  account, mostly GuardDuty's own test samples, which use placeholder values, so the robot's
  explanations of samples are more generic than for real findings.
- The robot only **recommends** actions; it cannot lock accounts or isolate instances.
- The video narration uses an AI-generated voice.

**Built with:** AWS Lambda, Amazon Bedrock (Amazon Nova Lite), Amazon DynamoDB, Amazon GuardDuty,
Amazon EventBridge, AWS IAM. I'm still new to AWS and built this with Claude Code as a pair programmer.
