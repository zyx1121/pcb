# KiCad and routing traps

Every entry below cost a board revision or a day. Read before writing pcbnew code, a rules file or a Freerouting run.

## Version

- Use KiCad 10.0.8 or newer 10.0.x. pcbkit pins `kicad/kicad:10.0.8`; change the pin in `bin/pcbkit` only.
- KiCad 11 removes the SWIG `pcbnew` module. Its replacement, the IPC API (`kipy`), needs a running KiCad on 10 and gets a headless `kicad-cli api-server` only in 11. Keep pcbnew calls in a few modules so the move is one change.
- The `kicad/kicad:nightly` image may predate the SWIG removal; check `kicad-cli version` before trusting a tag.

## Rules file (.kicad_dru)

- One mistake makes KiCad 10 drop the whole file silently: no message, DRC runs on board defaults, the exit code only reflects violations (issue #25848). Known causes:
  - an angle with a unit: `(min 134deg)`; write `(min 134)`
  - `A.Parent.Reference`; use `A.memberOfFootprint('U1')`
  - an unknown constraint name
  - a text variable `${...}`
- A rule that never matches still loads: `A.Type == 'pad'` (lowercase) is always false; write `'Pad'`.
- KiCad applies the last matching rule. An unconditional clearance rule after the net-class rules overrides all of them, and zones pull back by it too. Put the board-wide rule first, then one rule per class, then the strictest (mains) last.
- Prove each rule fires: a positive-control board with one deliberate violation per rule, checked by rule name in the DRC JSON.
- To measure actual spacing between nets, copy the board, set a 1.0 mm clearance on everything, run DRC: the reported actual values are the gaps.

## pcbnew scripting

- `board.Remove(item)` on an item from a live iterator skips items; collect first, then remove.
- `via.GetWidth()` needs a layer in 10 (`GetWidth(F_Cu)`). Under a Windows service the assert opens a dialog and hangs the process.
- `FOOTPRINT.Duplicate()` needs `addToParentGroup` in 10 and returns a `BOARD_ITEM`; cast or rebuild from the library.
- `FootprintLoad` with a path that does not exist returns `None` deep inside; check the library path per OS (`/usr/share/kicad/footprints` in the image).
- Changing `fp.Models()` in Python is not saved; rewrite the model path in the file text after saving.
- Headless KiCad 10 does not create teardrops; draw them as filled copper polygons from a script.
- `kicad-cli` prints image-handler debug lines on stderr; read the output files, not the text.

## Freerouting

- Freerouting 2.5 and 2.6 jars need Java 25. Run them in `eclipse-temurin:25-jre` when the host has an older Java.
- A rule area that only blocks zones is exported to the DSN as a keepout that blocks tracks too. Route those pads by hand.
- A hand-routed track must end on a pad centre, a via or another track, or Freerouting counts the net as unrouted and skips optimisation.
- Reserve an inner GND layer with `(autoroute_settings (layer_rule In1.Cu (active off)))` before `(boundary` in the DSN.
- Any DSN change moves the leftover small defects; rerun the full cleanup and gates after every route.

## Fabrication

- Set the aux origin at the bottom-left of the outline; Gerbers, drill and CPL all use it.
- A slot milled with a 1.0 mm tool has round ends; draw it with round ends or KiCad's creepage reads wrong.
- JLCPCB's zero rotation depends on the part's 3D model, so it can differ between parts in the same package. Check every new part in the placement preview, then add it to `[fab] rotate`.
