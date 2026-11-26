# pcb

Claude Code and Codex plugin for KiCad PCB work: a skill (`skills/pcb/`) for the design order, `pcbkit` (a Python package in `kit/` that runs inside the pinned KiCad image) for the gates and fabrication files, and a Bun MCP server (`src/`, bundled to `dist/server.js`) for JLCPCB parts and datasheets. Read [README.md](README.md) first.

## Layout

- `skills/pcb/`: the skill and its references. Generic only: no project names, voltages or part numbers from one board.
- `kit/pcbkit/`: the checks. `kicad.py` is the only module that imports `pcbnew` directly or runs `kicad-cli`; the others reach KiCad through it.
- `bin/pcbkit`: runs `python3 -m pcbkit` in `kicad/kicad:10.0.8`, or directly when `pcbnew` imports.
- `src/`: the MCP server. `src/jlc.ts` mirrors `kit/pcbkit/jlc.py`; change both together.

## Rules

- The KiCad image tag lives in `bin/pcbkit` and `.github/workflows/check.yml`. Change both together.
- A gate is judged by what it found, never by a printed summary or a tool's exit code alone. `kicad-cli pcb drc` exits 0 when it dropped the rules file.
- Every lint rule in `rules.py` comes from a case reproduced on the pinned KiCad, with a test in `Sentinel` or `Lint`. Do not add rules from another tool's list without reproducing them (kicad-druid's display-layer rule is wrong on KiCad 10).
- Project constants go in the project's `pcb.toml`, never in pcbkit.
- `plugin.json` and `mcp.json` are the manifest sources. Do not hand-edit the generated `.claude-plugin/plugin.json`, `.mcp.json` or `dist/server.js`.
- Repository documents and code comments are English.

## Where to run things

In Loki's environment, the MacBook is for editing and git only. Run `bun install`, the build, the tests and `bin/pcbkit` on `ssh sandbox` (`DOCKER="sudo -n docker"` there).

## Verify

```sh
bun install --frozen-lockfile
bun run check
docker run --rm -e PYTHONPATH=/k -v "$PWD/kit:/k:ro" -w /k kicad/kicad:10.0.8 python3 -m unittest discover -s tests
```

Then run `bin/pcbkit gate` on a real board and compare with its last known result.

## Release

1. Bump `version` in `package.json`, `plugin.json` and `kit/pcbkit/__init__.py`, run `bun run check`, and commit the regenerated files.
2. Merge the PR. Then pin the new commit in [zyx1121/marketplace](https://github.com/zyx1121/marketplace) (see its AGENTS.md).
