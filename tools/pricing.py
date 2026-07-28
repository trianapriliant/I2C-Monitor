"""
Tabel harga model Claude (USD per 1 juta token).

Sumber: harga API first-party Anthropic.
Cache: write = 1.25x harga input (TTL 5 menit) atau 2x (TTL 1 jam),
       read  = 0.1x harga input.
"""

# (input, output) USD per 1M token
MODEL_PRICING = {
    "claude-fable-5":   (10.00, 50.00),
    "claude-mythos-5":  (10.00, 50.00),
    "claude-opus-5":    (5.00,  25.00),
    "claude-opus-4-8":  (5.00,  25.00),
    "claude-opus-4-7":  (5.00,  25.00),
    "claude-opus-4-6":  (5.00,  25.00),
    "claude-opus-4-5":  (5.00,  25.00),
    "claude-sonnet-5":  (3.00,  15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00,   5.00),
}

# Dipakai kalau model tidak dikenal (mis. model baru rilis).
DEFAULT_PRICING = (5.00, 25.00)

# Ukuran context window per model (token).
CONTEXT_WINDOW = {
    "claude-fable-5":    1_000_000,
    "claude-mythos-5":   1_000_000,
    "claude-opus-5":     1_000_000,
    "claude-opus-4-8":   1_000_000,
    "claude-opus-4-7":   1_000_000,
    "claude-opus-4-6":   1_000_000,
    "claude-sonnet-5":   1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-haiku-4-5":    200_000,
}
DEFAULT_CONTEXT_WINDOW = 1_000_000

# Nama pendek supaya muat di layar 128px.
DISPLAY_NAMES = {
    "claude-fable-5":    "Fable 5",
    "claude-mythos-5":   "Mythos 5",
    "claude-opus-5":     "Opus 5",
    "claude-opus-4-8":   "Opus 4.8",
    "claude-opus-4-7":   "Opus 4.7",
    "claude-opus-4-6":   "Opus 4.6",
    "claude-sonnet-5":   "Sonnet 5",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5":  "Haiku 4.5",
}

# Label effort mengikuti istilah di panel Claude Code.
EFFORT_LABELS = {
    "low":    "Rendah",
    "medium": "Sedang",
    "high":   "Tinggi",
    "xhigh":  "S.Tinggi",
    "max":    "Maks",
}

CACHE_WRITE_5M_MULT = 1.25
CACHE_WRITE_1H_MULT = 2.00
CACHE_READ_MULT = 0.10


def _normalize(model: str) -> str:
    """Buang prefix provider (bedrock 'anthropic.') dan suffix tanggal."""
    if not model:
        return ""
    m = model.strip()
    for prefix in ("anthropic.", "us.anthropic.", "eu.anthropic."):
        if m.startswith(prefix):
            m = m[len(prefix):]
    return m


def _lookup(table, model, default):
    m = _normalize(model)
    if m in table:
        return table[m]
    for known, value in table.items():
        if m.startswith(known):
            return value
    return default


def context_window(model: str) -> int:
    return _lookup(CONTEXT_WINDOW, model, DEFAULT_CONTEXT_WINDOW)


def display_name(model: str) -> str:
    return _lookup(DISPLAY_NAMES, model, _normalize(model) or "?")


def effort_label(effort: str) -> str:
    return EFFORT_LABELS.get((effort or "").lower(), effort or "-")


def price_for(model: str):
    """Kembalikan (harga_input, harga_output) per 1M token."""
    m = _normalize(model)
    if m in MODEL_PRICING:
        return MODEL_PRICING[m]
    # Cocokkan prefix untuk varian bertanggal, mis. claude-haiku-4-5-20251001
    for known, prices in MODEL_PRICING.items():
        if m.startswith(known):
            return prices
    return DEFAULT_PRICING


def cost_for(model: str, usage: dict) -> float:
    """
    Hitung biaya satu request (USD) dari objek `usage` di transcript.

    Field cache_creation dipecah per-TTL kalau tersedia, karena
    write 1 jam dua kali lebih mahal daripada write 5 menit.
    """
    in_price, out_price = price_for(model)

    plain_in = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cache_read = usage.get("cache_read_input_tokens", 0) or 0

    creation = usage.get("cache_creation") or {}
    w5 = creation.get("ephemeral_5m_input_tokens", 0) or 0
    w1h = creation.get("ephemeral_1h_input_tokens", 0) or 0
    if not (w5 or w1h):
        # Transcript lama: hanya ada total, asumsikan TTL 5 menit.
        w5 = usage.get("cache_creation_input_tokens", 0) or 0

    cost = (
        plain_in * in_price
        + w5 * in_price * CACHE_WRITE_5M_MULT
        + w1h * in_price * CACHE_WRITE_1H_MULT
        + cache_read * in_price * CACHE_READ_MULT
        + out * out_price
    ) / 1_000_000

    return cost
