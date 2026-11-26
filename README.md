<div align="center">

<h1>pcb</h1>

<p><strong>KiCad PCB design for agents: a fixed design order, headless gates in a pinned KiCad container, and JLCPCB parts through MCP.</strong></p>

[![CI](https://img.shields.io/github/actions/workflow/status/zyx1121/pcb/check.yml?branch=main&style=flat-square&label=CI)](https://github.com/zyx1121/pcb/actions)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin-D97757?style=flat-square)](https://github.com/zyx1121/marketplace)
[![License](https://img.shields.io/github/license/zyx1121/pcb?style=flat-square)](LICENSE)

**English** | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

</div>

```console
$ bin/pcbkit gate
pcbkit gate: board.kicad_pcb, KiCad 10.0.8
PASS  rules
      . rules file loaded (sentinel fired on 141 footprints)
PASS  drc
      . 7 violations, 0 unconnected
PASS  parity
FAIL  route
      bend90 +3V3 51.60 -17.26 F.Cu 90 deg
gate: FAIL route
```

KiCad 10 drops a custom rules file with a single mistake and says nothing: DRC passes on default clearances, and the exit code is 0. An agent that reads "0 errors" ships a board that was never checked. pcbkit proves the rules loaded, compares the board with the schematic pad by pad, and judges every gate by what it found.

## Features

- **Rules that provably ran**: lints the `.kicad_dru` for the mistakes that make KiCad drop it, then runs DRC on a copy with a sentinel rule that must fire.
- **Board against schematic**: every reference, footprint, pad net and value, both ways.
- **Route lint**: right-angle bends and autorouter jogs that DRC cannot tell from a T junction.
- **JLCPCB ready**: Gerber zip, BOM and CPL with rotation fixes and through-hole centres; the BOM checked against JLCPCB's live library (Basic or Extended, stock).
- **Datasheets first**: MCP tools search parts and save each datasheet PDF, so values come from a page, not memory.
- **Second opinions**: kicad-druid's JLCPCB rules and kicad-happy's analyzers run as advice after the gates, listed but never failing.
- **One config per board**: `pcb.toml` holds the project's choices and waivers, each with a reason.

## Quick start

```sh
claude plugin marketplace add zyx1121/marketplace
claude plugin install pcb@zyx1121
```

Codex: `codex plugin marketplace add zyx1121/marketplace`, then `codex plugin add pcb@zyx1121`.

The MCP server needs Bun. `bin/pcbkit` needs Docker on a Linux host. Put a `pcb.toml` next to the board (see [skills/pcb/references/pcb-toml.md](skills/pcb/references/pcb-toml.md)), then run `bin/pcbkit gate` from that folder.

## Usage

| Command or tool | Does |
|---|---|
| `bin/pcbkit gate [names]` | runs the gates: `rules`, `drc`, `parity`, `route`, `jlc`, plus project commands |
| `bin/pcbkit fab` | writes the Gerber zip, `bom-jlc.csv` and `cpl-jlc.csv` |
| `bin/pcbkit jlc` | checks the BOM against JLCPCB's library |
| `bin/pcbkit datasheets` | saves every BOM part's datasheet into `datasheets/` |
| `bin/pcbkit lint-rules FILE` | lints a `.kicad_dru` without KiCad |
| `bin/pcbkit freeroute IN OUT` | autoroutes a DSN with Freerouting 2.6.0 (pinned, checksummed) |
| MCP `jlc_search` | searches JLCPCB's parts by keyword or value |
| MCP `jlc_part` | looks up LCSC codes: kind, stock, package, prices |
| MCP `datasheet_fetch` | saves one part's datasheet PDF |

The skill `pcb` sets the order: requirements, parts and datasheets, schematic, calculations, placement proposal, routing, gates, order, bring-up.

## Configuration

| Variable | Sets | Default |
|---|---|---|
| `PCBKIT_IMAGE` | the KiCad image | `kicad/kicad:10.0.8` |
| `DOCKER` | the docker command | `docker` |

## How it works

- `bin/pcbkit` mounts the project and `kit/` into the KiCad image and runs `python3 -m pcbkit`. Inside a KiCad container it runs Python directly.
- The `rules` gate appends `(rule "pcbkit sentinel" (constraint disallow footprint))` to a copy of the rules file. If no sentinel violation comes back, KiCad dropped the file.
- JLCPCB lookups use the search endpoint that jlcpcb.com's parts page calls; answers are cached for a day in `.pcbkit/jlc/`.
- pcbnew (SWIG) is removed in KiCad 11. Only `kit/pcbkit/kicad.py` and a few checks touch it, so the move to the IPC API is one change.

## Limits

- The JLCPCB endpoint is undocumented and may change.
- Placement and routing quality need a person's eye; the skill asks for renders and a choice before routing.
- Calculations (derating, creepage, coil voltage) stay in each project's own scripts, run as `[[gate.command]]`.

## For AI agents

Facts for coding agents and LLM tools. The rules for changing the code are in [AGENTS.md](AGENTS.md).

- **Summary**: Claude Code and Codex plugin with a PCB design skill, headless KiCad gates (`bin/pcbkit`) and 3 MCP tools for JLCPCB parts and datasheets.
- **Type**: plugin
- **Interfaces**: skill `pcb`; MCP `pcb` (stdio, `dist/server.js`); CLI `bin/pcbkit`
- **Install**: `claude plugin install pcb@zyx1121`, after `claude plugin marketplace add zyx1121/marketplace`
- **Run**: `bin/pcbkit gate` in a folder with `pcb.toml`
- **Verify**: `jlc_part` with `["C25804"]`; expect `kind` `basic`
- **Config**: `pcb.toml`, `PCBKIT_IMAGE`, `DOCKER`
- **Secrets**: none
- **Limits**: Docker on Linux for `bin/pcbkit`; KiCad 10.0.x

## Development

```sh
bun install --frozen-lockfile
bun run check
docker run --rm -e PYTHONPATH=/k -v "$PWD/kit:/k:ro" -w /k kicad/kicad:10.0.8 python3 -m unittest discover -s tests
```

## Credits

- [kicad-druid](https://github.com/Cimos/kicad-druid) (MIT): the JLCPCB rules files in `kit/pcbkit/vendor/kicad-druid/`.
- [kicad-happy](https://github.com/aklofas/kicad-happy) (MIT): downloaded at a pinned commit for the `happy` advice.
- [Freerouting](https://github.com/freerouting/freerouting) (GPL-3.0): downloaded at a pinned version and checksum, not bundled.

## License

[MIT](LICENSE)
