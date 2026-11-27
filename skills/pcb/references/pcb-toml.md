# pcb.toml

One file per board, next to the project. Paths are relative to it. Only `[board] pcb` is required.

```toml
[board]
pcb = "kicad/board.kicad_pcb"
netlist = "kicad/board.net.xml"        # kicad-cli sch export netlist --format kicadxml
schematic = "kicad/board.kicad_sch"
board_only = ["H"]                      # reference prefixes allowed on the board only

[rules]
file = "kicad/board.kicad_dru"          # default: the board's name with .kicad_dru

[route]
short_mm = 0.5

[fab]
out = "fab"
hand = ["SW4"]                          # soldered by hand: left out of BOM and CPL
split = { F1 = [["F1A", "1"], ["F1B", "2"]] }   # one footprint, two placed parts, by pad
rotate = [["^SOT-223", 180]]  # optional: degrees added per LCSC number or footprint pattern. Order: an LCSC entry,
                              # then the angle from the part's EasyEDA footprint (what JLCPCB's preview uses), then a
                              # footprint entry. The jlc gate fails where an LCSC entry disagrees with EasyEDA.
sides = ["Top"]               # sides JLCPCB assembles; the jlc gate fails on a placed part on another side

[jlc]
quantity = 5                            # boards to assemble; stock must cover parts x quantity
passives_basic = true                   # fail on a resistor or capacitor that is not a Basic part

[gate]
run = ["rules", "drc", "parity", "route", "jlc"]
advise = ["druid", "happy"]                 # never fail the gate; the default

[[gate.command]]                        # a project check; fails on a non-zero exit
name = "positive-control"
run = "python3 tools/test_drc_rules.py"

[[waive]]                               # turns one finding into a note; the reason prints every run
gate = "route"
match = "short /USB_D"
reason = "USB pad exits, hand-routed later"
```

Commands, from the folder that holds `pcb.toml`:

```
bin/pcbkit gate [names]     all gates, or the ones named
bin/pcbkit fab              Gerber zip, bom-jlc.csv, cpl-jlc.csv in [fab] out
bin/pcbkit jlc              the BOM against JLCPCB's library
bin/pcbkit datasheets       every BOM part's datasheet into datasheets/
bin/pcbkit lint-rules F     lint a .kicad_dru (no KiCad needed)
bin/pcbkit search 10k 0603  search JLCPCB's parts
bin/pcbkit freeroute in.dsn out.ses [options]   Freerouting 2.6.0 in a Java 25 container
```

Set `DOCKER="sudo -n docker"` when the user is not in the docker group. Inside a KiCad container (CI), `bin/pcbkit` runs Python directly.
