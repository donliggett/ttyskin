# ttyskin: specification

Status: version 0.4, built and checked on a real console (§6). The image import is new in 0.3; addresses written by ttyskin, the watcher and the hardening are new in 0.4.

ttyskin puts colour text art on the Linux login console (the text screen a machine shows after boot, before anyone logs in) and lets you switch between pieces of art. It has two parts:

- `ttyskin`, a command that installs a piece on a machine, removes it, and checks pieces.
- `ttyskin.html`, a single page that shows pieces exactly as the console draws them and lets you edit them.

## 1. How it works on the machine

- **Art:** the login prompt (`agetty`, util-linux 2.36 or newer) prints `/etc/issue` and then every file in `/etc/issue.d/`. ttyskin writes one file there, `/etc/issue.d/ttyskin.issue`, and never edits `/etc/issue`.
- **Colour:** the issue file carries colour escape sequences (`\e[...m`, which agetty turns into the escape character). The console shows 16 colours for text and 8 for backgrounds. Bright text (slots 8–15) is written as bold plus the base colour (`1;3x`), which the Linux console shows as the bright colour.
- **Palette:** the 16 colours themselves can be redefined. ttyskin sets them with `setvtrgb` and keeps them across reboots with its own boot unit, `ttyskin-palette.service`, which runs after the distribution's own palette unit. The palette applies to the whole console, not only to the art.
- **Redraw:** after a change (by `use`, `off` or the watcher), ttyskin clears every virtual console that is waiting at a login prompt (an active `getty@`/`autovt@` unit whose terminal has no one logged in, per `who`), then runs `agetty --reload` so the prompts redraw from the top; no reboot. Consoles where someone is logged in are never cleared. Login prompts start with `--noclear` on many distributions, which is why ttyskin clears them itself. If the reload fails, the change shows the next time the prompt is drawn.
- **Live values:** the issue file can include values the login prompt fills in each time it draws: host name, date, time, logged-in users, the terminal's name, the OS name (agetty's escapes `\n`, `\d`, `\t`, `\u`, `\l`, `\S`).
- **Addresses:** IPv4 addresses are not left to agetty. An address escape (`\4`) makes agetty watch the kernel's address events and redraw its prompt on every one (Wi-Fi reconnects, IPv6 router advertisements, containers starting), so the art repainted every few minutes. Instead `use` writes each address as plain text, and `ttyskin watch` (§3.1, run by `ttyskin-watch.service`) redraws, the same way `use` does, only when an address shown on screen changes. The issue file has no network-related escapes, so agetty never redraws on its own. A piece without addresses gives the same issue file as in 0.3, byte for byte.

## 2. A piece

A piece is a folder. Its name is the folder's name: lowercase letters, digits and dashes.

```
pieces/<name>/
  art.txt       characters, one line per row (UTF-8)
  fg.txt        text colour per cell (optional)
  bg.txt        background colour per cell (optional)
  palette.txt   the 16 colours (optional)
  piece.json    title, author, licence, notes (optional)
```

- **art.txt:** what is drawn. Trailing spaces don't matter; rows can be different lengths. Whatever the font, these are refused: tabs, control characters (below 32, 127, and the C1 controls U+0080–U+009F), Unicode format characters (category `Cf`: bidi overrides, zero-width characters and the like), surrogates, and characters two cells wide (East Asian Wide and Fullwidth). Only characters the console font has are allowed (`ttyskin check` and the page both flag the rest).
- **Files:** every file is read without following links, and a piece folder that is itself a link is refused. Each file must be a regular file of at most 1 MiB, in UTF-8. The piece folder is opened once (`O_DIRECTORY | O_NOFOLLOW`) and each file is opened relative to it (`O_NOFOLLOW`), so the folder can't be swapped for a link while it is read. `check` reports these as errors.
- **fg.txt and bg.txt:** the same shape as `art.txt`, one character per cell. `0`–`f` is a palette slot; `.`, a space or a missing cell means the console's default. Backgrounds take `0`–`7` only. A background colour past the end of an `art.txt` row colours spaces.
- **Live values in art.txt:** `{host}`, `{ipv4}`, `{ipv4:<interface>}`, `{date}`, `{time}`, `{users}`, `{tty}`, `{os}`.
  - `{ipv4:<interface>}` is the first IPv4 address whose label is that name. The label is the one `ip addr` shows, which is what agetty's `\4{<interface>}` matched; an alias like `eth0:1` has its own label.
  - `{ipv4}` is the first global-scope IPv4 address, in the kernel's order, on an interface that is up, running and not loopback. That is agetty's rule plus global scope; there is no fallback to resolving the host name.
  - An interface with no address shows `-`. Every address is checked with Python's `ipaddress.IPv4Address` before it is written; anything that doesn't pass shows `-` too. The colours of the token's first cell colour the value. Any other text in braces is drawn as written (`check` warns when it looks like a mistyped live value). A live value's length varies, so leave room after it.
- **palette.txt:** 16 lines, `#rrggbb`, in console order: black, red, green, brown/yellow, blue, magenta, cyan, light grey, then the bright versions of the same eight. Without it, the console's own palette is used (if an earlier piece set one, `use` restores the palette saved before the first `use`).
- **piece.json:** `{"title": "...", "author": "...", "license": "...", "notes": "..."}`. Every field is optional.

The repository ships one sample piece. Other folders under `pieces/` are ignored by git, so your own pieces stay out of the repository; `--dir`, `TTYSKIN_PIECES` or the config file point the command at pieces kept anywhere else.

## 3. The command

Requires Python 3.8 or newer (standard library only), util-linux `agetty` 2.36+, and `setvtrgb` (kbd) for palettes. `use` and `off` need root; the others don't.

| command | what it does |
| --- | --- |
| `ttyskin list` | lists the pieces, marking the one in use |
| `ttyskin show <name>` | prints the piece in the current terminal, with live values filled in from this machine; `--issue` prints the issue file instead |
| `ttyskin check <name>` | checks the name, colour codes, palette, `piece.json`, characters against the console font, and width against the console's size |
| `ttyskin use <name>` | checks the piece, then installs it and its palette and redraws the login prompt |
| `ttyskin off` | removes the art, restores the palette saved before the first `use`, and redraws |
| `ttyskin status` | the piece in use, the addresses on screen, the palette, the boot unit and the watcher, the pieces folder, the font and the console's size |
| `ttyskin font export` | writes a console font as JSON for the page (§4); `--psf <file>` picks the font, `-o <file>` the output |
| `ttyskin watch` | keeps the addresses in the art current (§3.1); run by `ttyskin-watch.service`, as root |

- **Options for every command:** `--dir <folder>`, `--font <file>` (`.psf`, `.psf.gz` or an exported `.json`), `--size <columns>x<rows>`.
- **Printing:** everything ttyskin prints that a piece can influence goes through one function: titles, folder names, art in `show`, values in `status`, error messages. It replaces every character `check` refuses in art with `?`, so a piece can't send escape codes to the terminal running ttyskin. `show` refuses a piece with file or character errors, as `use` does, and says to run `check`.
- **Dry run:** `use` and `off` take `--dry-run`, which prints every file they would write and every command they would run, and changes nothing.
- **Order of work:** `use` checks everything it needs (root, agetty's version, the piece, `setvtrgb` when a palette is involved, that the issue file is its own) before it writes anything.
- **System commands:** `agetty`, `setvtrgb`, `systemctl` and `who` are taken from `/usr/sbin`, `/usr/bin`, `/sbin` and `/bin` only, never from `PATH`. Each is run as an argument list (no shell) with a 10-second timeout.
- **Addresses:** read from the kernel with an `RTM_GETLINK` and an `RTM_GETADDR` dump over a netlink socket; no command output is parsed. If they can't be read, `use` warns and writes `-`.
- **Lock:** `use`, `off` and each look the watcher takes hold an exclusive `flock` on `/etc/ttyskin/lock` around reading the state, rendering and writing. A dry run takes no lock.
- **Pieces folder:** `--dir`, else `TTYSKIN_PIECES`, else `pieces_dir=` in `/etc/ttyskin/config`, else the `pieces/` folder next to the command (after following links).
- **Font:** `--font`, else `font=` in the config, else the newest `/etc/console-setup/cached_*.psf.gz`. Without a font, `check` skips characters and says so.
- **Font limits:** sizes are checked before anything is allocated. The font must be a regular file of at most 8 MiB after decompressing, with at most 65,536 glyphs of at most 64×64 and bytes per glyph matching that size. The Unicode table is read only to the end of the data. A bad font is an error (exit 4).
- **Console size:** `--size`, else `size=` in the config, else the framebuffer's size (`/sys/class/graphics/fb0/virtual_size`) divided by the font's cell size.
- **Files it owns:**
  - `/etc/issue.d/ttyskin.issue`.
  - `/etc/ttyskin/state.json`: the piece in use, the issue file's hash and the addresses written into it.
  - `/etc/ttyskin/current/`: the validated copy of the piece in use, holding whichever of its five files exist. It is root-owned, with the folder 0755 and the files 0644, and is written as a new folder, then renamed into place. `off` removes it.
  - `/etc/ttyskin/lock`.
  - `/etc/ttyskin/vtrgb`: the palette in use.
  - `/etc/ttyskin/vtrgb.saved`: the palette before the first `use`, read from `/sys/module/vt/parameters/default_{red,grn,blu}`.
  - `ttyskin-palette.service` and `ttyskin-watch.service`, installed by hand.
- **Ownership:** `use`, `off` and the watcher refuse to replace or remove an issue file whose hash doesn't match the one recorded. `use` and `off` replace it when given `--force`; the watcher never does.
- **Exit codes:** 0 done, 1 a piece failed its check, 2 usage error, 3 needs root, 4 the machine is missing something (an old `agetty`, no `setvtrgb`, an unreadable font), 5 a file ttyskin didn't write is in the way.
- **For tests:** `TTYSKIN_ROOT=<folder>` makes the command read and write system paths under that folder, run no system commands and read no addresses (every address shows `-`). `TTYSKIN_BRIGHT=aixterm` writes bright text as `9x` instead of `1;3x`.

### 3.1 The watcher

`ttyskin watch` is the command `ttyskin-watch.service` runs, as root. Its only inputs are the kernel's address events and the root-owned files ttyskin wrote. It listens on no port, opens no network connection, and never reads the pieces folder.

- **At start:** it takes one look (below), since addresses may have changed while it was stopped, then waits for events.
- **Events:** a netlink (`NETLINK_ROUTE`) socket subscribed to IPv4 address and link changes. It is drained on each wake and the messages are discarded; an overrun counts as an event.
- **Settle:** it looks `watch_settle` seconds after the last event, but no later than 60 seconds after the first event of a burst. `watch_settle=` goes in `/etc/ttyskin/config`, in whole seconds from 1 to 60; the default is 3.
- **Look:** under the lock, it re-reads `state.json` and `/etc/ttyskin/current/`, reads the addresses, and works out what the piece shows.
  - If nothing differs from the addresses recorded in `state.json`, it does nothing.
  - Otherwise it does what `use` does: it writes the issue file and the state, clears the waiting consoles, and runs `agetty --reload`.
  - With no piece in use, or a piece without addresses, a look does nothing.
- **Rate limit:** at most one redraw every 10 seconds; a change inside that window is applied when the window ends.
- **Logging:** one line per redraw (which addresses changed, from and to), one per problem, nothing per event.
- **Signals:** it exits cleanly (status 0) on SIGTERM and SIGINT.
- **Consoles:** they are opened with `O_NOCTTY | O_NONBLOCK`, so the watcher never takes a console as its controlling terminal and never blocks on a paused one.
- **`--prepare`:** creates `/run/agetty.reload` if it is missing, then exits. It opens the file without touching it, so nothing redraws. The service runs this outside its sandbox, before the watcher starts. agetty creates the file only when it starts waiting, and the sandbox can make the file writable only if it already exists.

The service, `systemd/ttyskin-watch.service`, runs as root because the watcher writes root-owned files, writes to `/dev/ttyN` and runs `agetty --reload`. Everything else is taken away:

- No capabilities.
- The file system is read-only except `/etc/issue.d`, `/etc/ttyskin` and `/run/agetty.reload`.
- Only netlink and local sockets, and no IP traffic.
- Only tty devices, write-only.
- A system-call filter, and 64 MB of memory.

`systemd-analyze security` rates it 1.8 ("OK"). It keeps the host's network namespace (`PrivateNetwork=` stays off), because the watcher needs the host's address events.

## 4. The page

`ttyskin.html` is one self-contained file with no build step and no network use. It opens from disk in any current browser; Chrome and Edge can also save into folders.

- **Open folder** (Chrome, Edge): pick a pieces folder or one piece's folder; dropping a folder on the page does the same. **Save** (Ctrl+S) writes `art.txt`, `fg.txt`, `bg.txt`, `palette.txt` and `piece.json` back into the piece's folder, and deletes `fg.txt`, `bg.txt` or `palette.txt` when the piece no longer has them.
- **Open read-only** (any browser): reads a folder; **Download** saves the current piece as a `.zip` of its files.
- **New** and **Duplicate** make a piece (a new folder when a pieces folder is open).
- **Import image…** turns a picture into a piece (below); dropping an image file on the page does the same.
- **View:**
  - The piece drawn with the console's bitmap font, in its palette, the Linux default palette or Ubuntu's.
  - The art alone (with room around it to keep drawing), or the whole console at its size in columns and rows, with a sample distribution line, the art, and the login prompt below it.
  - A grid; live values replaced by sample values; zoom.
  - The arrow keys flip between pieces.
- **Edit:**
  - Brush: pick a character, a text colour and a background, then click or drag. Right-click erases; Alt+click picks up a cell. The brush can change characters and colours, characters only, or colours only.
  - Text: click a cell and type; Enter goes to the next line at the starting column.
  - Select: drag a rectangle; drag inside it to move it; Ctrl+C, Ctrl+X, Ctrl+V and Delete. Pasting plain text from elsewhere uses the brush's colours.
  - Pick: click a cell to take its character and colours.
  - Undo and redo (Ctrl+Z, Ctrl+Y).
  - Palette: 16 colour pickers that recolour the art as you change them; **Make piece palette** starts one from the colours on screen.
  - Live values: insert one at the text cursor.
  - Every character in the font, to paint with or type at the cursor.
- **Check:** characters the font lacks are outlined in red and listed, with width against the console, tabs and text in braces that isn't a live value.
- **Sample values:** the host name, IPv4 address (with per-interface values, like `tailscale0=100.64.0.1`), OS name, terminal and user count the page shows for live values; date and time come from the clock. They are kept in the browser between visits.
- **Font:** the page includes the 8×16 Uni2 Fixed console font. **Font…** loads another: a `ttyskin font export` file, or a `.psf` / `.psf.gz` directly.
- **Console size:** presets (80×25, 160×50, 240×67, 320×90) or columns and rows typed in.

### Image import

**Import image…** (or an image file dropped on the page: anything the browser decodes, such as PNG, JPEG, WebP, GIF or SVG) opens a dialog with a live preview drawn in the console font, at the dialog's width (up to 2×), 1× or 2×. The result is an ordinary piece, to finish by hand.

- **Width** in columns. It starts at the smaller of the console's columns and the picture's width divided by the font's cell width. The height follows the picture's shape, allowing for the cell's: rows = columns × height / width × cell width / cell height. A picture taller than the console is capped at the console's rows (and the width shrinks to keep its shape); the dialog says so.
- **Palette:** *from the image* (the default), *this piece's palette* (when the open piece has one), *Linux default* or *Ubuntu default*.
- **Characters:** *blocks* (space `█ ░ ▒ ■ ▮`); *blocks and lines*, which adds shapes that carry edges in an 8×16 console font (`─ │ ═ ║ ┼ ├ ┤ ┬ ┴ ┌ ┐ └ ┘ ╭ ╮ ╰ ╯ ╱ ╲ ╳ / \ _ ‗ ¯ · . • ●`); or *every character in the font*, which is slow and warns above 80 columns. Only characters the loaded font has are used, and never `{` or `}`, combining marks or other characters that don't take one cell.
- **Into:** *a new piece* (named like **New**, with its own folder when a pieces folder is open) or *replace this piece* (one undo restores the art and the palette).
- The piece keeps the palette its colours were matched against: *from the image*, *Linux default* and *Ubuntu default* write it as the piece's `palette.txt`, so the console shows what the preview showed whatever palette the machine had; *this piece's palette* leaves `palette.txt` as it was. Afterwards View shows the piece in its palette.

How it chooses:

1. The picture is drawn at exactly one font cell of pixels per cell (columns × cell width by rows × cell height), smoothed when shrinking; when enlarging (pixel art) it keeps hard pixels. Pixels under 50% opacity are transparent.
2. **Palette from the image:** a picture with 16 colours or fewer keeps its own colours (near copies merged). Otherwise k-means in OKLab on a sample of the pixels finds 16, then near copies are merged and small clusters that are only the blend along an edge between two bigger colours are dropped. The 8 colours with the most area go in slots 0–7 (only those can be backgrounds), the rest in 8–15. Slot 0, the console's background, is the darkest colour; it is black when the picture's darkest colour isn't dark, or when the picture has transparent parts and no colour near black. Slot 7, the console's text colour, is the colour most readable on slot 0, and is lightened until it has a contrast ratio of at least 4.5:1 with slot 0. Slots the picture doesn't need keep the Linux default colours and aren't used in the art.
3. **Each cell:** for each candidate character, the glyph splits the cell's pixels into its "on" and "off" pixels. The text colour (any slot) is the one nearest the "on" pixels' mean, the background (slots 0–7, or none) the one nearest the "off" pixels' mean, and the character whose choice has the least sum of squared OKLab distances, pixel by pixel, wins. A transparent pixel counts as showing slot 0, and colouring it costs a little more, so transparent areas get no background colour and a fully transparent cell is a space.

The output uses only `0`–`f` for text, `0`–`7` for backgrounds and characters in the font, so it passes `ttyskin check` against that font.

## 5. Repository layout

```
ttyskin                          the command (Python, one file)
ttyskin.html                     the page (the font is embedded in it)
fonts/Uni2-Fixed16.psf.gz        the font the page embeds; also used by the tests
fonts/README.md                  where the font comes from; it is in the public domain
systemd/ttyskin-palette.service  keeps the palette across reboots
systemd/ttyskin-watch.service    runs ttyskin watch, which keeps addresses current
pieces/sample/                   the sample piece
tests/test_ttyskin.py            the command's tests (python3 -m unittest discover -s tests)
docs/SPEC.md                     this file
docs/GUIDE.md                    how to use the page and the command
docs/screenshot.png              the README's picture of the page
.github/workflows/pages.yml      publishes the page as a website on every push (actions pinned to commit SHAs)
README.md                        what it does, install, use
LICENSE                          MIT
```

Install is a clone and a link: the clone in `/opt/ttyskin`, the command linked into `/usr/local/bin`, the two units copied to `/etc/systemd/system` and enabled. Upgrading from 0.3 also means copying and enabling `ttyskin-watch.service` and running `use` again, so that `/etc/ttyskin/current/` exists. The README gives the exact commands.

## 6. Checked

In development: the command's behaviour against a stand-in root (73 tests in 0.4, Python 3.8 and 3.14 on Linux, 3.14 on Windows), the page in headless Chromium (rendering, editing, saving into a folder), the default font's licence. The image import (0.3) in headless Chromium and Edge: imports of a logo, a photo and a sprite at 64 to 320 columns pass `ttyskin check`, with no network requests.

On a real console (Ubuntu 26.04, util-linux 2.41.3, systemd 259, 2560×1440 framebuffer, 2026-10-20):

- Bright text written as `1;3x` shows as the bright colour.
- `agetty --reload` redraws a waiting login prompt straight away.
- `setvtrgb` run from an SSH session changes the console's palette straight away.
- The palette survives a reboot: `ttyskin-palette.service` runs right after the distribution's `setvtrgb.service`.

In 0.4, in a Debian 13 container with systemd 257 and util-linux 2.41.5 (2026-10-21):

- `systemd-analyze security --offline=yes` rates `ttyskin-watch.service` 1.8 ("OK").
- Inside the sandbox, `agetty --reload` works and `systemctl list-units` lists the login prompts.
- On a dummy interface:
  - A reconnect that returns the same address redraws nothing.
  - A real change redraws once, 3 seconds later.
  - A second change inside 10 seconds is applied when the 10 seconds end.
- SIGTERM stops the watcher with status 0.
- The addresses from the netlink dump match `ip -4 addr`.

Not checked: the watcher on a real console and with someone logged in (whether `who` sees the logins from inside the sandbox); whether `9x` (`TTYSKIN_BRIGHT=aixterm`) also works on the Linux console; clearing waiting consoles before the redraw (new in 0.2).
