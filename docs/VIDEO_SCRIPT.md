# Video script: "SOC It To 'Em gets a live wire" (target 2:45, hard limit 3:00)

**Story in one line:** before, the robot only sparred with six practice alerts; after one new tool, it
fights live bouts from Amazon GuardDuty the moment they happen.

## Before you record

- Browser zoom 110–125% so text is readable on a phone; hide the bookmarks bar (Ctrl+Shift+B).
- **Never show the AWS account ID** (top-right of the console). Crop, zoom or blur it in every console shot.
- Keep the old `rock-em-…` resource names out of close-ups: crop to the part of the screen you need
  (the variables table, the rule's event pattern), not the page title.
- No music, no logos besides AWS's own console. If you use an AI voice, add "Narration: AI-generated
  voice" to the YouTube description.
- Record each scene separately, then trim the waits in Clipchamp and add the on-screen text below.

## Script

| Time | ON SCREEN (cue) | VOICEOVER | ON-SCREEN TEXT |
|---|---|---|---|
| 0:00–0:12 | Page header: SOC IT TO 'EM, ● LIVE tag | "Security teams drown in alerts. SOC It To 'Em is my AI corner-man: it reads an alert, checks the facts, and makes the call, KO, split decision or dodge, in plain English." | SOC It To 'Em · AI security-alert triage on AWS |
| 0:12–0:22 | **BEFORE.** 2 s of Lambda > Environment variables showing `GUARDDUTY_TOOL = off` (crop to the table). Then the page: fight card only, no Live bouts | "Here's where it started: one Lambda function, Amazon Bedrock for the thinking, DynamoDB for the case log." | BEFORE |
| 0:22–0:32 | Click ALR-1001 → KO answer (jump-cut the wait) | "It can work an alert: impossible travel, KO, escalate now." | |
| 0:32–0:42 | Type "Are there any new findings from Amazon GuardDuty in our AWS account?" → its answer that it can't check | "But it only ever sparred with six practice alerts. Ask about the real AWS account, and it's blind." | It can't see the real account |
| 0:42–0:55 | GitHub: `lambda/guardduty_tool.py`, scroll past `TOOL` and `redact` | "So I gave it one new tool: get GuardDuty findings. It reads Amazon GuardDuty, AWS's own threat detector, and strips my account ID and access keys before the model ever sees them." | NEW TOOL: get_guardduty_findings |
| 0:55–1:05 | EventBridge rule's event pattern: GuardDuty Finding → Lambda (crop the name) | "Then an EventBridge rule wires GuardDuty to the robot. Every new finding rings the bell, no clicks needed." | GuardDuty → EventBridge → Lambda |
| 1:05–1:12 | Delete `GUARDDUTY_TOOL`, Save; reload the page: **Live bouts** panel appears | "Flip the switch on, and there's a new corner: live bouts." | AFTER |
| 1:12–1:22 | CloudShell: paste and run `create-sample-findings` | "Let's ring it. I ask GuardDuty to raise three test findings." | GuardDuty sample findings (safe, no real attack) |
| 1:22–1:40 | Back on the page; jump-cut to the new bouts sliding in and flashing; hold on their verdict tags | "A few minutes later, with nobody touching anything, they're on the card, already triaged. Each one: a verdict, a severity, and GuardDuty's own score." | Triaged automatically |
| 1:40–2:00 | Click the **KO** bout; scroll the answer; open Corner-man's notes and point at "⚙ auto · get_guardduty_findings" | "Open one and the whole call is there: what happened, why, who should do what next, and the exact evidence it pulled from GuardDuty, so a human can check its work." | |
| 2:00–2:10 | Click "Explain that for my boss" → answer | "And it's still a conversation. Ask a follow-up, and it explains it for the boss." | |
| 2:10–2:28 | The root-credential finding answer ("seen 168 times") | "Its first real finding? Me. While I built this, GuardDuty caught my root login being used, a hundred and sixty-eight times. The robot sent it to a human. Lesson learned: lock down root, use an everyday admin login." | A real finding, not a sample |
| 2:28–2:42 | GitHub: `docs/GUARDDUTY.md` and the test run (`OK`) | "The tool is one standalone file. It reads GuardDuty's API and EventBridge events alike, ships with a read-only IAM policy and offline tests, and drops into any Bedrock or Strands agent." | Reuse it: docs/GUARDDUTY.md |
| 2:42–2:50 | Back to the page header with Live bouts | "Before: practice dummies. Now: live bouts. SOC It To 'Em." | github.com/grand1llusion/rock-em-soc-em-robot |

About 340 words: comfortable at a normal speaking pace, with room for the jump cuts.

## Footage checklist

- [ ] Header shot (0:00)
- [ ] BEFORE: env var `off`, fight card, ALR-1001 KO, the "Are there any GuardDuty findings?" question
- [ ] GitHub: `guardduty_tool.py`, `docs/GUARDDUTY.md`, a test run
- [ ] EventBridge rule pattern
- [ ] Switch on + reload showing Live bouts
- [ ] CloudShell `create-sample-findings` with **new** finding types (re-used types do not create new bouts)
- [ ] New bouts arriving, the KO bout with its notes, "Explain that for my boss"
- [ ] The root-credential finding answer

## Upload

YouTube, visibility **Public**, under 3:00. Title: "SOC It To 'Em: giving an AI SOC agent a live GuardDuty
tool". Put the GitHub link and "Narration: AI-generated voice" (if used) in the description.
