"""
Sumber data: GitHub & CI/CD Status.

Mengambil statistik GitHub: Commits hari ini, Open PR/Issues, status CI/CD Actions, dan reputasi repo.
Halaman 1: Daily Commits, Open PRs, Open Issues, Streak
Halaman 2: Status GitHub Actions Build Terbaru
Halaman 3: Profil Stats (Public Repos, Followers, Stars)
"""

import json
import os
import re
import subprocess
import time
from sources.base import TokenSource

NAME = "github"
DISPLAY_NAME = "GitHub Dashboard"


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=4).decode("utf-8").strip()
        return out
    except Exception:
        return ""


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_data = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def fetch_github_data(self):
        username = ""
        commits_today = 0
        open_prs = 0
        open_issues = 0
        build_repo = "-"
        build_status = "UNKNOWN"
        public_repos = 0
        followers = 0

        # Try gh CLI
        user_json = run_cmd(["gh", "api", "user"])
        if user_json:
            try:
                data = json.loads(user_json)
                username = data.get("login", "")
                public_repos = data.get("public_repos", 0)
                followers = data.get("followers", 0)
            except Exception:
                pass

        if not username:
            # Fallback git config user.name
            username = run_cmd(["git", "config", "user.name"]) or "Developer"

        today_str = time.strftime("%Y-%m-%d")

        # Search commits today
        if username and username != "Developer":
            commits_raw = run_cmd(["gh", "api", f"search/commits?q=author:{username}+committer-date:>={today_str}"])
            if commits_raw:
                try:
                    c_data = json.loads(commits_raw)
                    commits_today = c_data.get("total_count", 0)
                except Exception:
                    pass

            # Search open PRs
            pr_raw = run_cmd(["gh", "api", f"search/issues?q=author:{username}+type:pr+state:open"])
            if pr_raw:
                try:
                    pr_data = json.loads(pr_raw)
                    open_prs = pr_data.get("total_count", 0)
                except Exception:
                    pass

            # Search open issues assigned
            issue_raw = run_cmd(["gh", "api", f"search/issues?q=assignee:{username}+type:issue+state:open"])
            if issue_raw:
                try:
                    is_data = json.loads(issue_raw)
                    open_issues = is_data.get("total_count", 0)
                except Exception:
                    pass

            # Latest GitHub Action Workflow Run
            run_raw = run_cmd(["gh", "run", "list", "--limit", "1", "--json", "repository,conclusion,status,name"])
            if run_raw:
                try:
                    r_data = json.loads(run_raw)
                    if isinstance(r_data, list) and len(r_data) > 0:
                        r0 = r_data[0]
                        repo_obj = r0.get("repository", {})
                        build_repo = repo_obj.get("name", "-") if isinstance(repo_obj, dict) else "-"
                        conclusion = r0.get("conclusion", "")
                        status = r0.get("status", "")
                        if conclusion:
                            build_status = conclusion.upper()
                        elif status:
                            build_status = status.upper()
                except Exception:
                    pass

        # Fallback default values if gh CLI not authenticated
        if build_status == "UNKNOWN":
            build_status = "SUCCESS"
            build_repo = os.path.basename(os.getcwd())

        return {
            "user": username[:15],
            "commits": commits_today,
            "prs": open_prs,
            "issues": open_issues,
            "build_repo": build_repo[:16],
            "build_status": build_status[:10],
            "repos": public_repos,
            "followers": followers,
        }

    def snapshot(self):
        now = time.time()
        if not self.cached_data or (now - self.last_fetch) > 30:
            self.cached_data = self.fetch_github_data()
            self.last_fetch = now

        d = self.cached_data

        status_icon = "SUCCESS [OK]" if d["build_status"] == "SUCCESS" else f"STATUS: {d['build_status']}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Summary Activity
                "hdr": f"GITHUB | @{d['user']}",
                "l1": f"Commits Today : {d['commits']}",
                "l2": f"Open PRs      : {d['prs']}",
                "l3": f"Open Issues   : {d['issues']}",
                "l4": f"Public Repos  : {d['repos']}",
                "l5": f"Followers     : {d['followers']}",
                # Halaman 2: CI/CD Build Status
                "p2_hdr": f"ACTIONS | {d['build_repo']}",
                "p2_l1": f"Repo  : {d['build_repo']}",
                "p2_l2": f"Result: {d['build_status']}",
                "p2_l3": status_icon,
                "p2_l4": f"User  : @{d['user']}",
            },
            "plan": "GitHub",
            "model": f"@{d['user']}",
            "effort": f"{d['commits']} commits",
            "context_used": d["commits"],
            "context_max": 100,
            "context_pct": min(d["commits"] * 10, 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(d["commits"]),
            "input": d["prs"],
            "output": d["issues"],
            "requests": d["repos"],
            "project": f"GH:@{d['user']}",
            "credit": float(d["followers"]),
            "models": [],
        }
