"""The part's footprint in the EasyEDA library, which JLCPCB's placement preview uses.

JLCPCB turns each part's EasyEDA footprint by the CPL rotation, so the rotation a part needs is the angle
from its EasyEDA footprint to the KiCad one: compare where pin 1 sits, seen from the middle of the pads.
Checked on 11 parts against the preview (2026-11-27): all matched.

Only pad numbers and positions are kept in the cache. The library is the JLCEDA/EasyEDA official library
(https://easyeda.com, https://lceda.cn).
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from pathlib import Path

URL = "https://easyeda.com/api/products/{}/components?version=6.4.19.5"


def pads(code: str, cache: Path) -> dict[str, tuple[float, float]] | None:
    """Pad number -> centre (EasyEDA units, y down) of the part's footprint; cached for a day."""
    f = cache / f"{code}.json"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        data = json.loads(f.read_text())
    else:
        req = urllib.request.Request(URL.format(code), headers={"User-Agent": "pcbkit"})
        with urllib.request.urlopen(req, timeout=30) as r:
            res = (json.load(r) or {}).get("result") or {}
        shapes = ((res.get("packageDetail") or {}).get("dataStr") or {}).get("shape") or []
        data = {}
        for s in shapes:
            if s.startswith("PAD~"):
                p = s.split("~")
                if len(p) > 8 and p[8] and p[8] not in data:
                    data[p[8]] = [float(p[2]), float(p[3])]
        cache.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))
    return {k: (v[0], v[1]) for k, v in data.items()} or None


def _pin1_angle(p: dict[str, tuple[float, float]]) -> float | None:
    cx = sum(v[0] for v in p.values()) / len(p)
    cy = sum(v[1] for v in p.values()) / len(p)
    x, y = p["1"][0] - cx, p["1"][1] - cy
    if math.hypot(x, y) < 1e-6 * (1 + max(abs(v[0] - cx) + abs(v[1] - cy) for v in p.values())):
        return None
    return math.degrees(math.atan2(-y, x)) % 360  # counter-clockwise, y up


def offset(kicad: dict[str, tuple[float, float]], easy: dict[str, tuple[float, float]]) -> int | None:
    """Degrees (0, 90, 180 or 270) to add to the KiCad rotation, or None when pin 1 cannot tell."""
    keep = [n for n in kicad if n in easy]
    if "1" not in keep or len(keep) < 3:
        return None
    a = _pin1_angle({n: kicad[n] for n in keep})
    b = _pin1_angle({n: easy[n] for n in keep})
    if a is None or b is None:
        return None
    return round((a - b) / 90) * 90 % 360
