"""
Registry sumber data token.

Menambah IDE / AI baru:
    1. bikin sources/<nama>.py, contek pola di claude_code.py
    2. daftarkan di _REGISTRY di bawah
    3. (opsional) bikin profil OLED-nya di include/profiles/<nama>.h
"""

from sources import (
    claude_code,
    antigravity,
    sysmon,
    crypto,
    weather,
    spotify,
    pomodoro,
    github,
    network,
    stocks,
    todo,
    companion,
    visualizer,
    thermals,
    calendar,
    docker,
    worldclock,
)

_REGISTRY = {
    claude_code.NAME: claude_code.Source,
    antigravity.NAME: antigravity.Source,
    sysmon.NAME: sysmon.Source,
    crypto.NAME: crypto.Source,
    weather.NAME: weather.Source,
    spotify.NAME: spotify.Source,
    pomodoro.NAME: pomodoro.Source,
    github.NAME: github.Source,
    network.NAME: network.Source,
    stocks.NAME: stocks.Source,
    todo.NAME: todo.Source,
    companion.NAME: companion.Source,
    visualizer.NAME: visualizer.Source,
    thermals.NAME: thermals.Source,
    calendar.NAME: calendar.Source,
    docker.NAME: docker.Source,
    worldclock.NAME: worldclock.Source,
}


def available_sources():
    return sorted(_REGISTRY)


def get_source(name, **kwargs):
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise SystemExit(
            f"[FATAL] Sumber '{name}' tidak dikenal. "
            f"Pilihan: {', '.join(available_sources())}"
        )
    return cls(**kwargs)

