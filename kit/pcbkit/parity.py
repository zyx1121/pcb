"""The board against the schematic's netlist, both ways: references, footprints, the net of every pad, values.

A netlist net with one node ("unconnected-(...)") counts as no net. References that start with a prefix in
board_only (mounting holes by default) may exist on the board alone.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from . import kicad


def read_netlist(path: Path):
    root = ET.parse(path).getroot()
    comps = {c.get("ref"): ((c.findtext("footprint") or "").split(":")[-1], c.findtext("value") or "")
             for c in root.iter("comp")}
    pads = {}
    for n in root.iter("net"):
        nodes = list(n.iter("node"))
        name = "" if len(nodes) < 2 or n.get("name", "").startswith("unconnected-") else n.get("name")
        for node in nodes:
            pads[(node.get("ref"), node.get("pin"))] = name
    return comps, pads


def check(pcb: Path, netlist: Path, board_only: list[str]) -> list[str]:
    board = kicad.load(pcb)
    comps, want = read_netlist(netlist)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    bad = [f"in the netlist only: {r}" for r in sorted(set(comps) - set(fps))]
    bad += [f"on the board only: {r}" for r in sorted(set(fps) - set(comps))
            if not any(r.startswith(p) for p in board_only)]
    seen = set()
    for ref, fp in sorted(fps.items()):
        if ref not in comps:
            continue
        name, value = comps[ref]
        have_name = str(fp.GetFPID().GetLibItemName())
        if have_name != name:
            bad.append(f"{ref} footprint: board {have_name}, netlist {name}")
        if fp.GetValue() != value:
            bad.append(f"{ref} value: board '{fp.GetValue()}', netlist '{value}'")
        for p in fp.Pads():
            num = p.GetNumber()
            if not num:
                continue
            have = p.GetNetname()
            have = "" if have.startswith("unconnected-") else have
            exp = want.get((ref, num), "")
            seen.add((ref, num))
            if have != exp:
                bad.append(f"{ref} pad {num}: board '{have}', netlist '{exp}'")
    for ref, num in sorted(set(want) - seen):
        if ref in fps:
            bad.append(f"{ref} pad {num} is in the netlist, the footprint has no such pad")
    return bad
