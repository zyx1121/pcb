# Calculations and design checks

One row per check, in a script that exits non-zero on a FAIL:

```
group, item, value, limit, verdict (pass | FAIL | open), source (datasheet + page, or tool), note
```

`open` means not measured yet. A waived FAIL keeps its row and gets a reason in `pcb.toml`.

| Check | Limit | Source |
|---|---|---|
| Capacitor voltage | ≤ 60 % of rated | NASA PD-ED-1201 |
| Resistor power | ≤ 60 % of rated | NASA PD-ED-1201 |
| Semiconductor voltage | ≤ 75 % of rated | NASA PD-ED-1201 |
| Relay coil voltage | between 110 % of must-operate and the maximum coil voltage | the relay datasheet, ECSS-Q-ST-30-11 |
| Coil flyback | a diode (or diode plus Zener) across every coil | netlist |
| Decoupling | at least one 100 nF per supply pin, next to it | netlist + geometry |
| Buck hot loop | input capacitor and diode on the same layer, no vias | the regulator datasheet, TI AN-1229 |
| Strapping pins | the state the datasheet requires at reset, no large capacitor | MCU datasheet |
| Mains clearance | from mains voltage and overvoltage category through IEC 60664-1 table F.2 | TI SLUP419 |
| Mains creepage | from voltage, pollution degree, material group and insulation type | IEC 60664-1 |
| JLC minimums | 2-layer 1 oz: 0.10 mm track and gap, 0.20 mm annular ring, 1.0 mm slot, 1.0 mm silkscreen height | jlcpcb.com capabilities |

Read the numbers from the part's own datasheet, not from a similar part.

kicad-happy (github.com/aklofas/kicad-happy, MIT) is a useful second opinion: `analyze_schematic.py` and `analyze_pcb.py` run offline and flag missing decoupling, power-tree problems and missing fiducials. Treat its output as a list to read, not a gate: on a 141-part board it raised 128 findings, most of them noise.
