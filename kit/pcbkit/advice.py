"""Second opinions: findings to read, never a reason to fail the gate.

  druid  DRC on a copy of the board with kicad-druid's JLCPCB rules (vendor/kicad-druid) for its copper
         layer count, instead of the project's rules. Shows what the fab's own limits would flag.
  happy  kicad-happy's offline analyzers on the schematic and the board: missing decoupling, power tree,
         fiducials, thermal vias, voltage domains. Its errors and warnings only; it is noisy, so waive the
         false ones in pcb.toml with a reason.

bin/pcbkit downloads kicad-happy at a pinned commit and passes its folder in PCBKIT_HAPPY.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import kicad
from .config import Config

VENDOR = Path(__file__).parent / "vendor" / "kicad-druid"


def druid(cfg: Config) -> list[str]:
    layers = kicad.load(cfg.pcb).GetCopperLayerCount()
    rules = {2: "JLCPCB-2L-1oz", 4: "JLCPCB-4L-2oz", 6: "JLCPCB-6L-1oz"}.get(layers)
    if not rules:
        return [f"no kicad-druid JLCPCB rules for {layers} copper layers"]
    with tempfile.TemporaryDirectory(prefix="pcbkit-druid-") as tmp:
        t = Path(tmp)
        shutil.copy(cfg.pcb, t / "d.kicad_pcb")
        pro = cfg.pcb.with_suffix(".kicad_pro")
        if pro.exists():
            shutil.copy(pro, t / "d.kicad_pro")
        shutil.copy(VENDOR / f"{rules}.kicad_dru", t / "d.kicad_dru")
        rep = kicad.drc(t / "d.kicad_pcb", t / "drc.json", refill=False)
    seen, out = set(), []
    for v in rep.get("violations", []):
        if "JLCPCB" not in v.get("description", ""):
            continue  # the board's own checks; the drc gate covers those
        items = ", ".join(i.get("description", "")[:60] for i in v.get("items", []))
        line = f"{v.get('severity')} {v.get('description')}: {items}"
        if line not in seen:
            seen.add(line)
            out.append(line)
    return out


def happy(cfg: Config) -> list[str]:
    root = os.environ.get("PCBKIT_HAPPY")
    if not root or not Path(root).is_dir():
        return ["kicad-happy is not available (run through bin/pcbkit, with network for the first download)"]
    scripts = Path(root) / "skills" / "kicad" / "scripts"
    jobs = [("analyze_pcb.py", cfg.pcb)]
    if cfg.schematic and cfg.schematic.exists():
        jobs.insert(0, ("analyze_schematic.py", cfg.schematic))
    out = []
    with tempfile.TemporaryDirectory(prefix="pcbkit-happy-") as tmp:
        for script, src in jobs:
            dest = Path(tmp) / (script + ".json")
            r = subprocess.run(["python3", str(scripts / script), str(src), "--output", str(dest)],
                               capture_output=True, text=True, cwd=cfg.root)
            if r.returncode or not dest.exists():
                out.append(f"{script} failed: {(r.stderr or r.stdout).strip().splitlines()[-1:]}")
                continue
            for f in json.loads(dest.read_text()).get("findings", []):
                if f.get("severity") in ("error", "warning"):
                    out.append(f"{f['severity']} {f.get('rule_id', '')}: {f.get('summary', '')}")
    return out


ADVICE = {"druid": druid, "happy": happy}
