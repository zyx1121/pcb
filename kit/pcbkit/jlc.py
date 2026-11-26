"""JLCPCB parts: the BOM against JLCPCB's live library, and datasheets from LCSC.

The search endpoint is the one jlcpcb.com's own parts page calls. It is undocumented and needs no login;
answers are cached in .pcbkit/jlc/ for a day. Fields used:

  componentLibraryType  "base" = Basic part (no loading fee), "expand" = Extended
  preferredComponentFlag  true with "expand" = Preferred Extended (no fee on Economic assembly)
  stockCount, componentSpecificationEn (package), dataManualUrl (datasheet), componentModelEn (MPN)
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

from .config import Config
from .fab import parts

SEARCH = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
UA = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"}
PASSIVE = re.compile(r"^(R|C|L|RN)\d")
CHIP = re.compile(r"\b(0201|0402|0603|0805|1206|1210|2010|2512)\b")


def search(keyword: str, size: int = 10) -> list[dict]:
    body = json.dumps({"currentPage": 1, "pageSize": size, "keyword": keyword, "searchSource": "search"}).encode()
    req = urllib.request.Request(SEARCH, data=body, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return ((data.get("data") or {}).get("componentPageInfo") or {}).get("list") or []


def part(code: str, cache: Path) -> dict | None:
    """One LCSC number, from the cache when it is under a day old."""
    f = cache / f"{code}.json"
    if f.exists() and time.time() - f.stat().st_mtime < 86400:
        return json.loads(f.read_text()) or None
    hit = next((p for p in search(code, 5) if p.get("componentCode") == code), None)
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(hit or {}))
    return hit


def kind(p: dict) -> str:
    if p.get("componentLibraryType") == "base":
        return "basic"
    return "preferred" if p.get("preferredComponentFlag") else "extended"


def check(cfg: Config) -> tuple[list[str], list[str]]:
    """Problems that block an order, and notes. Uses the netlist's LCSC field."""
    cache = cfg.root / ".pcbkit" / "jlc"
    lines: dict[str, list[str]] = {}
    fps: dict[str, str] = {}
    for ref, p in parts(cfg.netlist).items():
        if p["skip"] or ref in cfg.hand or any(ref.startswith(b) for b in cfg.board_only):
            continue
        if not p["lcsc"]:
            lines.setdefault("", []).append(ref)
            continue
        lines.setdefault(p["lcsc"], []).append(ref)
        fps[p["lcsc"]] = p["footprint"]
    bad, notes = [], []
    if "" in lines:
        bad.append("no LCSC number: " + ", ".join(sorted(lines.pop(""))))
    counts = {"basic": 0, "preferred": 0, "extended": 0}
    for code, refs in sorted(lines.items()):
        p = part(code, cache)
        if not p:
            bad.append(f"{code} ({', '.join(refs)}): not in JLCPCB's library")
            continue
        k = kind(p)
        counts[k] += 1
        need = len(refs) * cfg.quantity
        stock = int(p.get("stockCount") or 0)
        pkg = p.get("componentSpecificationEn") or ""
        tag = f"{code} {p.get('componentModelEn', '')} [{pkg}, {k}, stock {stock}] {', '.join(refs)}"
        if stock < need:
            bad.append(f"{tag}: stock below the {need} needed")
        size = CHIP.search(pkg)
        if cfg.passives_basic and k != "basic" and size and all(PASSIVE.match(r) for r in refs):
            bad.append(f"{tag}: a chip passive that is not a Basic part (loading fee); use a Basic value or combine two")
        if size and size.group(1) not in fps.get(code, ""):
            notes.append(f"{tag}: package {size.group(1)} but footprint {fps[code]}")
        if k == "extended":
            notes.append(f"{tag}: extended")
    notes.insert(0, "lines: {basic} basic, {preferred} preferred extended, {extended} extended".format(**counts))
    return bad, notes


def datasheet(code: str, folder: Path) -> Path | None:
    """Save the datasheet PDF of one LCSC number as folder/<code>.pdf. LCSC's datasheet link answers with an
    HTML page; the PDF is the datasheet.lcsc.com link inside it."""
    out = folder / f"{code}.pdf"
    if out.exists() and out.stat().st_size > 1000:
        return out
    p = part(code, folder.parent / ".pcbkit" / "jlc") or {}
    url = p.get("dataManualUrl")
    if not url:
        return None
    for _ in range(2):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        if body[:4] == b"%PDF":
            folder.mkdir(parents=True, exist_ok=True)
            out.write_bytes(body)
            return out
        m = re.search(rb"https?://[^\"'\s]*datasheet\.lcsc\.com/[^\"'\s]+\.pdf", body)
        if not m:
            return None
        url = m.group(0).decode()
    return None
