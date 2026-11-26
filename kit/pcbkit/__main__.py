"""pcbkit: headless KiCad checks and fabrication outputs, configured by pcb.toml.

    python3 -m pcbkit gate [names...]      run the gates (all, or the ones named)
    python3 -m pcbkit fab                  Gerber zip, JLCPCB BOM and CPL into [fab] out
    python3 -m pcbkit jlc                  the BOM against JLCPCB's library
    python3 -m pcbkit datasheets [dir]     download every BOM part's datasheet (default datasheets/)
    python3 -m pcbkit lint-rules FILE...   lint .kicad_dru files (no KiCad needed)
    python3 -m pcbkit search KEYWORD       search JLCPCB's parts

Options: -c/--config PATH (default ./pcb.toml).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pcbkit", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default="pcb.toml")
    ap.add_argument("command", choices=["gate", "fab", "jlc", "datasheets", "lint-rules", "search"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args(argv)

    if a.command == "lint-rules":
        from .rules import lint

        n = 0
        for f in a.args:
            for p in lint(Path(f)):
                print(f"{f}:{p}")
                n += 1
        return 1 if n else 0
    if a.command == "search":
        from .jlc import kind, search

        for p in search(" ".join(a.args), 20):
            print(f"{p.get('componentCode'):>10}  {kind(p):9}  stock {int(p.get('stockCount') or 0):>9}  "
                  f"{p.get('componentSpecificationEn', '')[:14]:14}  {p.get('componentModelEn', '')}  {p.get('describe', '')[:60]}")
        return 0

    from .config import load

    cfg = load(a.config)
    if a.command == "gate":
        from .gate import run

        return run(cfg, a.args or None)
    if a.command == "fab":
        from .fab import run

        for line in run(cfg):
            print(line)
        return 0
    if a.command == "jlc":
        from .jlc import check

        bad, notes = check(cfg)
        for n in notes:
            print("  ." if not n.startswith("lines") else "", n)
        for b in bad:
            print("FAIL", b)
        return 1 if bad else 0
    if a.command == "datasheets":
        from .fab import parts
        from .jlc import datasheet

        folder = cfg.root / (a.args[0] if a.args else "datasheets")
        codes = sorted({p["lcsc"] for p in parts(cfg.netlist).values() if p["lcsc"] and not p["skip"]})
        missing = [c for c in codes if not datasheet(c, folder)]
        print(f"datasheets: {len(codes) - len(missing)} of {len(codes)} in {folder}")
        for c in missing:
            print("  none for", c)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
