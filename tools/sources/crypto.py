"""
Sumber data: Crypto & Fiat Ticker (3 Halaman Multi-Koin + Animasi Ticker Carousel Clean Size 1).

Halaman 1 (5 Koin): BTC, ETH, SOL, BNB, USDT
Halaman 2 (5 Koin): XRP, DOGE, ADA, AVAX, DOT
Halaman 3 (Animasi Carousel Clean Size 1): SUI, LINK, PEPE, NEAR, APT, RENDER, FET, FIL, LTC, ICP
"""

import json
import urllib.request
import time
from sources.base import TokenSource

NAME = "crypto"
DISPLAY_NAME = "Crypto Ticker"

ALTCOINS_P3 = [
    ("sui", "SUI"),
    ("chainlink", "LINK"),
    ("pepe", "PEPE"),
    ("near", "NEAR"),
    ("aptos", "APT"),
    ("render-token", "RENDER"),
    ("fetch-ai", "FET"),
    ("filecoin", "FIL"),
    ("litecoin", "LTC"),
    ("internet-computer", "ICP"),
]


def fetch_crypto_prices():
    ids = "bitcoin,ethereum,solana,binancecoin,tether,ripple,dogecoin,cardano,avalanche-2,polkadot,sui,chainlink,pepe,near,aptos,render-token,fetch-ai,filecoin,litecoin,internet-computer"
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd,idr&include_24hr_change=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass

    # Fallback default values if API limits
    return {
        "bitcoin": {"usd": 67450, "usd_24h_change": 2.5, "idr": 1080000000},
        "ethereum": {"usd": 3480, "usd_24h_change": -1.2, "idr": 55800000},
        "solana": {"usd": 185.5, "usd_24h_change": 4.1, "idr": 2960000},
        "binancecoin": {"usd": 585.0, "usd_24h_change": 1.8, "idr": 9360000},
        "tether": {"usd": 1.00, "usd_24h_change": 0.0, "idr": 16200},
        "ripple": {"usd": 0.62, "usd_24h_change": 0.5, "idr": 9920},
        "dogecoin": {"usd": 0.135, "usd_24h_change": -0.8, "idr": 2160},
        "cardano": {"usd": 0.42, "usd_24h_change": 1.2, "idr": 6720},
        "avalanche-2": {"usd": 28.5, "usd_24h_change": 3.4, "idr": 456000},
        "polkadot": {"usd": 6.85, "usd_24h_change": 2.1, "idr": 109600},
        "sui": {"usd": 3.42, "usd_24h_change": 8.5},
        "chainlink": {"usd": 14.80, "usd_24h_change": 5.2},
        "pepe": {"usd": 0.0000092, "usd_24h_change": 12.4},
        "near": {"usd": 5.15, "usd_24h_change": 4.3},
        "aptos": {"usd": 9.20, "usd_24h_change": 3.1},
        "render-token": {"usd": 6.45, "usd_24h_change": 7.8},
        "fetch-ai": {"usd": 1.35, "usd_24h_change": 6.2},
        "filecoin": {"usd": 4.50, "usd_24h_change": 1.9},
        "litecoin": {"usd": 72.50, "usd_24h_change": 0.9},
        "internet-computer": {"usd": 8.90, "usd_24h_change": 2.7},
    }


class Source(TokenSource):
    NAME = NAME
    DISPLAY_NAME = DISPLAY_NAME

    def __init__(self, scope="today", project=None):
        super().__init__(scope=scope, project=project)
        self.cached_data = None
        self.last_fetch = 0
        self.p3_index = 0

    def available(self):
        return True

    def totals(self):
        return {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0, "requests": 0}

    def snapshot(self):
        now = time.time()
        if not self.cached_data or (now - self.last_fetch) > 30:
            self.cached_data = fetch_crypto_prices()
            self.last_fetch = now

        data = self.cached_data
        btc = data.get("bitcoin", {})
        eth = data.get("ethereum", {})
        sol = data.get("solana", {})
        bnb = data.get("binancecoin", {})
        usdt = data.get("tether", {})

        xrp = data.get("ripple", {})
        doge = data.get("dogecoin", {})
        ada = data.get("cardano", {})
        avax = data.get("avalanche-2", {})
        dot = data.get("polkadot", {})

        btc_usd, btc_chg = btc.get("usd", 0), btc.get("usd_24h_change", 0.0)
        eth_usd, eth_chg = eth.get("usd", 0), eth.get("usd_24h_change", 0.0)
        sol_usd, sol_chg = sol.get("usd", 0), sol.get("usd_24h_change", 0.0)
        bnb_usd, bnb_chg = bnb.get("usd", 0), bnb.get("usd_24h_change", 0.0)
        usdt_usd, usdt_chg = usdt.get("usd", 1.0), usdt.get("usd_24h_change", 0.0)

        xrp_usd, xrp_chg = xrp.get("usd", 0), xrp.get("usd_24h_change", 0.0)
        doge_usd, doge_chg = doge.get("usd", 0), doge.get("usd_24h_change", 0.0)
        ada_usd, ada_chg = ada.get("usd", 0), ada.get("usd_24h_change", 0.0)
        avax_usd, avax_chg = avax.get("usd", 0), avax.get("usd_24h_change", 0.0)
        dot_usd, dot_chg = dot.get("usd", 0), dot.get("usd_24h_change", 0.0)

        usd_idr = int(btc.get("idr", 0) / btc_usd) if btc_usd else 16200

        # Rotate Page 3 altcoins every 2 seconds
        self.p3_index = int(now // 2) % len(ALTCOINS_P3)
        alt_id, alt_symbol = ALTCOINS_P3[self.p3_index]
        alt_data = data.get(alt_id, {})
        alt_usd = alt_data.get("usd", 0.0)
        alt_chg = alt_data.get("usd_24h_change", 0.0)

        # Format price for p3 clean size 1 text
        if alt_usd < 0.001:
            p3_price_str = f"${alt_usd:.6f}"
        elif alt_usd < 1.0:
            p3_price_str = f"${alt_usd:.3f}"
        else:
            p3_price_str = f"${alt_usd:,.2f}"

        p3_line2_str = f"Harga: {p3_price_str}"
        p3_line3_str = f"24h: {alt_chg:+.1f}%  [{self.p3_index+1:02d}/10]"

        return {
            "source": self.DISPLAY_NAME,
            "custom": {
                # Halaman 1: Top 5 Cryptos (BTC, ETH, SOL, BNB, USDT)
                "hdr": f"CRYPTO (1/3) | Rp{usd_idr:,}",
                "l1": f"BTC : ${btc_usd:,.0f} ({btc_chg:+.1f}%)",
                "l2": f"ETH : ${eth_usd:,.0f} ({eth_chg:+.1f}%)",
                "l3": f"SOL : ${sol_usd:,.1f} ({sol_chg:+.1f}%)",
                "l4": f"BNB : ${bnb_usd:,.1f} ({bnb_chg:+.1f}%)",
                "l5": f"USDT: ${usdt_usd:,.3f} ({usdt_chg:+.1f}%)",
                # Halaman 2: Altcoins (XRP, DOGE, ADA, AVAX, DOT)
                "p2_hdr": f"CRYPTO (2/3) | Rp{usd_idr:,}",
                "p2_l1": f"XRP : ${xrp_usd:,.3f} ({xrp_chg:+.1f}%)",
                "p2_l2": f"DOGE: ${doge_usd:,.3f} ({doge_chg:+.1f}%)",
                "p2_l3": f"ADA : ${ada_usd:,.3f} ({ada_chg:+.1f}%)",
                "p2_l4": f"AVAX: ${avax_usd:,.1f} ({avax_chg:+.1f}%)",
                "p2_l5": f"DOT : ${dot_usd:,.2f} ({dot_chg:+.1f}%)",
                # Halaman 3: Animasi Carousel Altcoins Clean Size 1
                "p3_hdr": f"CRYPTO (3/3) | ALTCOINS",
                "p3_l1": f"{alt_symbol}/USD",
                "p3_l2": p3_line2_str,
                "p3_l3": p3_line3_str,
            },
            "plan": "Crypto",
            "model": f"BTC ${btc_usd:,.0f}",
            "effort": f"{btc_chg:+.1f}% 24h",
            "context_used": int(btc_usd),
            "context_max": 100000,
            "context_pct": 50,
            "limit_5h_pct": 50,
            "limit_5h_mins": 300,
            "limit_week_pct": 50,
            "limit_week_mins": 4320,
            "cost": float(btc_usd),
            "input": int(eth_usd),
            "output": int(sol_usd),
            "requests": int(usd_idr // 100),
            "project": f"1USD=Rp{usd_idr:,}",
            "credit": float(eth_usd),
            "models": [
                {"model": f"BTC ${btc_usd:,.0f}", "cost": 0.0, "pct": 50},
                {"model": f"ETH ${eth_usd:,.0f}", "cost": 0.0, "pct": 50},
            ],
        }
