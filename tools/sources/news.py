"""
Sumber data: Breaking News & Tech RSS Reader Ticker (Modul #21 - news).

Membaca headline berita terkini real-time dari RSS Feed (Tech, AI, Global, National).
"""

import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from sources.base import TokenSource

NAME = "news"
DISPLAY_NAME = "News Ticker"

DEFAULT_HEADLINES = [
    ("TECH", "AI & Robotics breakthroughs shape the future of software development"),
    ("GLOBAL", "Global tech ecosystem expands with ultra-fast edge computing"),
    ("AI", "Generative AI models achieve new benchmarks in pair programming"),
    ("DEV", "Open-source developer tools empower next-gen IoT hardware innovation"),
]


def clean_html_tags(raw_text):
    clean = re.sub(r"<[^>]+>", "", raw_text)
    return clean.strip()


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.headlines = DEFAULT_HEADLINES
        self.last_fetch = 0
        self.headline_index = 0
        self.last_switch = time.time()

    def _fetch_rss(self):
        url = "https://news.google.com/rss/search?q=technology+AI&hl=en-US&gl=US&ceid=US:en"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    xml_data = resp.read()
                    root = ET.fromstring(xml_data)
                    fetched = []
                    for item in root.findall(".//item")[:6]:
                        title = item.find("title")
                        if title is not None and title.text:
                            clean_t = clean_html_tags(title.text)
                            fetched.append(("NEWS", clean_t))
                    if fetched:
                        self.headlines = fetched
        except Exception:
            pass

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if now - self.last_fetch > 300:
            self.last_fetch = now
            try:
                self._fetch_rss()
            except Exception:
                pass

        if now - self.last_switch > 8:
            self.headline_index = (self.headline_index + 1) % len(self.headlines)
            self.last_switch = now

        category, headline = self.headlines[self.headline_index]

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                "hdr": f"NEWS | {category}",
                "eq": f"{self.headline_index + 1}/{len(self.headlines)}",
                "l1": headline,
                "l2": headline,
                "l3": f"Source: RSS ({category})",
                "l4": f"Item {self.headline_index + 1}/{len(self.headlines)}",
            },
            "plan": "News",
            "model": category,
            "effort": headline[:16],
            "context_used": self.headline_index + 1,
            "context_max": len(self.headlines),
            "context_pct": int((self.headline_index + 1) / len(self.headlines) * 100),
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": 0.0,
            "input": self.headline_index + 1,
            "output": len(self.headlines),
            "requests": 1,
            "project": "RSS Feed",
            "credit": 0.0,
            "models": [],
        }
