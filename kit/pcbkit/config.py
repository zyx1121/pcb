"""Project settings from pcb.toml.

Every path is relative to the folder that holds pcb.toml. Only [board] pcb is required; the rest has
defaults that suit a two-layer board ordered from JLCPCB.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Waiver:
    gate: str
    match: str
    reason: str


@dataclass
class Command:
    name: str
    run: str


@dataclass
class Config:
    root: Path
    pcb: Path
    netlist: Path | None = None
    schematic: Path | None = None
    rules: Path | None = None
    board_only: list[str] = field(default_factory=lambda: ["H"])
    short_mm: float = 0.5
    fab_out: Path | None = None
    hand: list[str] = field(default_factory=list)
    split: dict[str, list[list[str]]] = field(default_factory=dict)
    rotate: list[tuple[str, float]] = field(default_factory=list)
    quantity: int = 2
    passives_basic: bool = True
    gates: list[str] = field(default_factory=lambda: ["rules", "drc", "parity", "route"])
    commands: list[Command] = field(default_factory=list)
    waivers: list[Waiver] = field(default_factory=list)

    def waived(self, gate: str, line: str) -> Waiver | None:
        return next((w for w in self.waivers if w.gate == gate and w.match in line), None)


def load(path: str | Path = "pcb.toml") -> Config:
    path = Path(path).resolve()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    root = path.parent
    rel = lambda v: (root / v) if v else None  # noqa: E731
    board = data.get("board", {})
    if "pcb" not in board:
        raise SystemExit(f"{path}: [board] pcb is required")
    pcb = root / board["pcb"]
    rules = data.get("rules", {})
    fab = data.get("fab", {})
    jlc = data.get("jlc", {})
    gate = data.get("gate", {})
    return Config(
        root=root,
        pcb=pcb,
        netlist=rel(board.get("netlist")),
        schematic=rel(board.get("schematic")),
        rules=rel(rules.get("file")) or pcb.with_suffix(".kicad_dru"),
        board_only=board.get("board_only", ["H"]),
        short_mm=float(data.get("route", {}).get("short_mm", 0.5)),
        fab_out=rel(fab.get("out", "fab")),
        hand=fab.get("hand", []),
        split=fab.get("split", {}),
        rotate=[(p, float(d)) for p, d in fab.get("rotate", [])],
        quantity=int(jlc.get("quantity", 2)),
        passives_basic=bool(jlc.get("passives_basic", True)),
        gates=gate.get("run", ["rules", "drc", "parity", "route"]),
        commands=[Command(c["name"], c["run"]) for c in gate.get("command", [])],
        waivers=[Waiver(w["gate"], w.get("match", ""), w["reason"]) for w in data.get("waive", [])],
    )
