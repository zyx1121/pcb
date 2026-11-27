"""pcbkit tests. The pure tests run anywhere; the KiCad tests run inside the kicad/kicad image (CI does).

    PYTHONPATH=kit python3 -m unittest discover -s kit/tests
"""
import importlib.util
import tempfile
import textwrap
import unittest
from pathlib import Path

from pcbkit import config, fab, rules

HAS_KICAD = importlib.util.find_spec("pcbnew") is not None

GOOD = """(version 1)
(rule "Edge"
  (constraint edge_clearance (min 0.3mm)))
(rule "No acute"
  (condition "A.Type == 'Track'")
  (constraint track_angle (min 89)))
"""

BROKEN = {
    "deg unit": GOOD.replace("(min 89)", "(min 89deg)"),
    "parent": GOOD.replace("A.Type == 'Track'", "A.Parent.Reference == 'U1'"),
    "unknown constraint": GOOD.replace("edge_clearance", "edge_gap"),
    "text variable": GOOD.replace("(min 0.3mm)", "(min ${EDGE})"),
    "no version header": GOOD.replace("(version 1)\n", ""),
}


def write(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


class Lint(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_good_file_is_clean(self):
        self.assertEqual(rules.lint(write(self.tmp, "g.kicad_dru", GOOD)), [])

    def test_each_silent_drop_is_caught(self):
        for name, text in BROKEN.items():
            with self.subTest(name):
                self.assertTrue(rules.lint(write(self.tmp, "b.kicad_dru", text)))

    def test_lowercase_type(self):
        found = "\n".join(rules.lint(write(self.tmp, "l.kicad_dru", GOOD.replace("'Track'", "'track'"))))
        self.assertIn("never matches", found)

    def test_silkscreen_layer_name_is_fine(self):
        # KiCad 10 accepts "?.Silkscreen"; kicad-druid flags it, wrongly
        text = GOOD + '(rule "s" (layer "?.Silkscreen") (constraint text_height (min 1.0mm)))\n'
        self.assertEqual(rules.lint(write(self.tmp, "s.kicad_dru", text)), [])

    def test_unbalanced_and_duplicate(self):
        found = "\n".join(rules.lint(write(self.tmp, "u.kicad_dru", GOOD + '(rule "Edge" (constraint hole_size (min 0.3mm))\n')))
        self.assertIn("unclosed", found)
        self.assertIn("defined twice", found)


class Config(unittest.TestCase):
    def test_defaults_and_waivers(self):
        tmp = Path(tempfile.mkdtemp())
        p = write(tmp, "pcb.toml", """
            [board]
            pcb = "b.kicad_pcb"
            [[waive]]
            gate = "route"
            match = "short /USB"
            reason = "hand-routed later"
        """)
        cfg = config.load(p)
        self.assertEqual(cfg.rules, tmp / "b.kicad_dru")
        self.assertEqual(cfg.gates, ["rules", "drc", "parity", "route"])
        self.assertEqual(cfg.advise, ["druid", "happy"])
        self.assertIsNotNone(cfg.waived("route", "short /USB_DP 1 2 0.1 mm"))
        self.assertIsNone(cfg.waived("drc", "short /USB_DP"))

    def test_pcb_is_required(self):
        tmp = Path(tempfile.mkdtemp())
        with self.assertRaises(SystemExit):
            config.load(write(tmp, "pcb.toml", "[board]\n"))


class Bom(unittest.TestCase):
    def test_netlist_parts_and_grouping(self):
        tmp = Path(tempfile.mkdtemp())
        net = write(tmp, "n.xml", """<export><components>
            <comp ref="R2"><value>10k</value><footprint>R:R_0603</footprint><fields><field name="LCSC">C25804</field></fields></comp>
            <comp ref="R10"><value>10k</value><footprint>R:R_0603</footprint><fields><field name="LCSC">C25804</field></fields></comp>
            <comp ref="R1"><value>10k</value><footprint>R:R_0603</footprint><fields><field name="LCSC">C25804</field></fields></comp>
            <comp ref="R3"><value>1k</value><footprint>R:R_0603</footprint><property name="dnp"/></comp>
            <comp ref="SW1"><value>SW</value><footprint>S:SW</footprint></comp>
            <comp ref="SW2"><value>RST</value><footprint>S:TS</footprint><fields><field name="LCSC">C318884</field></fields></comp>
            <comp ref="SW3"><value>BOOT</value><footprint>S:TS</footprint><fields><field name="LCSC">C318884</field></fields></comp>
            <comp ref="F1"><value>5A</value><footprint>F:Clip</footprint><property name="LCSC" value="C151075"/></comp>
            </components></export>""")
        cfg = config.Config(root=tmp, pcb=tmp / "b.kicad_pcb", netlist=net, hand=["SW1"],
                            split={"F1": [["F1A", "1"], ["F1B", "2"]]})
        rows, missing = fab.bom_rows(cfg, {"R1", "R2", "R10", "F1A", "F1B", "SW2", "SW3"})
        self.assertEqual(rows[0], ["5A", "F1A,F1B", "Clip", "C151075"])
        self.assertEqual(rows[1], ["10k", "R1,R2,R10", "R_0603", "C25804"])
        self.assertEqual(rows[2], ["RST/BOOT", "SW2,SW3", "TS", "C318884"])   # one line per LCSC number
        self.assertEqual(missing, [])


@unittest.skipUnless(HAS_KICAD, "needs the KiCad image")
class Sentinel(unittest.TestCase):
    """The reason the rules gate exists: KiCad must load the good file and drop each broken one."""

    @classmethod
    def setUpClass(cls):
        import pcbnew

        cls.tmp = Path(tempfile.mkdtemp())
        board = pcbnew.BOARD()
        for x0, y0, x1, y1 in [(0, 0, 30, 0), (30, 0, 30, 20), (30, 20, 0, 20), (0, 20, 0, 0)]:
            s = pcbnew.PCB_SHAPE(board)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetLayer(pcbnew.Edge_Cuts)
            s.SetStart(pcbnew.VECTOR2I_MM(x0, y0))
            s.SetEnd(pcbnew.VECTOR2I_MM(x1, y1))
            board.Add(s)
        fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Resistor_SMD.pretty", "R_0603_1608Metric")
        fp.SetReference("R1")
        fp.SetPosition(pcbnew.VECTOR2I_MM(10, 10))
        board.Add(fp)
        cls.pcb = cls.tmp / "t.kicad_pcb"
        board.Save(str(cls.pcb))

    def test_good_file_loads(self):
        ok, msg = rules.sentinel(self.pcb, write(self.tmp, "g.kicad_dru", GOOD))
        self.assertTrue(ok, msg)

    def test_listed_constraints_load(self):
        # names that are easy to get wrong: each must load on its own
        for c in ["clearance", "hole_clearance", "hole_to_hole", "text_thickness", "track_width", "via_diameter",
                  "mechanical_clearance", "mechanical_hole_clearance", "solder_mask_sliver"]:
            with self.subTest(c):
                self.assertIn(c, rules.CONSTRAINTS)
                text = f'(version 1)\n(rule "c"\n  (constraint {c} (min 0.1mm)))\n'
                ok, _ = rules.sentinel(self.pcb, write(self.tmp, "c.kicad_dru", text))
                self.assertTrue(ok, c)

    def test_vendored_druid_rules_load(self):
        from pcbkit.advice import VENDOR

        for f in sorted(VENDOR.glob("*.kicad_dru")):
            with self.subTest(f.name):
                self.assertEqual(rules.lint(f), [])
                ok, _ = rules.sentinel(self.pcb, f)
                self.assertTrue(ok, f.name)

    def test_broken_files_are_dropped(self):
        for name, text in BROKEN.items():
            with self.subTest(name):
                ok, _ = rules.sentinel(self.pcb, write(self.tmp, "b.kicad_dru", text))
                self.assertFalse(ok, f"{name}: KiCad loaded it; if a newer KiCad reports the error, update rules.py")


if __name__ == "__main__":
    unittest.main()
