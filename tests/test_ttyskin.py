"""Tests for the ttyskin command. Run from the repository root:

    python3 -m unittest discover -s tests

They run against a temporary folder standing in for / (TTYSKIN_ROOT), so they
change nothing on the machine and run no system commands.
"""

import contextlib
import gzip
import importlib.machinery
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "ttyskin")
_loader = importlib.machinery.SourceFileLoader("ttyskin", SCRIPT)
_spec = importlib.util.spec_from_loader("ttyskin", _loader)
T = importlib.util.module_from_spec(_spec)
_loader.exec_module(T)


def psf2(chars, width=8, height=16):
    """A tiny PSF2 font with one blank glyph per character."""
    n = len(chars)
    charsize = height * ((width + 7) // 8)
    head = struct.pack("<8I", 0x864AB572, 0, 32, 1, n, charsize, height, width)
    glyphs = b"\x00" * (charsize * n)
    table = b"".join(c.encode("utf-8") + b"\xff" for c in chars)
    return head + glyphs + table


FONT_CHARS = " abcdefghijklmnopqrstuvwxyz{}:·\\█░▒─│┌┐└┘═║╔╗╚╝"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "root")
        self.pieces = os.path.join(self.tmp.name, "pieces")
        os.makedirs(os.path.join(self.root, "etc/console-setup"))
        with gzip.open(os.path.join(self.root, "etc/console-setup/cached_Test16.psf.gz"), "wb") as f:
            f.write(psf2(FONT_CHARS))
        vt = os.path.join(self.root, "sys/module/vt/parameters")
        os.makedirs(vt)
        for c in ("red", "grn", "blu"):
            with open(os.path.join(vt, "default_" + c), "w") as f:
                f.write(",".join(["0"] * 15 + ["255"]) + "\n")
        fb = os.path.join(self.root, "sys/class/graphics/fb0")
        os.makedirs(fb)
        with open(os.path.join(fb, "virtual_size"), "w") as f:
            f.write("640,480\n")  # 80x30 with an 8x16 font
        self._env = {k: os.environ.get(k) for k in ("TTYSKIN_ROOT", "TTYSKIN_PIECES", "TTYSKIN_BRIGHT")}
        os.environ["TTYSKIN_ROOT"] = self.root
        os.environ["TTYSKIN_PIECES"] = self.pieces
        os.environ.pop("TTYSKIN_BRIGHT", None)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def piece(self, name, art, fg=None, bg=None, palette=None):
        d = os.path.join(self.pieces, name)
        os.makedirs(d, exist_ok=True)
        for fname, rows in (("art.txt", art), ("fg.txt", fg), ("bg.txt", bg), ("palette.txt", palette)):
            if rows is not None:
                with open(os.path.join(d, fname), "w", encoding="utf-8") as f:
                    f.write("\n".join(rows) + "\n")
        return T.Piece(self.pieces, name)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = T.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def path(self, p):
        return os.path.join(self.root, p.lstrip("/"))

    def read(self, p):
        return T.read_text(self.path(p))


PALETTE = ["#%02x%02x%02x" % (i * 16, i * 16, i * 16) for i in range(16)]


class TestRender(Base):
    def test_plain(self):
        p = self.piece("a", ["ab", "c"])
        self.assertEqual(T.to_issue(p), "ab\nc\n")

    def test_backslash_is_escaped(self):
        p = self.piece("a", ["a\\b"])
        self.assertEqual(T.to_issue(p), "a\\\\b\n")

    def test_colour_runs(self):
        p = self.piece("a", ["abc"], fg=["11d"], bg=["..2"])
        self.assertEqual(T.to_issue(p), "\\e[0;31mab\\e[0;1;35;42mc\\e[0m\n")

    def test_bright_aixterm(self):
        os.environ["TTYSKIN_BRIGHT"] = "aixterm"
        p = self.piece("a", ["a"], fg=["9"])
        self.assertEqual(T.to_issue(p), "\\e[0;91ma\\e[0m\n")

    def test_background_past_art(self):
        p = self.piece("a", ["a"], bg=[".44"])
        self.assertEqual(T.to_issue(p), "a\\e[0;44m  \\e[0m\n")

    def test_spaces_keep_colour_state(self):
        p = self.piece("a", ["a b"], fg=["1.1"])
        self.assertEqual(T.to_issue(p), "\\e[0;31ma b\\e[0m\n")

    def test_tokens(self):
        p = self.piece("a", ["{host} {ipv4:eth0} {ipv4} {date} {time} {users} {tty} {os}"])
        self.assertEqual(T.to_issue(p), "\\n \\4{eth0} \\4 \\d \\t \\u \\l \\S\n")

    def test_token_takes_first_cell_colour(self):
        p = self.piece("a", ["{tty}!"], fg=["2....3"])
        self.assertEqual(T.to_issue(p), "\\e[0;32m\\l\\e[0;33m!\\e[0m\n")

    def test_unknown_braces_are_literal(self):
        p = self.piece("a", ["{hostname} {"])
        self.assertEqual(T.to_issue(p), "{hostname} {\n")

    def test_vtrgb(self):
        pal = [(i, i + 1, i + 2) for i in range(16)]
        rows = T.palette_to_vtrgb(pal).splitlines()
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].split(",")[:2], ["0", "1"])
        self.assertEqual(rows[2].split(",")[-1], "17")


class TestCheck(Base):
    def check(self, p, size=(80, 30)):
        return T.check_piece(p, T.Font(T.default_font_path()), size)

    def test_ok(self):
        e, _ = self.check(self.piece("a", ["abc"], fg=["123"], palette=PALETTE))
        self.assertEqual(e, [])

    def test_bad_name(self):
        e, _ = self.check(self.piece("Bad_Name", ["a"]))
        self.assertTrue(any("name" in x for x in e))

    def test_missing_glyph(self):
        e, _ = self.check(self.piece("a", ["a▓"]))
        self.assertTrue(any("not in the console font" in x for x in e))

    def test_bad_colours(self):
        e, _ = self.check(self.piece("a", ["ab"], fg=["1z"], bg=["8."]))
        self.assertEqual(len([x for x in e if "is not a colour" in x]), 2)

    def test_bad_palette(self):
        e, _ = self.check(self.piece("a", ["a"], palette=PALETTE[:15]))
        self.assertTrue(any("palette" in x for x in e))

    def test_tab(self):
        e, _ = self.check(self.piece("a", ["a\tb"]))
        self.assertTrue(any("tab" in x for x in e))

    def test_too_wide(self):
        e, _ = self.check(self.piece("a", ["a" * 81]))
        self.assertTrue(any("columns wide" in x for x in e))

    def test_not_a_token_warns(self):
        _, w = self.check(self.piece("a", ["{hostname}"]))
        self.assertTrue(any("not a live value" in x for x in w))

    def test_console_size_from_framebuffer(self):
        f = T.Font(T.default_font_path())
        self.assertEqual(T.console_size(type("A", (), {"size": None})(), f), (80, 30))


class TestFont(Base):
    def test_psf2_map(self):
        f = T.Font(T.default_font_path())
        self.assertTrue(f.has("█"))
        self.assertFalse(f.has("▓"))
        self.assertEqual((f.width, f.height), (8, 16))

    def test_psf1(self):
        n, cs = 256, 16
        table = b""
        for i in range(n):
            table += struct.pack("<H", 0x41 + i if i < 3 else 0x2588) if i < 4 else b""
            table += b"\xff\xff"
        data = bytes([0x36, 0x04, 0x02, cs]) + b"\x00" * (n * cs) + table
        w, h, glyphs, cmap = T.parse_psf(data)
        self.assertEqual((w, h, len(glyphs)), (8, 16, 256))
        self.assertEqual(cmap[0x41], 0)
        self.assertEqual(cmap[0x2588], 3)

    def test_export_round_trip(self):
        out = os.path.join(self.tmp.name, "font.json")
        code, _, _ = self.run_cli("font", "export", "-o", out)
        self.assertEqual(code, 0)
        f = T.Font(out)
        self.assertTrue(f.has("░"))
        self.assertEqual(json.loads(T.read_text(out))["format"], "ttyskin-font/1")


class TestUseOff(Base):
    def test_dry_run_writes_nothing(self):
        self.piece("a", ["a"], palette=PALETTE)
        code, out, _ = self.run_cli("use", "a", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("would write", out)
        self.assertFalse(os.path.exists(self.path("/etc/issue.d/ttyskin.issue")))
        self.assertFalse(os.path.exists(self.path("/etc/ttyskin")))

    def test_use_then_off(self):
        self.piece("a", ["a"], fg=["1"], palette=PALETTE)
        self.assertEqual(self.run_cli("use", "a")[0], 0)
        self.assertTrue(os.path.exists(self.path("/etc/issue.d/ttyskin.issue")))
        self.assertTrue(os.path.exists(self.path("/etc/ttyskin/vtrgb")))
        saved = self.read("/etc/ttyskin/vtrgb.saved")
        self.assertTrue(saved.startswith("0,0,"))
        self.assertEqual(T.read_state()["piece"], "a")
        code, out, _ = self.run_cli("off")
        self.assertEqual(code, 0)
        self.assertIn("vtrgb.saved", out)  # the saved palette is put back
        for p in ("/etc/issue.d/ttyskin.issue", "/etc/ttyskin/vtrgb",
                  "/etc/ttyskin/vtrgb.saved", "/etc/ttyskin/state.json"):
            self.assertFalse(os.path.exists(self.path(p)), p)

    def test_saved_palette_is_kept_across_switches(self):
        self.piece("a", ["a"], palette=PALETTE)
        self.piece("b", ["b"], palette=list(reversed(PALETTE)))
        self.run_cli("use", "a")
        first = self.read("/etc/ttyskin/vtrgb.saved")
        self.run_cli("use", "b")
        self.assertEqual(self.read("/etc/ttyskin/vtrgb.saved"), first)

    def test_switch_to_piece_without_palette_restores(self):
        self.piece("a", ["a"], palette=PALETTE)
        self.piece("b", ["b"])
        self.run_cli("use", "a")
        code, out, _ = self.run_cli("use", "b")
        self.assertEqual(code, 0)
        self.assertIn("vtrgb.saved", out)
        self.assertFalse(os.path.exists(self.path("/etc/ttyskin/vtrgb")))

    def test_refuses_foreign_issue_file(self):
        self.piece("a", ["a"])
        os.makedirs(self.path("/etc/issue.d"))
        with open(self.path("/etc/issue.d/ttyskin.issue"), "w") as f:
            f.write("someone else's\n")
        self.assertEqual(self.run_cli("use", "a")[0], T.EXIT_IN_THE_WAY)
        self.assertEqual(self.run_cli("off")[0], T.EXIT_IN_THE_WAY)
        self.assertEqual(self.run_cli("use", "a", "--force")[0], 0)

    def test_failed_check_changes_nothing(self):
        self.piece("a", ["a▓"])
        self.assertEqual(self.run_cli("use", "a")[0], T.EXIT_CHECK)
        self.assertFalse(os.path.exists(self.path("/etc/issue.d/ttyskin.issue")))

    def test_unknown_piece(self):
        self.assertEqual(self.run_cli("use", "nope")[0], T.EXIT_USAGE)

    def test_list_marks_current(self):
        self.piece("a", ["a"])
        self.piece("b", ["b"])
        self.run_cli("use", "b")
        _, out, _ = self.run_cli("list")
        self.assertIn("* b", out)
        self.assertIn("  a", out)


class TestSample(unittest.TestCase):
    def test_sample_piece_passes(self):
        p = T.Piece(os.path.join(HERE, "..", "pieces"), "sample")
        font = T.Font(os.path.join(HERE, "..", "fonts", "Uni2-Fixed16.psf.gz"))
        errors, _ = T.check_piece(p, font, (80, 25))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
