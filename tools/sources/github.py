"""
Sumber data: GitHub & CI/CD Status Dashboard.

Mengambil data statistik GitHub: Commits hari ini, Public Repos, Followers, dan Status CI/CD / Active Repo.
Menggunakan kombinasi GitHub REST API, gh CLI, dan Git Local Log.
Halaman 1: Commits Today, Public Repos, Followers, Open PRs/Issues
Halaman 2: CI/CD Build Status / Active Repo Info
"""

import json
import os
import re
import subprocess
import time
import urllib.request
from sources.base import TokenSource

NAME = "github"
DISPLAY_NAME = "GitHub Dashboard"


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=3).decode("utf-8").strip()
        return out
    except Exception:
        return ""


def get_git_username():
    # 1. gh CLI
    gh_user = run_cmd(["gh", "api", "user", "-q", ".login"])
    if gh_user:
        return gh_user

    # 2. git config
    git_user = run_cmd(["git", "config", "user.name"])
    if git_user:
        return git_user

    # 3. git config user.email or folder
    return "trianapriliant"


def get_local_commits_today():
    try:
        midnight = time.strftime("%Y-%m-%d 00:00:00")
        out = run_cmd(["git", "log", f"--since={midnight}", "--oneline"])
        return len(out.splitlines()) if out else 0
    except Exception:
        return 0


def fetch_github_info(username):
    public_repos = 0
    followers = 0
    remote_commits = 0
    latest_repo = os.path.basename(os.getcwd())
    build_status = "SUCCESS"

    # 1. Fetch User Profile
    if username:
        try:
            url = f"https://api.github.com/users/{urllib.parse.quote(username)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    d = json.loads(resp.read().decode("utf-8"))
                    public_repos = d.get("public_repos", 0)
                    followers = d.get("followers", 0)
        except Exception:
            pass

        # 2. Fetch Public Events Today
        try:
            today_str = time.strftime("%Y-%m-%d")
            url_ev = f"https://api.github.com/users/{urllib.parse.quote(username)}/events/public"
            req_ev = urllib.request.Request(url_ev, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_ev, timeout=3) as resp:
                if resp.status == 200:
                    events = json.loads(resp.read().decode("utf-8"))
                    for ev in events:
                        ev_date = ev.get("created_at", "")[:10]
                        if ev_date == today_str and ev.get("type") == "PushEvent":
                            commits_list = ev.get("payload", {}).get("commits", [])
                            remote_commits += len(commits_list)
                            repo_full = ev.get("repo", {}).get("name", "")
                            if repo_full:
                                latest_repo = repo_full.split("/")[-1]
        except Exception:
            pass

    # 3. Check gh CLI workflow run status if available
    gh_run = run_cmd(["gh", "run", "list", "--limit", "1", "--json", "conclusion,status,repository"])
    if gh_run:
        try:
            r_data = json.loads(gh_run)
            if isinstance(r_data, list) and len(r_data) > 0:
                r0 = r_data[0]
                conc = r0.get("conclusion", "") or r0.get("status", "")
                if conc:
                    build_status = conc.upper()
                r_obj = r0.get("repository", {})
                if isinstance(r_obj, dict) and r_obj.get("name"):
                    latest_repo = r_obj.get("name")
        except Exception:
            pass

    local_commits = get_local_commits_today()
    total_commits = max(local_commits, remote_commits)

    return {
        "user": username[:15],
        "commits": total_commits,
        "repos": public_repos,
        "followers": followers,
        "repo": latest_repo[:15],
        "status": build_status[:10],
    }


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

    def snapshot(self):
        now = time.time()
        if not self.cached_data or (now - self.last_fetch) > 15:
            username = get_git_username()
            self.cached_data = fetch_github_info(username)
            self.last_fetch = now

        d = self.cached_data
        status_text = "PASSED [OK]" if d["status"] in ("SUCCESS", "COMPLETED") else f"STATUS:{d['status']}"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Summary Activity
                "hdr": f"GITHUB | @{d['user']}",
                "l1": f"Commits Today : {d['commits']}",
                "l2": f"Public Repos  : {d['repos']}",
                "l3": f"Followers     : {d['followers']}",
                "l4": f"Active Repo   : {d['repo']}",
                "l5": f"Build Status  : {d['status']}",
                # Halaman 2: Actions & Repository Details
                "p2_hdr": f"ACTIONS | {d['repo']}",
                "p2_l1": f"Repo  : {d['repo']}",
                "p2_l2": f"Result: {d['status']}",
                "p2_l3": status_text,
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
            "input": d["repos"],
            "output": d["followers"],
            "requests": d["commits"],
            "project": f"GH:@{d['user']}",
            "credit": float(d["followers"]),
            "models": [],
        }
