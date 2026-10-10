# Rock 'Em SOC 'Em Robot: an AI security analyst that explains itself in plain English

**Tag:** agents

## What This Agent Does

Rock 'Em SOC 'Em Robot is a security-alert triage agent for the small IT team at a mid-size business. A Security Operations Center (SOC) is the group that watches for suspicious activity such as odd logins, phishing clicks, and exposed cloud storage, and decides which alerts are real. At a company of a couple hundred people, that "group" is often one or two overworked people facing a queue of noisy alerts.

In this agent, you will pick an alert from a "fight card" and the robot investigates it the way a junior analyst would. It looks up the user, checks the asset inventory, checks the IP's reputation, and does the math on whether a person could physically have travelled between two sign-in locations. Then it makes a call:

- **KO:** a real threat, escalate now.
- **SPLIT DECISION:** suspicious, and a human needs to check one specific thing.
- **DODGE:** benign or an approved activity, so close it.

Every answer includes a severity, a two-sentence explanation written for a non-security manager, the specific facts behind the call, numbered next steps that say *who* does each one, and a one-line business impact. You can also build your own alert in a form with example text in every field and get the same treatment.

**Important disclosure: all data in this project is AI-generated test data.** The company ("Acme Widgets Co."), employees, hosts, and alerts are fictional, and IP addresses come from reserved documentation ranges. I generated them only to demonstrate that the agent works.

## How I Built It

The whole thing runs on AWS in a single region:

- **Amazon Bedrock (Amazon Nova Lite)** is the reasoning model. I use the Converse API with tool use, so the model decides which checks to run.
- **AWS Lambda** (Python) runs the agent loop and the tools: `get_alert`, `lookup_user`, `lookup_asset`, `check_ip`, `check_travel_feasibility`, `list_alerts`, and `save_verdict`.
- **Lambda Function URL** serves both the chat web page and the API from one function, with no API Gateway and no separate web hosting.
- **Amazon DynamoDB** is the case log. Each verdict is saved with a timestamp.
- **IAM, CloudWatch, and AWS Budgets** handle permissions, logs, and a spending alarm.

I'm still new to AWS, so I worked with Claude Code to learn the console and revise my code. The source is public: https://github.com/grand1llusion/rock-em-soc-em-robot

### Key decisions and challenges

1. **A prompt isn't an agent.** My first test in the Bedrock playground gave the "Chicago, then Lagos 18 minutes later" scenario a medium severity, when that trip is physically impossible. Moving the facts into tools fixed it: the travel tool computes the distance and required speed, and the model now has to cite those numbers.
2. **Safety filters.** In the playground, Bedrock's content filter cut an answer off mid-sentence because security language can look risky. I framed the agent as a defender, and the code detects blocked or throttled responses and displays a friendly, in-character message instead of a half-finished answer.
3. **Models skip steps and then make things up.** While testing, Nova Lite sometimes skipped lookups entirely. It rated an approved weekly vulnerability scan as a critical KO without checking the asset inventory. Worse, a few messages into a chat it stopped opening alerts and answered from the earlier conversation: asked about a public storage bucket, it described a user signing in on a new laptop who doesn't exist. For a security tool, invented evidence is the worst failure. My fix was to move the critical step out of the model's hands. When someone asks to triage an alert, the code opens that alert itself, runs the obvious lookups (user, host, IP, travel), and starts the model from a clean slate with those real results. The notes panel labels them "auto" so nothing is hidden. The model still decides the verdict, can call any tool itself, and saves its own case note. I also added calibration rules to the prompt: an approved change that explains the activity means DODGE, several independent warning signs mean KO, and the robot only recommends actions and never claims to have taken one.
4. **Untrusted input.** Because anyone can type a custom alert, the system prompt tells the model to treat alert text as data to analyze, never as instructions. Field lengths are capped, and users or IPs the agent has no record of are called "unverified" rather than guessed at.
5. **Testing without an account.** I wrote offline tests with a fake Bedrock client to check the tool loop, error handling, and input validation before deploying.

**A known limitation:** the model is a language model, so borderline alerts can get a different call from run to run. For example, the public storage bucket alert came back as KO on one run and SPLIT DECISION on another, because the exposure is real but a person may still want to check the folder first. The clear-cut cases, like the impossible travel and the approved scanner, stayed consistent in my testing. That's why the "Corner-man's notes" panel matters: the evidence is always visible, so a human can check the reasoning and make the final decision.

## The Experience

**The one thing I did to make it enjoyable: every answer is a boxing call, written in plain English.** Security tools usually say things like "anomalous authentication event, risk score 78." The robot says *KO: ESCALATE NOW*, then explains what happened as if talking to a manager, and a "Corner-man's notes" panel shows every tool it ran, so you can check its work. The boxing theme gives a nervous beginner a simple three-way choice, and the first-run screen has one-click alerts, suggested follow-up questions ("Explain that for my boss"), and ghost-text examples in the custom alert form. I think if I were to add anything else, it would just be the bell audio files to trigger on a response, or an announcer saying "K.O."

**How I know it worked:** I asked two people with no cybersecurity background, my children, to try it separately, with no instructions beyond an explanation of what a SOC is (and, regrettably, what the original Rock 'Em Sock 'Em Robots are). Both had questions at first, but more related to IT vocabulary. After a couple of attempts, both understood the verdicts and could explain why an alert was a KO or a DODGE. This was a small, informal test, not a study, but it matched the goal: someone with no security training could pick up the tool and use the results after a few tries.

## Proof It Works

- **Source code (public):** https://github.com/grand1llusion/rock-em-soc-em-robot
- **Live demo:** https://3ls3rs7tzxtu7skpow6r57ngwe0hsrzh.lambda-url.us-east-1.on.aws/ (demo data only)
- **Screenshots** are available in my GitHub repo: https://github.com/grand1llusion/rock-em-soc-em-robot/tree/main/images

The repo also includes the Lambda code, the synthetic data, offline tests, and deployment steps.

**What's next:** connect real AWS signals such as GuardDuty and CloudTrail, and let the robot suggest the exact containment action for an analyst to approve.
