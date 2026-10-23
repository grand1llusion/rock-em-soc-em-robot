"""Synthetic data for SOC It To 'Em.

EVERYTHING in this file is AI-generated test data for the fictional company
"Acme Widgets Co." (about 250 employees). No real people, hosts, or customers.
IP addresses come from the RFC 5737 documentation ranges (203.0.113.0/24,
198.51.100.0/24) or private ranges, so they never point at real systems.
"""

COMPANY = "Acme Widgets Co. (fictional, ~250 employees)"

ALERTS = {
    "ALR-1001": {
        "id": "ALR-1001",
        "title": "Impossible travel: jsmith signed in from two continents",
        "source": "Identity provider (SSO)",
        "time": "Tue 09:20 CT",
        "details": (
            "User jsmith signed in from Chicago, US at 09:02 CT (MacBook, usual "
            "browser). At 09:20 CT the same account signed in from Lagos, "
            "Nigeria (new Windows device, IP 198.51.100.77). The second sign-in "
            "passed MFA with a push approval 40 seconds after the prompt."
        ),
        "entities": {"user": "jsmith", "ip": "198.51.100.77",
                     "from_city": "Chicago", "to_city": "Lagos", "minutes_apart": 18},
    },
    "ALR-1002": {
        "id": "ALR-1002",
        "title": "Phishing: Finance user clicked a lookalike invoice link",
        "source": "Email security + web proxy",
        "time": "Wed 14:41 CT",
        "details": (
            "mgarcia received an email 'Invoice overdue - action required' from "
            "billing@acme-widgets-pay.com (our real domain is acmewidgets.example). "
            "She clicked the link at 14:38. The proxy then logged a form POST to "
            "acme-widgets-pay.com (domain registered 2 days ago, IP 203.0.113.50) "
            "which looks like a credential-harvesting login page."
        ),
        "entities": {"user": "mgarcia", "ip": "203.0.113.50",
                     "domain": "acme-widgets-pay.com"},
    },
    "ALR-1003": {
        "id": "ALR-1003",
        "title": "Brute force then success on the SSH bastion",
        "source": "Bastion host auth logs",
        "time": "Thu 03:12 CT",
        "details": (
            "148 failed SSH logins for several account names from 203.0.113.9 "
            "between 03:02 and 03:11 CT, followed by one SUCCESSFUL login as "
            "svc-backup at 03:12 CT from the same IP. Afterwards, svc-backup ran "
            "'whoami' and 'cat /etc/passwd'."
        ),
        "entities": {"user": "svc-backup", "ip": "203.0.113.9", "host": "bastion-01"},
    },
    "ALR-1004": {
        "id": "ALR-1004",
        "title": "Cloud storage bucket made public",
        "source": "Cloud configuration monitor",
        "time": "Fri 11:05 CT",
        "details": (
            "Bucket 'acme-marketing-assets' was changed from private to "
            "public-read by user rpatel (Marketing). The bucket holds 212 files: "
            "mostly product brochures and logos, plus one folder named "
            "'q3-customer-list-DRAFT' with 3 spreadsheets."
        ),
        "entities": {"user": "rpatel", "asset": "acme-marketing-assets"},
    },
    "ALR-1005": {
        "id": "ALR-1005",
        "title": "Internal port scan detected",
        "source": "Network IDS",
        "time": "Sat 01:30 CT",
        "details": (
            "Host 10.20.5.14 probed 1,900 ports across 60 internal servers in "
            "40 minutes, using many scan signatures."
        ),
        "entities": {"ip": "10.20.5.14"},
    },
    "ALR-1006": {
        "id": "ALR-1006",
        "title": "New admin account created at 2 AM on a Sunday",
        "source": "Directory audit log",
        "time": "Sun 02:14 CT",
        "details": (
            "User dthompson (IT admin) created a new domain admin account "
            "'tmp-migration-admin' at 02:14 CT from his usual laptop on the "
            "corporate VPN."
        ),
        "entities": {"user": "dthompson", "ip": "10.20.8.31"},
    },
}

USERS = {
    "jsmith": {
        "name": "Jordan Smith", "title": "Sales Director", "department": "Sales",
        "home_location": "Chicago, US", "usual_devices": ["MacBook Pro (managed)"],
        "mfa": "push notifications", "privileged": False,
        "notes": "Travels domestically. No international travel on the calendar this month.",
    },
    "mgarcia": {
        "name": "Maria Garcia", "title": "Accounts Payable Specialist", "department": "Finance",
        "home_location": "Austin, US", "usual_devices": ["Dell laptop (managed)"],
        "mfa": "push notifications", "privileged": False,
        "notes": "Can approve vendor payments up to $25,000. High-value target for fraud.",
    },
    "svc-backup": {
        "name": "Backup service account", "title": "Service account", "department": "IT",
        "home_location": "n/a", "usual_devices": ["backup-01 (10.20.1.5)"],
        "mfa": "none (key-based)", "privileged": True,
        "notes": "Should ONLY ever log in from 10.20.1.5. Never interactive, never runs 'whoami'.",
    },
    "rpatel": {
        "name": "Riya Patel", "title": "Marketing Coordinator", "department": "Marketing",
        "home_location": "Chicago, US", "usual_devices": ["MacBook Air (managed)"],
        "mfa": "push notifications", "privileged": False,
        "notes": "Has storage-admin rights on the marketing bucket only. Preparing a brochure download page.",
    },
    "dthompson": {
        "name": "Dana Thompson", "title": "Senior Systems Administrator", "department": "IT",
        "home_location": "Chicago, US", "usual_devices": ["ThinkPad (managed)"],
        "mfa": "hardware key", "privileged": True,
        "notes": "On-call this weekend. Open change ticket CHG-2240: 'Weekend server migration, "
                 "temporary admin account tmp-migration-admin approved, to be deleted Monday'.",
    },
}

ASSETS = {
    "10.20.5.14": {
        "name": "nessus-scanner-01", "owner": "IT Security", "role": "Approved vulnerability scanner",
        "notes": "Runs the weekly authenticated scan Saturdays 01:00-04:00 CT under change ticket CHG-2231.",
    },
    "10.20.1.5": {
        "name": "backup-01", "owner": "IT", "role": "Backup server",
        "notes": "The only host svc-backup should log in from.",
    },
    "bastion-01": {
        "name": "bastion-01", "owner": "IT", "role": "SSH jump host, internet-facing",
        "notes": "Password logins are still enabled (known gap). Gateway to production servers.",
    },
    "10.20.8.31": {
        "name": "dthompson-vpn-lease", "owner": "IT", "role": "VPN address pool",
        "notes": "Corporate VPN client range.",
    },
    "acme-marketing-assets": {
        "name": "acme-marketing-assets", "owner": "Marketing", "role": "Cloud storage bucket",
        "notes": "Intended to host public brochures. The folder 'q3-customer-list-DRAFT' should NOT be public: "
                 "it contains customer names and emails (internal data).",
    },
}

IP_REPUTATION = {
    "198.51.100.77": {"country": "Nigeria", "reputation": "suspicious",
                      "detail": "Residential proxy network seen in credential-stuffing campaigns."},
    "203.0.113.50": {"country": "Netherlands", "reputation": "malicious",
                     "detail": "Hosts a known phishing kit; domain acme-widgets-pay.com registered 2 days ago."},
    "203.0.113.9": {"country": "Romania", "reputation": "malicious",
                    "detail": "Reported for SSH brute forcing across many networks in the last 7 days."},
}

# City -> (latitude, longitude), used by the travel-feasibility tool.
CITIES = {
    "chicago": (41.88, -87.63), "lagos": (6.52, 3.38), "new york": (40.71, -74.01),
    "london": (51.51, -0.13), "austin": (30.27, -97.74), "seattle": (47.61, -122.33),
    "denver": (39.74, -104.99), "los angeles": (34.05, -118.24), "toronto": (43.65, -79.38),
    "frankfurt": (50.11, 8.68), "mumbai": (19.08, 72.88), "singapore": (1.35, 103.82),
    "sao paulo": (-23.55, -46.63), "moscow": (55.76, 37.62), "bucharest": (44.43, 26.10),
}
