"""The one place that talks to KiCad: the pcbnew module and kicad-cli.

pcbnew is KiCad's SWIG binding. KiCad 10 ships it; KiCad 11 removes it in favour of the IPC API (kipy and
`kicad-cli api-server`). Keep every pcbnew call behind this module or in the checks that import it lazily,
so the move to 11 touches one package.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or "kicad-cli"


def pcbnew():
    import pcbnew as p  # noqa: PLC0415  (imported late: the pure checks run without KiCad)

    return p


def load(path: Path):
    return pcbnew().LoadBoard(str(path))


def mm(v: int) -> float:
    return pcbnew().ToMM(v)


def cli(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run kicad-cli. Its stdout and stderr carry wx image-handler noise; callers read files, not text."""
    return subprocess.run([CLI, *args], capture_output=True, text=True, check=check)


def version() -> str:
    return cli("version").stdout.strip()


def drc(pcb: Path, report: Path, refill: bool = True) -> dict:
    """Run DRC and return the JSON report. kicad-cli exits 0 even when the rules file failed to load, so the
    exit code says nothing: rules.sentinel() is how a gate knows the rules ran."""
    args = ["pcb", "drc", str(pcb), "-o", str(report), "--format", "json", "--severity-all"]
    if refill:
        args.append("--refill-zones")
    cli(*args)
    return json.loads(report.read_text(encoding="utf-8"))
