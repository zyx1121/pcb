"""Route lint: what KiCad's DRC cannot tell apart.

KiCad's track_angle rule sees a T branch and a right-angle bend alike, so it can only reject acute angles.
This walks every track node and reports:

  bend90   a node where exactly two tracks meet at 90 degrees or less, away from a pad or via
  short    a track segment (or arc) shorter than short_mm: the jogs an autorouter leaves
  corners  how many corners each net turns, worst first (fewer is a cleaner route)

Positions are in mm from the board's aux origin (the fabrication origin), y down as in KiCad.
"""
from __future__ import annotations

import math
from pathlib import Path

from . import kicad


def check(pcb: Path, short_mm: float = 0.5) -> tuple[list[str], dict[str, int]]:
    p = kicad.pcbnew()
    board = kicad.load(pcb)
    org = board.GetDesignSettings().GetAuxOrigin()
    ox, oy = p.ToMM(org.x), p.ToMM(org.y)
    R = lambda v: round(p.ToMM(v), 3)  # noqa: E731
    nodes: dict = {}
    segs = []
    anchors = set()
    for tr in board.GetTracks():
        if tr.GetClass() == "PCB_VIA":
            q = tr.GetPosition()
            anchors.add((R(q.x), R(q.y), tr.GetNetname()))
            continue
        a, b = tr.GetStart(), tr.GetEnd()
        s = ((R(a.x), R(a.y)), (R(b.x), R(b.y)), tr.GetLayer(), tr.GetNetname())
        if tr.GetClass() == "PCB_ARC":
            # an arc leaves each end along its tangent; its length is radius x angle
            c, m = tr.GetCenter(), tr.GetMid()
            c, m = (R(c.x), R(c.y)), (R(m.x), R(m.y))
            for e in (s[0], s[1]):
                t = (-(e[1] - c[1]), e[0] - c[0])
                if t[0] * (m[0] - e[0]) + t[1] * (m[1] - e[1]) < 0:
                    t = (-t[0], -t[1])
                nodes.setdefault((e, s[2], s[3]), []).append((e[0] + t[0], e[1] + t[1]))
            if p.ToMM(tr.GetRadius()) * abs(tr.GetAngle().AsRadians()) < short_mm:
                segs.append(s)
            continue
        segs.append(s)
        for u, v in ((s[0], s[1]), (s[1], s[0])):
            nodes.setdefault((u, s[2], s[3]), []).append(v)
    pads = [(pad.GetNetname(), pad) for fp in board.GetFootprints() for pad in fp.Pads()]

    def on_pad(q, layer, net):
        v = p.VECTOR2I(p.FromMM(q[0]), p.FromMM(q[1]))
        return (q[0], q[1], net) in anchors or any(
            n == net and pad.IsOnLayer(layer) and pad.HitTest(v) for n, pad in pads)

    found, corners = [], {}
    for (q, layer, net), others in nodes.items():
        if len(others) != 2 or on_pad(q, layer, net):
            continue
        v1 = (others[0][0] - q[0], others[0][1] - q[1])
        v2 = (others[1][0] - q[0], others[1][1] - q[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        if l1 == 0 or l2 == 0:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)))))
        if ang < 179.0:
            corners[net] = corners.get(net, 0) + 1
        if ang < 91.0:
            found.append(f"bend90 {net} {q[0] - ox:.2f} {q[1] - oy:.2f} {board.GetLayerName(layer)} {ang:.0f} deg")
    for s in segs:
        d = math.dist(s[0], s[1])
        if d < short_mm:
            found.append(f"short {s[3]} {s[0][0] - ox:.2f} {s[0][1] - oy:.2f} {d:.3f} mm")
    return found, dict(sorted(corners.items(), key=lambda kv: -kv[1]))
