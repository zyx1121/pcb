"""Fabrication outputs for JLCPCB: Gerbers and drill files in one zip, the assembly BOM and the CPL.

Everything is measured from the board's aux origin (set it to the bottom-left corner of the outline).

CPL, two differences from KiCad's position file:
- Rotation: JLCPCB's 3D model of a part has its own zero, which can differ between parts in the same
  package. So there is no built-in table: [fab] rotate lists footprint
  name patterns and degrees counter-clockwise, each one checked in the placement preview on cart.jlcpcb.com.
- Position: JLCPCB centres each model on the point. KiCad anchors a through-hole footprint on pin 1, so
  through-hole parts get the centre of their body (the F.Fab outline).

BOM: built from the netlist, one line per value, footprint and LCSC number. References are listed one by one
(JLCPCB does not read "LED1-LED8"). Parts in [fab] hand, not fitted, excluded from the BOM or position files,
or board-only drop out. [fab] split turns one footprint into several placed parts (a fuse made of two clips).
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from . import kicad
from .config import Config

def fields(comp) -> dict[str, str]:
    out = {f.get("name"): (f.text or "") for f in comp.iter("field")}
    for p in comp.iter("property"):
        out.setdefault(p.get("name"), p.get("value") or "")
    return out


def parts(netlist: Path) -> dict[str, dict]:
    """ref -> value, footprint, lcsc, mpn, dnp from the netlist."""
    out = {}
    for c in ET.parse(netlist).getroot().iter("comp"):
        f = fields(c)
        props = {p.get("name") for p in c.iter("property")}
        out[c.get("ref")] = {
            "value": c.findtext("value") or "",
            "footprint": (c.findtext("footprint") or "").split(":")[-1],
            "lcsc": (f.get("LCSC") or f.get("LCSC Part #") or f.get("JLCPCB") or "").strip(),
            "mpn": (f.get("MPN") or "").strip(),
            "skip": bool(props & {"dnp", "exclude_from_bom", "exclude_from_board"}),
        }
    return out


def cpl_rows(cfg: Config) -> list[list]:
    p = kicad.pcbnew()
    board = kicad.load(cfg.pcb)
    org = board.GetDesignSettings().GetAuxOrigin()
    table = [(re.compile(a), d) for a, d in cfg.rotate]
    rows = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        if ref in cfg.hand or fp.IsDNP() or fp.IsExcludedFromPosFiles() or fp.IsBoardOnly() or not fp.Pads():
            continue
        name = str(fp.GetFPID().GetLibItemName())
        rot = fp.GetOrientationDegrees()
        side = "Bottom" if fp.IsFlipped() else "Top"
        if ref in cfg.split:  # one row per piece, at the middle of that piece's pads
            for piece, pad in cfg.split[ref]:
                ps = [q.GetPosition() for q in fp.Pads() if q.GetNumber() == pad]
                rows.append([piece, sum(q.x for q in ps) / len(ps), sum(q.y for q in ps) / len(ps), side, rot % 360])
            continue
        add = next((d for pat, d in table if pat.search(name)), 0)
        if fp.GetAttributes() & p.FP_THROUGH_HOLE:
            x, y = body_centre(p, fp)
        else:
            x, y = fp.GetPosition().x, fp.GetPosition().y
        rows.append([ref, x, y, side, (rot + add) % 360])
    return [[r, f"{p.ToMM(x - org.x):.4f}mm", f"{p.ToMM(org.y - y):.4f}mm", s, f"{a:.0f}"] for r, x, y, s, a in rows]


def body_centre(p, fp):
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() == p.F_Fab and g.GetClass() != "PCB_TEXT":
            b = g.GetBoundingBox()
            xs += [b.GetX(), b.GetX() + b.GetWidth()]
            ys += [b.GetY(), b.GetY() + b.GetHeight()]
    if not xs:
        c = fp.GetBoundingBox(False, False).GetCenter()
        return c.x, c.y
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def bom_rows(cfg: Config, placed: set[str]) -> tuple[list[list], list[str]]:
    groups: dict[tuple, list[str]] = {}
    for ref, part in parts(cfg.netlist).items():
        pieces = [n for n, _ in cfg.split[ref]] if ref in cfg.split else [ref]
        pieces = [n for n in pieces if n in placed and ref not in cfg.hand and not part["skip"]]
        if pieces:
            groups.setdefault((part["value"], part["footprint"], part["lcsc"]), []).extend(pieces)
    key = lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r) or 0))  # noqa: E731
    rows = [[v, ",".join(sorted(refs, key=key)), fp, lcsc] for (v, fp, lcsc), refs in groups.items()]
    rows.sort(key=lambda r: key(r[1].split(",")[0]))
    missing = [r[1] for r in rows if not r[3]]
    return rows, missing


def copper_layers(cfg: Config) -> list[str]:
    n = kicad.load(cfg.pcb).GetCopperLayerCount()
    return ["F.Cu", *[f"In{i}.Cu" for i in range(1, n - 1)], "B.Cu"]


def run(cfg: Config) -> list[str]:
    out = cfg.fab_out
    gerber = out / "gerber"
    gerber.mkdir(parents=True, exist_ok=True)
    for f in gerber.iterdir():
        f.unlink()
    layers = copper_layers(cfg) + ["F.Paste", "B.Paste", "F.Silkscreen", "B.Silkscreen", "F.Mask", "B.Mask", "Edge.Cuts"]
    kicad.cli("pcb", "export", "gerbers", str(cfg.pcb), "-o", str(gerber), "--layers", ",".join(layers),
              "--use-drill-file-origin")
    kicad.cli("pcb", "export", "drill", str(cfg.pcb), "-o", str(gerber) + "/", "--format", "excellon",
              "--excellon-units", "mm", "--excellon-separate-th", "--drill-origin", "plot",
              "--generate-map", "--map-format", "gerberx2")
    zpath = out / f"{cfg.pcb.stem}-gerber.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(gerber.iterdir()):
            z.write(f, f.name)
    cpl = cpl_rows(cfg)
    with open(out / "cpl-jlc.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(cpl)
    report = [f"gerber: {zpath.name}, {len(list(gerber.iterdir()))} files", f"cpl: {len(cpl)} parts"]
    if cfg.netlist:
        rows, missing = bom_rows(cfg, {r[0] for r in cpl})
        with open(out / "bom-jlc.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, quoting=csv.QUOTE_ALL)
            w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
            w.writerows(rows)
        report.append(f"bom: {len(rows)} lines" + (f", no LCSC number: {'; '.join(missing)}" if missing else ""))
    if cfg.hand:
        report.append("by hand: " + ", ".join(cfg.hand))
    return report
