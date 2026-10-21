# ttyskin: specification

Status: version 0.3, built and checked on a real console (§6); the image import is new in 0.3.

ttyskin puts colour text art on the Linux login console (the text screen a machine shows after boot, before anyone logs in) and lets you switch between pieces of art. It has two parts:

- `ttyskin`, a command that installs a piece on a machine, removes it, and checks pieces.
- `ttyskin.html`, a single page that shows pieces exactly as the console draws them and lets you edit them.

## 1. How it works on the machine

- **Art:** the login prompt (`agetty`, util-linux 2.36 or newer) prints `/etc/issue` and then every file in `/etc/issue.d/`. ttyskin writes one file there, `/etc/issue.d/ttyskin.issue`, and never edits `/etc/issue`.
- **Colour:** the issue file carries colour escape sequences (`\e[...m`, which agetty turns into the escape character). The console shows 16 colours for text and 8 for backgrounds. Bright text (slots 8–15) is written as bold plus the base colour (`1;3x`), which the Linux console shows as the bright colour.
- **Palette:** the 16 colours themselves can be redefined. ttyskin sets them with `setvtrgb` and keeps them across reboots with its own boot unit, `ttyskin-palette.service`, which runs after the distribution's own palette unit. The palette applies to the whole console, not only to the art.
- **Redraw:** after a change, ttyskin clears every virtual console that is waiting at a login prompt (an active `getty@`/`autovt@` unit whose terminal has no one logged in, per `who`), then runs `agetty --reload` so the prompts redraw from the top; no reboot. Consoles where someone is logged in are never cleared. Login prompts start with `--noclear` on many distributions, which is why ttyskin clears them itself. If the reload fails, the change shows the next time the prompt is drawn.
- **Live values:** the issue file can include values the login prompt fills in each time it draws: host name, an interface's IPv4 address, date, time, logged-in users, the terminal's name, the OS name.

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

- **art.txt:** what is drawn. Trailing spaces don't matter; rows can be different lengths. No tabs or control characters. Only characters the console font has are allowed (`ttyskin check` and the page both flag the rest).
- **fg.txt and bg.txt:** the same shape as `art.txt`, one character per cell. `0`–`f` is a palette slot; `.`, a space or a missing cell means the console's default. Backgrounds take `0`–`7` only. A background colour past the end of an `art.txt` row colours spaces.
- **Live values in art.txt:** `{host}`, `{ipv4}` (the first global address), `{ipv4:<interface>}`, `{date}`, `{time}`, `{users}`, `{tty}`, `{os}`. The colours of the token's first cell colour the value. Any other text in braces is drawn as written (`check` warns when it looks like a mistyped live value). A live value's length varies, so leave room after it.
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
| `ttyskin status` | the piece in use, the palette, the boot unit, the pieces folder, the font and the console's size |
| `ttyskin font export` | writes a console font as JSON for the page (§4); `--psf <file>` picks the font, `-o <file>` the output |

- **Options for every command:** `--dir <folder>`, `--font <file>` (`.psf`, `.psf.gz` or an exported `.json`), `--size <columns>x<rows>`.
- **Dry run:** `use` and `off` take `--dry-run`, which prints every file they would write and every command they would run, and changes nothing.
- **Order of work:** `use` checks everything it needs (root, agetty's version, the piece, `setvtrgb` when a palette is involved, that the issue file is its own) before it writes anything.
- **Pieces folder:** `--dir`, else `TTYSKIN_PIECES`, else `pieces_dir=` in `/etc/ttyskin/config`, else the `pieces/` folder next to the command (after following links).
- **Font:** `--font`, else `font=` in the config, else the newest `/etc/console-setup/cached_*.psf.gz`. Without a font, `check` skips characters and says so.
- **Console size:** `--size`, else `size=` in the config, else the framebuffer's size (`/sys/class/graphics/fb0/virtual_size`) divided by the font's cell size.
- **Files it owns:** `/etc/issue.d/ttyskin.issue`; `/etc/ttyskin/state.json` (the piece in use and the issue file's hash), `/etc/ttyskin/vtrgb` (the palette in use), `/etc/ttyskin/vtrgb.saved` (the palette before the first `use`, read from `/sys/module/vt/parameters/default_{red,grn,blu}`); and `ttyskin-palette.service`, installed by hand. `use` and `off` refuse to replace or remove an issue file whose hash doesn't match the one they recorded, unless given `--force`.
- **Exit codes:** 0 done, 1 a piece failed its check, 2 usage error, 3 needs root, 4 the machine is missing something (an old `agetty`, no `setvtrgb`, an unreadable font), 5 a file ttyskin didn't write is in the way.
- **For tests:** `TTYSKIN_ROOT=<folder>` makes the command read and write system paths under that folder and run no system commands. `TTYSKIN_BRIGHT=aixterm` writes bright text as `9x` instead of `1;3x`.

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
- Afterwards View shows the piece in the palette it was made for: the piece's palette for *from the image* and *this piece's palette*; *Linux default* or *Ubuntu default* leave the piece without `palette.txt` (the console's own colours) and select that palette in View.

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
systemd/ttyskin-palette.service  keeps the palette across reboots
pieces/sample/                   the sample piece
tests/test_ttyskin.py            the command's tests (python3 -m unittest discover -s tests)
docs/SPEC.md                     this file
README.md                        what it does, install, use
LICENSE                          MIT; the font's public-domain note
```

Install is a clone and a link: the clone in `/opt/ttyskin`, the command linked into `/usr/local/bin`, the unit copied to `/etc/systemd/system`. The README gives the exact commands.

## 6. Checked

In development: the command's behaviour against a stand-in root (31 tests, Python 3.13 and 3.14), the page in headless Chromium (rendering, editing, saving into a folder), the default font's licence. The image import (0.3) in headless Chromium and Edge: imports of a logo, a photo and a sprite at 64 to 320 columns pass `ttyskin check`, with no network requests.

On a real console (Ubuntu 26.04, util-linux 2.41.3, systemd 259, 2560×1440 framebuffer, 2026-10-20):

- Bright text written as `1;3x` shows as the bright colour.
- `agetty --reload` redraws a waiting login prompt straight away.
- `setvtrgb` run from an SSH session changes the console's palette straight away.
- The palette survives a reboot: `ttyskin-palette.service` runs right after the distribution's `setvtrgb.service`.

Not checked: whether `9x` (`TTYSKIN_BRIGHT=aixterm`) also works on the Linux console; clearing waiting consoles before the redraw (new in 0.2).
