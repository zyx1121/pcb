"""Run the gates in pcb.toml in order and judge each one by what it found, never by a printed summary.

Built-in gates:
  rules   lint the rules file, then prove KiCad loaded it (sentinel)
  drc     DRC with zones refilled: errors and unconnected items fail; warnings are listed
  parity  board against netlist (references, footprints, pad nets, values)
  route   route lint: bend90 and short segments
  jlc     the BOM against JLCPCB's library, and the CPL against the sides assembled and each part's
          EasyEDA footprint (network)
Project commands ([[gate.command]]) fail on a non-zero exit.

Advice ([gate] advise, default druid and happy; see advice.py) runs last and never fails the gate: it lists
what kicad-druid and kicad-happy would change. Waive a false one like any finding, under the advice's name.

A [[waive]] entry with the gate's name and a substring of one finding turns that finding into a note; the
reason is printed every run. A waiver that matches nothing is reported, so stale waivers do not pile up.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import jlc, kicad, parity, route, rules
from .advice import ADVICE
from .config import Config


def g_rules(cfg: Config) -> tuple[list[str], list[str]]:
    if not cfg.rules.exists():
        return [f"no rules file at {cfg.rules}"], []
    bad = [f"{cfg.rules.name}:{p}" for p in rules.lint(cfg.rules)]
    ok, msg = rules.sentinel(cfg.pcb, cfg.rules)
    return (bad if ok else [*bad, msg]), ([msg] if ok else [])


def g_drc(cfg: Config) -> tuple[list[str], list[str]]:
    out = cfg.root / ".pcbkit"
    out.mkdir(exist_ok=True)
    rep = kicad.drc(cfg.pcb, out / "drc.json")
    bad, notes = [], []
    for v in rep.get("violations", []):
        pos = v.get("items", [{}])[0].get("pos", {})
        line = f"{v.get('severity')} {v.get('type')}: {v.get('description')} at {pos.get('x')}, {pos.get('y')}"
        (bad if v.get("severity") == "error" else notes).append(line)
    for v in rep.get("unconnected_items", []):
        bad.append(f"unconnected: {v.get('description')} {[i.get('description') for i in v.get('items', [])]}")
    notes.insert(0, f"{len(rep.get('violations', []))} violations, {len(rep.get('unconnected_items', []))} unconnected")
    return bad, notes


def g_parity(cfg: Config) -> tuple[list[str], list[str]]:
    if not cfg.netlist:
        return ["[board] netlist is not set"], []
    return parity.check(cfg.pcb, cfg.netlist, cfg.board_only), []


def g_route(cfg: Config) -> tuple[list[str], list[str]]:
    found, corners = route.check(cfg.pcb, cfg.short_mm)
    worst = ", ".join(f"{n} {c}" for n, c in list(corners.items())[:8])
    return found, [f"corners per net (worst): {worst}"]


def g_jlc(cfg: Config) -> tuple[list[str], list[str]]:
    bad, notes = jlc.check(cfg)
    from . import fab
    return bad + fab.check(cfg), notes


BUILTIN = {"rules": g_rules, "drc": g_drc, "parity": g_parity, "route": g_route, "jlc": g_jlc}


def g_command(cmd: str, root: Path) -> tuple[list[str], list[str]]:
    r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True)
    tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip() and "image handler" not in ln][-12:]
    return ([f"exit {r.returncode}", *tail] if r.returncode else []), ([] if r.returncode else tail[-3:])


def run(cfg: Config, only: list[str] | None = None) -> int:
    gates = [(g, None) for g in cfg.gates] + [(c.name, c.run) for c in cfg.commands]
    if only:
        gates = [g for g in gates if g[0] in only]
    used: set[int] = set()
    failed = []
    print(f"pcbkit gate: {cfg.pcb.name}, KiCad {kicad.version()}")
    for name, cmd in gates:
        try:
            bad, notes = g_command(cmd, cfg.root) if cmd else BUILTIN[name](cfg)
        except Exception as e:  # a gate that crashes has not passed
            bad, notes = [f"crashed: {type(e).__name__}: {e}"], []
        kept = []
        for line in bad:
            w = cfg.waived(name, line)
            if w:
                used.add(id(w))
                notes.append(f"waived ({w.reason}): {line}")
            else:
                kept.append(line)
        print(f"{'PASS' if not kept else 'FAIL'}  {name}")
        for line in kept[:40]:
            print(f"      {line}")
        if len(kept) > 40:
            print(f"      ... {len(kept) - 40} more")
        for line in notes[:12]:
            print(f"      . {line}")
        if kept:
            failed.append(name)
    for name in [a for a in cfg.advise if not only or a in only]:
        try:
            found = ADVICE[name](cfg)
        except Exception as e:  # advice that crashes is reported, not fatal
            found = [f"crashed: {type(e).__name__}: {e}"]
        kept = []
        for line in found:
            w = cfg.waived(name, line)
            if w:
                used.add(id(w))
            else:
                kept.append(line)
        print(f"ADVICE {name}: {len(kept)} to read" + (f", {len(found) - len(kept)} waived" if len(found) > len(kept) else ""))
        for line in kept[:30]:
            print(f"      {line}")
    for w in cfg.waivers:
        if id(w) not in used and (not only or w.gate in only):
            print(f"      stale waiver: [{w.gate}] '{w.match}' matched nothing")
    print("gate:", "PASS" if not failed else "FAIL " + ", ".join(failed))
    return 1 if failed else 0
