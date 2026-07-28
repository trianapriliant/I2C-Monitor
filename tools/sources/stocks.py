"""
Sumber data: Stock Market & Global Exchange Rates (Forex).

Mengambil data harga Saham Tech (AAPL, NVDA, GOOGL, MSFT, AMZN) dan Kurs Mata Uang (USD/IDR, EUR/IDR, SGD/IDR, JPY/IDR).
Halaman 1: Saham Tech Utama (AAPL, NVDA, GOOGL, MSFT, AMZN)
Halaman 2: Kurs Mata Uang Dunia (USD/IDR, EUR/IDR, SGD/IDR, JPY/IDR)
"""

import json
import urllib.request
import time
from sources.base import TokenSource

NAME = "stocks"
DISPLAY_NAME = "Stock Market"


def fetch_stock_data():
    # Use Yahoo Finance v8 chart API for fast stock quotes
    symbols = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN"]
    results = {}
    for sym in symbols:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    d = json.loads(resp.read().decode("utf-8"))
                    meta = d["chart"]["result"][0]["meta"]
                    price = meta.get("regularMarketPrice", 0.0)
                    prev_close = meta.get("chartPreviousClose", price)
                    chg_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else 0.0
                    results[sym] = (price, chg_pct)
        except Exception:
            pass

    # Fallbacks if API blocked or offline
    if "AAPL" not in results:
        results = {
            "AAPL": (224.50, 1.2),
            "NVDA": (118.25, 3.4),
            "GOOGL": (168.40, -0.5),
            "MSFT": (448.90, 0.8),
            "AMZN": (182.60, 1.5),
        }

    # Fetch Fiat Exchange Rates
    rates = {"USD": 16200, "EUR": 17650, "SGD": 12050, "JPY": 105.2}
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                d = json.loads(resp.read().decode("utf-8"))
                r = d.get("rates", {})
                idr = r.get("IDR", 16200)
                eur = r.get("EUR", 0.92)
                sgd = r.get("SGD", 1.34)
                jpy = r.get("JPY", 154.0)
                rates["USD"] = int(idr)
                rates["EUR"] = int(idr / eur) if eur else 17650
                rates["SGD"] = int(idr / sgd) if sgd else 12050
                rates["JPY"] = float(idr / jpy) if jpy else 105.2
    except Exception:
        pass

    return results, rates


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_stocks = None
        self.cached_rates = None
        self.last_fetch = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if not self.cached_stocks or (now - self.last_fetch) > 60:
            self.cached_stocks, self.cached_rates = fetch_stock_data()
            self.last_fetch = now

        s = self.cached_stocks
        r = self.cached_rates

        aapl = s.get("AAPL", (224.5, 0.0))
        nvda = s.get("NVDA", (118.25, 0.0))
        googl = s.get("GOOGL", (168.4, 0.0))
        msft = s.get("MSFT", (448.9, 0.0))
        amzn = s.get("AMZN", (182.6, 0.0))

        usd_idr = r.get("USD", 16200)
        eur_idr = r.get("EUR", 17650)
        sgd_idr = r.get("SGD", 12050)
        jpy_idr = r.get("JPY", 105.2)

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Tech Stocks (AAPL, NVDA, GOOGL, MSFT, AMZN)
                "hdr": f"STOCKS (1/2) | TECH",
                "l1": f"AAPL : ${aapl[0]:.2f} ({aapl[1]:+.1f}%)",
                "l2": f"NVDA : ${nvda[0]:.2f} ({nvda[1]:+.1f}%)",
                "l3": f"GOOGL: ${googl[0]:.2f} ({googl[1]:+.1f}%)",
                "l4": f"MSFT : ${msft[0]:.2f} ({msft[1]:+.1f}%)",
                "l5": f"AMZN : ${amzn[0]:.2f} ({amzn[1]:+.1f}%)",
                # Halaman 2: Currency Exchange Rates (USD/IDR, EUR/IDR, SGD/IDR, JPY/IDR)
                "p2_hdr": f"FOREX (2/2) | Rp{usd_idr:,}",
                "p2_l1": f"USD/IDR : Rp{usd_idr:,}",
                "p2_l2": f"EUR/IDR : Rp{eur_idr:,}",
                "p2_l3": f"SGD/IDR : Rp{sgd_idr:,}",
                "p2_l4": f"JPY/IDR : Rp{jpy_idr:.1f}",
            },
            "plan": "Stocks",
            "model": f"AAPL ${aapl[0]:.2f}",
            "effort": f"{aapl[1]:+.1f}% 24h",
            "context_used": int(aapl[0]),
            "context_max": 500,
            "context_pct": 50,
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(aapl[0]),
            "input": int(nvda[0]),
            "output": int(googl[0]),
            "requests": int(usd_idr // 100),
            "project": f"USD=Rp{usd_idr:,}",
            "credit": float(msft[0]),
            "models": [],
        }
