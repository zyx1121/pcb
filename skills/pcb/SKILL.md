---
name: pcb
description: Design a KiCad PCB with an agent, from parts to a JLCPCB order, in a fixed order with headless gates. Covers picking parts from JLCPCB's library, reading every datasheet, computing ratings before claiming them, placement proposals, routing with Freerouting, DRC and netlist gates, and fabrication files. Use when designing, changing, checking or ordering a PCB, or writing KiCad scripts. Triggers on 'PCB', 'KiCad', 'layout', '擺位', '佈線', 'DRC', 'JLCPCB', '下單打板', 'BOM', 'CPL', '料號', 'datasheet', 'Freerouting', 'gerber'.
---

# PCB

A board is done when the gates pass and the person approved the placement, not when it looks right. Every value on the board comes from a datasheet page or a calculation, never from memory.

Tools in this plugin:

- `bin/pcbkit` runs the checks inside the pinned KiCad image (`kicad/kicad:10.0.8`). Run it on a Linux host with Docker, from the folder that holds `pcb.toml`. See [references/pcb-toml.md](references/pcb-toml.md).
  - It lives in this plugin's folder: `${CLAUDE_PLUGIN_ROOT}/bin/pcbkit`.
  - When the board is on another host, clone the same release there and call that copy: `git clone https://github.com/zyx1121/pcb <dir>`, then `<dir>/bin/pcbkit gate` from the board folder. Only `bin/` and `kit/` are needed; it needs Docker and nothing else.
- MCP tools `jlc_search`, `jlc_part`, `datasheet_fetch` query JLCPCB's parts library and save datasheets.

## Order

Do the steps in this order. A later step never starts on a guess about an earlier one.

1. **Requirements and the original board.** List every function. When the board replaces an existing one, photograph it and compute its key values (currents, voltages, coil ratings) from its parts; copy what works.
2. **Parts.** Pick each part with `jlc_search`: Basic parts first (no loading fee), enough stock for boards x quantity, the newest small package that fits. Save every datasheet with `datasheet_fetch` and read it to the last page. Put each number you will rely on in a table with its page.
3. **Schematic.** Generate it from a script, run ERC, export the netlist, check pins against a pin table you wrote from the datasheets.
4. **Calculations.** Derating, power, ripple, voltage domains, relay coils, creepage. One row per check: item, value, limit, verdict, source page. A claim like "enough" or "safe" needs its row. See [references/checks.md](references/checks.md).
5. **Placement proposal.** Write the zones, signal directions and connector sides first. Make 2 to 4 candidates, including a different overall direction. Measure each with the same script (route length, crossings, gaps) and render them side by side. The person picks; do not route before that. Include the current placement as a baseline measured the same way. Report pin or net changes apart from placement effects. Survey what nobody asked about (datasheets, assembler rules, safety) as rule and current-state rows, and state any cost first. Try candidates in a separate script that imports the generator's helpers; never edit the production generator to try one. For tidiness, crop the same region of old and new and look at them side by side.
6. **Routing.** Route mains, power and sensitive nets by script or hand. Autoroute the rest with `bin/pcbkit freeroute in.dsn out.ses` (Freerouting 2.6.0, pinned and checksummed), then clean up (finish, tidy short jogs, teardrops). See [references/kicad.md](references/kicad.md).
7. **Gates.** `bin/pcbkit gate`. Every gate is judged by what it found, never by a printed summary. A finding is fixed or waived in `pcb.toml` with a reason; nothing is skipped.
8. **Order.** `bin/pcbkit fab`, then check the CPL in JLCPCB's placement preview part by part, then a two-model review of the whole package. Present the quote options to the person; ordering is their decision.
9. **Bring-up.** Test the board alone on USB or a bench supply before it touches the machine.

## Rules

- Read the datasheet before choosing or swapping a part; a part without a saved datasheet is not chosen.
- Prefer Basic parts. For a passive value that is not Basic, combine two Basic values in series or parallel.
- Repeated circuits use one template, placed in a row on shared alignment lines, with named gap values instead of scattered numbers. Mirror them when the circuit allows. Keep 4 or 5 gap values at most.
- Space connectors evenly and leave room for plugs and wires; the circuit itself may be dense.
- Show each stage to the person as a render or a web page, not a description.
- Run KiCad itself to compare options; do not draw diagrams by hand.
- Do not guess a number. Compute it and say which tool computed it.
- Keep project constants (voltages, parts that are hand-soldered, rotations) in `pcb.toml` or the project's own scripts, never in this skill.

## Gates

`bin/pcbkit gate` runs, in the order of `[gate] run`:

| Gate | Fails on |
|---|---|
| `rules` | a known mistake in the `.kicad_dru` file, or the file not loaded at all (sentinel rule did not fire) |
| `drc` | any DRC error or unconnected item, zones refilled first |
| `parity` | any reference, footprint, pad net or value that differs from the netlist |
| `route` | right-angle bends away from pads, and segments shorter than `short_mm` |
| `jlc` | a part without an LCSC number, not in the library, short of stock, or a non-Basic passive |

Then two advice lists that never fail the gate, to read and act on: `druid` (kicad-druid's JLCPCB rules for the layer count) and `happy` (kicad-happy's schematic and board analyzers: decoupling, power tree, fiducials, thermal vias). Fix what is real; waive what is not, with the reason.

Project commands in `[[gate.command]]` (positive-control board, creepage, calculations) fail on a non-zero exit. Write project checks so they exit non-zero on a finding.

## When KiCad misbehaves

Read [references/kicad.md](references/kicad.md) before writing pcbnew code or a rules file. The worst trap: KiCad 10 drops a rules file with one mistake without a word, and DRC then passes on default clearances. The `rules` gate exists for that.
