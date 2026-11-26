"""Checks for a custom rules file (.kicad_dru), which KiCad drops without a word when one rule is wrong.

KiCad 10.0.8 `kicad-cli pcb drc` loads a rules file with a mistake as if it were empty: no message, the
board's default clearances take over, the exit code only reflects violations (KiCad issue #25848). Two
layers catch that:

  lint()      reads the text: the mistakes seen so far that make KiCad drop the file or a rule
  sentinel()  copies the board, appends a rule that fires on any board, runs DRC and requires every rule
              name the file defines to be loaded (the sentinel proves the file loaded at all)

A rule whose condition silently never matches (for example 'pad' in lowercase) still loads; lint() is the
only guard for that. A project proves each rule fires with its own positive-control board.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path

from . import kicad

# KiCad 10 custom rule constraints (docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom-design-rules)
CONSTRAINTS = {
    "annular_width", "assertion", "bridged_mask", "clearance", "connection_width", "courtyard_clearance",
    "creepage", "diff_pair_gap", "diff_pair_uncoupled", "disallow", "edge_clearance", "hole_clearance",
    "hole_size", "hole_to_hole", "length", "min_resolved_spokes", "physical_clearance",
    "physical_hole_clearance", "silk_clearance", "skew", "solder_mask_expansion", "solder_paste_abs_margin",
    "solder_paste_rel_margin", "text_height", "text_thickness", "thermal_relief_gap", "thermal_spoke_width",
    "track_angle", "track_segment_length", "track_width", "via_count", "via_dangling", "via_diameter",
    "zone_connection",
}
TYPE_LITERALS = {"track": "Track", "via": "Via", "pad": "Pad", "text": "Text", "graphic": "Graphic", "zone": "Zone"}
SENTINEL = "pcbkit sentinel"


def names(text: str) -> list[str]:
    return re.findall(r'\(rule\s+"([^"]+)"', text) + re.findall(r"\(rule\s+([^\s\"()]+)", text)


def lint(path: Path) -> list[str]:
    """Problems as 'line: message'. Empty when none of the known mistakes is present."""
    text = path.read_text(encoding="utf-8")
    out: list[str] = []
    depth = 0
    for i, line in enumerate(text.splitlines(), 1):
        code = re.sub(r'"[^"]*"', '""', line.split("#", 1)[0]) if not line.lstrip().startswith("#") else ""
        depth += code.count("(") - code.count(")")
        if depth < 0:
            out.append(f"{i}: a ')' closes nothing")
            depth = 0
        for m in re.finditer(r"\(constraint\s+([a-z_]+)", line):
            if m.group(1) not in CONSTRAINTS:
                out.append(f"{i}: unknown constraint '{m.group(1)}': KiCad drops the whole file")
        if re.search(r"\(\s*(min|max|opt)\s+-?[\d.]+\s*deg\b", line):
            out.append(f"{i}: an angle with a 'deg' unit: KiCad drops the whole file; write the bare number")
        if re.search(r"\b[AB]\.Parent\.", line):
            out.append(f"{i}: '.Parent.' in a condition: KiCad drops the whole file; use A.memberOfFootprint('U1')")
        for m in re.finditer(r"\.Type\s*[=!]=\s*'([^']*)'", line):
            if m.group(1) in TYPE_LITERALS:
                out.append(f"{i}: type '{m.group(1)}' never matches; write '{TYPE_LITERALS[m.group(1)]}'")
        if "${" in line:
            out.append(f"{i}: a text variable cannot be resolved in a rule: KiCad drops the whole file")
    if depth:
        out.append(f"end: {depth} unclosed '('")
    if not re.search(r"^\s*\(version\s+1\)", text, re.M):
        out.append("1: no '(version 1)' header")
    seen: set[str] = set()
    for n in names(text):
        if n in seen:
            out.append(f"rule '{n}' is defined twice: the later one wins")
        seen.add(n)
    return out


def sentinel(pcb: Path, rules: Path) -> tuple[bool, str]:
    """Copy the board and its rules to a scratch folder, add a rule that flags every footprint, run DRC.
    True when the sentinel fires, that is when KiCad loaded the file."""
    with tempfile.TemporaryDirectory(prefix="pcbkit-") as tmp:
        t = Path(tmp)
        board = t / "s.kicad_pcb"
        shutil.copy(pcb, board)
        pro = pcb.with_suffix(".kicad_pro")
        if pro.exists():
            shutil.copy(pro, t / "s.kicad_pro")
        for lib in ("fp-lib-table", "sym-lib-table"):
            if (pcb.parent / lib).exists():
                shutil.copy(pcb.parent / lib, t / lib)
        text = rules.read_text(encoding="utf-8").rstrip() + (
            f'\n\n(rule "{SENTINEL}"\n  (severity warning)\n  (constraint disallow footprint))\n')
        (t / "s.kicad_dru").write_text(text, encoding="utf-8")
        report = kicad.drc(board, t / "drc.json", refill=False)
        fired = sum(1 for v in report.get("violations", []) if SENTINEL in json.dumps(v))
        if fired:
            return True, f"rules file loaded (sentinel fired on {fired} footprints)"
        return False, "rules file NOT loaded: KiCad dropped it, DRC ran on board defaults"
