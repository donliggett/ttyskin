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
import time
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
        # addresses are written as text (0.4); the rest stay agetty escapes
        p = self.piece("a", ["{host} {ipv4:eth0} {ipv4} {date} {time} {users} {tty} {os}"])
        issue = T.to_issue(p, {"ipv4:eth0": "10.0.0.5", "ipv4": "192.168.1.9"})
        self.assertEqual(issue, "\\n 10.0.0.5 192.168.1.9 \\d \\t \\u \\l \\S\n")
        self.assertEqual(T.to_issue(p), "\\n - - \\d \\t \\u \\l \\S\n")

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


class TestConsoles(unittest.TestCase):
    UNITS = ("getty@tty1.service loaded active running Getty on tty1\n"
             "autovt@tty2.service loaded active running Getty on tty2\n"
             "getty@tty10.service loaded active running Getty on tty10\n")

    def test_idle_skips_logged_in(self):
        who = "adonis   tty1         2026-10-20 17:55\nadonis   pts/0        2026-10-20 17:38 (100.85.8.85)\n"
        self.assertEqual(T.idle_consoles(self.UNITS, who), ["tty2", "tty10"])

    def test_idle_none_logged_in(self):
        self.assertEqual(T.idle_consoles(self.UNITS, ""), ["tty1", "tty2", "tty10"])

    def test_no_consoles(self):
        self.assertEqual(T.idle_consoles("", ""), [])


UP = T.IFF_UP | T.IFF_RUNNING
# (label, address, link flags, scope), in the kernel's order
IFADDRS = [
    ("lo", "127.0.0.1", UP | T.IFF_LOOPBACK, 254),
    ("eth1", "169.254.3.3", UP, 253),       # link scope: not {ipv4}
    ("wlan0", "192.168.1.9", T.IFF_UP, 0),  # up but not running: not {ipv4}
    ("eth0", "10.0.0.5", UP, 0),
    ("eth0:1", "10.0.0.6", UP, 0),
    ("tailscale0", "100.64.0.1", UP, 0),
]


class FakeAddresses(Base):
    """Base with T.ifaddrs replaced by self.addrs."""

    def setUp(self):
        super().setUp()
        self.addrs = list(IFADDRS)
        self._ifaddrs = T.ifaddrs
        T.ifaddrs = lambda: list(self.addrs)

    def tearDown(self):
        T.ifaddrs = self._ifaddrs
        super().tearDown()

    def set_address(self, label, addr):
        self.addrs = [(l, addr if l == label else a, f, s) for l, a, f, s in self.addrs]


class TestAddresses(FakeAddresses):
    def test_pick_rules(self):
        self.assertEqual(T.pick_address(IFADDRS, None), "10.0.0.5")
        self.assertEqual(T.pick_address(IFADDRS, "eth0"), "10.0.0.5")
        self.assertEqual(T.pick_address(IFADDRS, "eth0:1"), "10.0.0.6")
        self.assertEqual(T.pick_address(IFADDRS, "wlan0"), "192.168.1.9")  # named: any state
        self.assertIsNone(T.pick_address(IFADDRS, "eth9"))
        self.assertIsNone(T.pick_address(IFADDRS[:3], None))

    def test_validated(self):
        for bad in ("999.1.1.1", "10.0.0.5\x1b[31m", "10.0.0.5 ", "", None, "::1", "\\4"):
            self.assertEqual(T.valid_address(bad), T.NO_ADDRESS, repr(bad))
        self.assertEqual(T.valid_address("10.0.0.5"), "10.0.0.5")

    def test_use_writes_literal_addresses(self):
        self.piece("a", ["ip {ipv4:tailscale0} lan {ipv4} x {ipv4:eth9} {host}"], fg=["...2"])
        self.assertEqual(self.run_cli("use", "a")[0], 0)
        issue = self.read("/etc/issue.d/ttyskin.issue")
        self.assertEqual(issue, "ip \\e[0;32m100.64.0.1 \\e[0mlan 10.0.0.5 x - \\n\n")
        self.assertNotIn("\\4", issue)
        self.assertEqual(T.read_state()["addresses"],
                         {"ipv4": "10.0.0.5", "ipv4:eth9": "-", "ipv4:tailscale0": "100.64.0.1"})

    def test_invalid_address_is_placeholder(self):
        self.set_address("eth0", "10.0.0.300")
        self.piece("a", ["{ipv4:eth0}a"])
        self.run_cli("use", "a")
        self.assertEqual(self.read("/etc/issue.d/ttyskin.issue"), "-a\n")

    def test_address_source_failure_is_placeholder(self):
        def broken():
            raise OSError("no netlink here")
        T.ifaddrs = broken
        self.piece("a", ["{ipv4}"])
        code, out, _ = self.run_cli("use", "a")
        self.assertEqual(code, 0)
        self.assertIn("can't read this machine's addresses", out)
        self.assertEqual(self.read("/etc/issue.d/ttyskin.issue"), "-\n")

    def test_piece_without_addresses_unchanged(self):
        # the same issue file 0.3 wrote, byte for byte
        self.piece("a", ["{os} · {tty}", "ab"], fg=["1111111111111", "2."])
        self.run_cli("use", "a")
        self.assertEqual(self.read("/etc/issue.d/ttyskin.issue"), "\\e[0;31m\\S · \\l\\e[0m\n\\e[0;32ma\\e[0mb\n")
        self.assertEqual(T.read_state()["addresses"], {})


class TestCurrentCopy(FakeAddresses):
    def files(self, d):
        out = {}
        for n in sorted(os.listdir(d)):
            with open(os.path.join(d, n), "rb") as f:
                out[n] = f.read()
        return out

    def test_use_writes_copy_and_off_removes_it(self):
        self.piece("a", ["a {ipv4}"], fg=["1"], palette=PALETTE)
        self.run_cli("use", "a")
        cur = self.path("/etc/ttyskin/current")
        self.assertEqual(self.files(cur), self.files(os.path.join(self.pieces, "a")))
        if os.name == "posix":
            self.assertEqual(os.stat(cur).st_mode & 0o777, 0o755)
            self.assertEqual(os.stat(os.path.join(cur, "art.txt")).st_mode & 0o777, 0o644)
        self.piece("b", ["b"])
        self.run_cli("use", "b")
        self.assertEqual(sorted(os.listdir(cur)), ["art.txt"])
        self.assertEqual(sorted(n for n in os.listdir(self.path("/etc/ttyskin")) if n.startswith(".")), [])
        self.run_cli("off")
        self.assertFalse(os.path.exists(cur))

    def test_dry_run_writes_no_copy(self):
        self.piece("a", ["a"])
        _, out, _ = self.run_cli("use", "a", "--dry-run")
        self.assertIn("current", out)
        self.assertFalse(os.path.exists(self.path("/etc/ttyskin")))

    def look(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            redrew = T.watch_look()
        return redrew, out.getvalue(), err.getvalue()

    def test_watch_renders_from_the_copy_only(self):
        self.piece("a", ["at {ipv4:eth0}"])
        self.run_cli("use", "a")
        # the pieces folder changes or goes away: the watcher doesn't care
        with open(os.path.join(self.pieces, "a", "art.txt"), "w") as f:
            f.write("edited {ipv4:eth0}\n")
        os.rename(self.pieces, self.pieces + ".gone")
        self.set_address("eth0", "10.0.0.7")
        redrew, out, _ = self.look()
        self.assertTrue(redrew)
        self.assertIn("{ipv4:eth0} 10.0.0.5 -> 10.0.0.7", out)
        issue = self.read("/etc/issue.d/ttyskin.issue")
        self.assertEqual(issue, "at 10.0.0.7\n")
        state = T.read_state()
        self.assertEqual(state["addresses"], {"ipv4:eth0": "10.0.0.7"})
        self.assertEqual(state["issue_sha256"], T.sha256(issue))
        self.assertTrue(T.issue_is_ours(state))

    def test_watch_no_change_no_redraw(self):
        self.piece("a", ["at {ipv4}"])
        self.run_cli("use", "a")
        before = os.stat(self.path("/etc/issue.d/ttyskin.issue")).st_mtime_ns
        self.assertEqual(self.look(), (False, "", ""))
        self.assertEqual(os.stat(self.path("/etc/issue.d/ttyskin.issue")).st_mtime_ns, before)

    def test_watch_leaves_foreign_issue_alone(self):
        self.piece("a", ["at {ipv4}"])
        self.run_cli("use", "a")
        with open(self.path("/etc/issue.d/ttyskin.issue"), "w") as f:
            f.write("someone else's\n")
        self.set_address("eth0", "10.0.0.8")
        redrew, _, err = self.look()
        self.assertFalse(redrew)
        self.assertIn("wasn't written by ttyskin", err)
        self.assertEqual(self.read("/etc/issue.d/ttyskin.issue"), "someone else's\n")

    def test_watch_idle(self):
        self.assertEqual(self.look(), (False, "", ""))  # nothing in use
        self.piece("a", ["no addresses {host}"])
        self.run_cli("use", "a")
        self.set_address("eth0", "10.0.0.9")
        self.assertEqual(self.look(), (False, "", ""))  # nothing to keep current
        self.run_cli("off")
        self.assertEqual(self.look(), (False, "", ""))

    def test_settle_config(self):
        problems = []
        self.assertEqual(T.watch_settle({}, problems.append), 3)
        self.assertEqual(T.watch_settle({"watch_settle": "15"}, problems.append), 15)
        for bad in ("0", "61", "2.5", "-1", "x"):
            self.assertEqual(T.watch_settle({"watch_settle": bad}, problems.append), 3)
        self.assertEqual(len(problems), 5)


class TestPacing(unittest.TestCase):
    """The watcher's decisions, as pure functions of times and addresses."""

    def simulate(self, events, addr_at, settle=3, end=300):
        """events: times the kernel sends address events; addr_at(t): the
        addresses shown at time t. Returns the times of the redraws."""
        written = addr_at(0)
        first = last = last_redraw = None
        redraws = []
        events = sorted(events)
        for tick in range(end * 4):
            t = tick / 4
            while events and events[0] <= t:
                events.pop(0)
                first = t if first is None else first
                last = t
            due = T.look_at(first, last, last_redraw, settle)
            if due is not None and t >= due:
                first = last = None
                now = addr_at(t)
                if T.address_changes(written, now):
                    written = now
                    redraws.append(t)
                    last_redraw = t
        return redraws

    def test_nothing_happens(self):
        self.assertIsNone(T.look_at(None, None, 5, 3))
        self.assertEqual(self.simulate([], lambda t: {"ipv4": "10.0.0.5"}), [])

    def test_reconnect_same_address(self):
        # Wi-Fi drops and comes back with the same address: events, no redraw
        def addr(t):
            return {"ipv4": "-" if 10 <= t < 11 else "10.0.0.5"}
        self.assertEqual(self.simulate([10, 10.25, 10.5, 11], addr), [])

    def test_one_redraw_per_change(self):
        def addr(t):
            return {"ipv4": "10.0.0.5" if t < 20 else "10.0.0.7"}
        self.assertEqual(self.simulate([20, 20.5, 21], addr), [24])

    def test_rate_limit(self):
        def addr(t):
            return {"ipv4": "10.0.0.5" if t < 20 else "10.0.0.6" if t < 25 else "10.0.0.7"}
        redraws = self.simulate([20, 25], addr)
        self.assertEqual(redraws, [23, 33])  # the second waits for the window to end

    def test_never_faster_than_the_limit(self):
        def addr(t):
            return {"ipv4": "10.0.0.%d" % (t // 2)}
        redraws = self.simulate([i * 2 for i in range(100)], addr)
        self.assertTrue(redraws)
        self.assertTrue(all(b - a >= T.WATCH_INTERVAL for a, b in zip(redraws, redraws[1:])))

    def test_steady_events_dont_postpone_for_ever(self):
        def addr(t):
            return {"ipv4": "10.0.0.5" if t < 1 else "10.0.0.7"}
        redraws = self.simulate([1 + i for i in range(200)], addr)
        self.assertEqual(redraws[0], 1 + T.WATCH_MAX_WAIT)

    def test_changes(self):
        self.assertEqual(T.address_changes({"ipv4": "a", "ipv4:x": "b"}, {"ipv4": "a", "ipv4:x": "c"}),
                         [("ipv4:x", "b", "c")])
        self.assertEqual(T.address_changes({}, {"ipv4": "a"}), [("ipv4", None, "a")])
        self.assertEqual(T.address_changes({"ipv4": "a"}, {"ipv4": "a"}), [])


def can_symlink():
    with tempfile.TemporaryDirectory() as d:
        try:
            os.symlink(d, os.path.join(d, "l"))
            return True
        except (OSError, NotImplementedError, AttributeError):
            return False


class TestHardening(Base):
    def check(self, name):
        return T.check_piece(T.Piece(self.pieces, name), T.Font(T.default_font_path()), (80, 30))

    def refuses(self, name, words):
        e, _ = self.check(name)
        self.assertTrue(any(words in x for x in e), e)
        code, out, _ = self.run_cli("use", name)
        self.assertEqual(code, T.EXIT_CHECK)
        self.assertIn(words, out)
        self.assertFalse(os.path.exists(self.path("/etc/issue.d/ttyskin.issue")))
        self.assertEqual(self.run_cli("check", name)[0], T.EXIT_CHECK)

    @unittest.skipUnless(can_symlink(), "needs symlinks")
    def test_linked_art(self):
        secret = os.path.join(self.tmp.name, "shadow")
        with open(secret, "w") as f:
            f.write("root:secret\n")
        d = os.path.join(self.pieces, "a")
        os.makedirs(d)
        os.symlink(secret, os.path.join(d, "art.txt"))
        self.refuses("a", "link")
        p = T.Piece(self.pieces, "a")
        self.assertEqual(p.art, [])
        self.assertEqual(self.run_cli("show", "a", "--issue")[0], T.EXIT_CHECK)

    @unittest.skipUnless(can_symlink(), "needs symlinks")
    def test_linked_piece_folder(self):
        real = os.path.join(self.tmp.name, "elsewhere")
        os.makedirs(real)
        with open(os.path.join(real, "art.txt"), "w") as f:
            f.write("a\n")
        os.makedirs(self.pieces)
        os.symlink(real, os.path.join(self.pieces, "a"), target_is_directory=True)
        self.refuses("a", "piece folder is a link")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs fifos")
    def test_fifo(self):
        d = os.path.join(self.pieces, "a")
        os.makedirs(d)
        os.mkfifo(os.path.join(d, "art.txt"))  # opening it normally would block for ever
        self.refuses("a", "not a regular file")

    def test_oversized_file(self):
        self.piece("a", ["a"])
        with open(os.path.join(self.pieces, "a", "fg.txt"), "w") as f:
            f.write("1" * (T.MAX_PIECE_FILE + 1))
        self.refuses("a", "bigger than")

    def test_not_utf8(self):
        self.piece("a", ["a"])
        with open(os.path.join(self.pieces, "a", "art.txt"), "wb") as f:
            f.write(b"a\xff\n")
        self.refuses("a", "not UTF-8")

    def test_c1_control(self):
        self.piece("a", ["a\u0085b"])
        self.refuses("a", "C1 control")
        self.piece("b", ["a\u009bb"])
        self.refuses("b", "C1 control")

    def test_bidi_and_zero_width(self):
        self.piece("a", ["ab‮c"])
        self.refuses("a", "invisible format character")
        self.piece("b", ["a​b"])
        self.refuses("b", "invisible format character")

    def test_wide(self):
        self.piece("a", ["aＷ"])
        self.refuses("a", "two cells wide")
        self.piece("b", ["漢"])
        self.refuses("b", "two cells wide")

    @unittest.skipUnless(T.DIR_FD_OK, "needs dir_fd")
    def test_reads_through_the_folder(self):
        self.piece("a", ["a"], fg=["1"])
        p = T.Piece(self.pieces, "a")
        self.assertTrue(p.read_by_dir_fd)
        self.assertEqual(p.fg, ["1"])

    @unittest.skipUnless(can_symlink() and T.DIR_FD_OK, "needs symlinks and dir_fd")
    def test_links_refused_without_dir_fd_too(self):
        T.DIR_FD_OK = False
        try:
            self.test_linked_piece_folder()
            self.assertFalse(T.Piece(self.pieces, "a").read_by_dir_fd)
        finally:
            T.DIR_FD_OK = True

    def assertNoRaw(self, *texts):
        for text in texts:
            for bad in ("\x1b", "\x07", "\x85", "\x9b", "‮"):
                self.assertNotIn(bad, text)

    def test_title_with_osc(self):
        self.piece("a", ["a"])
        with open(os.path.join(self.pieces, "a", "piece.json"), "w", encoding="utf-8") as f:
            json.dump({"title": "x\u001b]0;owned\u0007y\u009b‮z"}, f)
        code, out, err = self.run_cli("list")
        self.assertEqual(code, 0)
        self.assertIn("x?]0;owned?y??z", out)
        self.assertNoRaw(out, err)

    @unittest.skipUnless(os.name == "posix", "needs control characters in file names")
    def test_folder_name_with_escape(self):
        d = os.path.join(self.pieces, "a\x1b[31m")
        os.makedirs(d)
        with open(os.path.join(d, "art.txt"), "w") as f:
            f.write("a\n")
        code, out, err = self.run_cli("list")
        self.assertIn("a?[31m", out)
        self.assertNoRaw(out, err)
        code, out, err = self.run_cli("check", "a\x1b[31m")
        self.assertEqual(code, T.EXIT_CHECK)
        self.assertNoRaw(out, err)
        os.environ["TTYSKIN_PIECES"] = d
        code, out, err = self.run_cli("status")
        self.assertNoRaw(out, err)

    def test_show_refuses_raw_characters(self):
        for i, art in enumerate(["a\x1b[31mb", "c\u0085d", "e‮f", "g\x9b2Jh"]):
            name = "p%d" % i
            self.piece(name, [art])
            for argv in (("show", name), ("show", name, "--issue")):
                code, out, err = self.run_cli(*argv)
                self.assertEqual(code, T.EXIT_CHECK, argv)
                self.assertIn("ttyskin check", err)
                self.assertNoRaw(out, err)

    def test_show_still_works(self):
        self.piece("a", ["ab {tty}"], fg=["12"])
        code, out, _ = self.run_cli("show", "a")
        self.assertEqual(code, 0)
        self.assertIn("\x1b[0;31ma", out)  # ttyskin's own colours, nothing else

    def bad_font(self, data, name="bad.psf"):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as f:
            f.write(data)
        self.piece("a", ["a"])
        start = time.monotonic()
        code, _, err = self.run_cli("check", "a", "--font", path)
        self.assertLess(time.monotonic() - start, 2)
        self.assertEqual(code, T.EXIT_MISSING)
        self.assertIn("can't read the font", err)
        return err

    def test_psf2_huge_glyph_count(self):
        head = struct.pack("<8I", 0x864AB572, 0, 32, 1, 2 ** 31, 16, 16, 8)
        self.assertIn("2147483648 glyphs", self.bad_font(head + b"\x00" * 64))

    def test_psf2_bad_sizes(self):
        self.bad_font(struct.pack("<8I", 0x864AB572, 0, 32, 0, 256, 16, 16, 8))  # truncated
        self.bad_font(struct.pack("<8I", 0x864AB572, 0, 32, 0, 1, 99999, 9999, 8))
        self.bad_font(struct.pack("<8I", 0x864AB572, 0, 32, 0, 1, 8, 16, 8) + b"\x00" * 16)  # charsize lies
        self.bad_font(struct.pack("<8I", 0x864AB572, 0, 2 ** 31, 0, 1, 16, 16, 8) + b"\x00" * 16)
        self.bad_font(b"\x72\xb5\x4a\x86\x00")
        self.bad_font(bytes([0x36, 0x04, 0x00, 16]) + b"\x00" * 100)  # PSF1, truncated

    def test_gzip_bomb(self):
        err = self.bad_font(gzip.compress(b"\x00" * (T.MAX_FONT_FILE + 10)), "bomb.psf.gz")
        self.assertIn("uncompressed", err)

    def test_font_export_bad_font(self):
        path = os.path.join(self.tmp.name, "bad.psf")
        with open(path, "wb") as f:
            f.write(b"not a font")
        self.assertEqual(self.run_cli("font", "export", "--psf", path)[0], T.EXIT_MISSING)

    def test_commands_ignore_path(self):
        planted = os.path.join(self.tmp.name, "bin")
        os.makedirs(planted)
        for name in ("agetty", "setvtrgb", "who", "systemctl", "ttyskin-planted"):
            p = os.path.join(planted, name)
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho planted\n")
            os.chmod(p, 0o755)
        old = os.environ.get("PATH", "")
        os.environ["PATH"] = planted + os.pathsep + old
        try:
            self.assertIsNone(T.find_command("ttyskin-planted"))
            for name in ("agetty", "setvtrgb", "who", "systemctl"):
                found = T.find_command(name)
                self.assertTrue(found is None or os.path.dirname(found) in T.SYSTEM_DIRS, found)
            self.assertEqual(T.find_command("ttyskin-planted", dirs=(planted,)),
                             os.path.join(planted, "ttyskin-planted"))
            self.assertIsNone(T.command_output("ttyskin-planted"))
        finally:
            os.environ["PATH"] = old


class TestSample(unittest.TestCase):
    def test_sample_piece_passes(self):
        p = T.Piece(os.path.join(HERE, "..", "pieces"), "sample")
        font = T.Font(os.path.join(HERE, "..", "fonts", "Uni2-Fixed16.psf.gz"))
        errors, _ = T.check_piece(p, font, (80, 25))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
