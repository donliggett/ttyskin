# ttyskin: specification

Status: draft for review. Nothing is built yet.

ttyskin puts colour text art on the Linux login console (the text screen a machine shows after boot, before anyone logs in) and lets you switch between pieces of art. It has two parts:

- `ttyskin`, a command that installs a piece on a machine, removes it, and checks pieces.
- `ttyskin.html`, a single page that shows pieces exactly as the console draws them and lets you edit them.

## 1. How it works on the machine

- **Art:** the login prompt (`agetty`, util-linux 2.36 or newer) prints `/etc/issue` and then every file in `/etc/issue.d/`. ttyskin writes one file there, `/etc/issue.d/ttyskin.issue`, and never edits `/etc/issue`.
- **Colour:** the issue file carries standard colour escape sequences. The console shows 16 colours for text and 8 for backgrounds.
- **Palette:** the 16 colours themselves can be redefined. ttyskin sets them with `setvtrgb` and keeps them across reboots with its own small boot unit. The palette applies to the whole console, not only to the art.
- **Redraw:** after a change, ttyskin asks the running login prompts to redraw (`agetty --reload`), so no reboot is needed.
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

- **art.txt:** what is drawn. Trailing spaces don't matter; rows can be different lengths. Only characters the console font has are allowed (`ttyskin check` and the page both flag the rest).
- **fg.txt and bg.txt:** the same shape as `art.txt`, one character per cell. `0`–`f` is a palette slot, `.` (or a missing cell) means the console's default. Backgrounds take `0`–`7` only.
- **Live values in art.txt:** written as `{host}`, `{ipv4:<interface>}`, `{date}`, `{time}`, `{users}`, `{tty}`, `{os}`. The colour of the token's first cell colours the value. A literal brace is written `{{` or `}}`. A live value's length varies, so leave room after it.
- **palette.txt:** 16 lines, `#rrggbb`, in console order: black, red, green, brown/yellow, blue, magenta, cyan, light grey, then the bright versions of the same eight. Without it, the machine's current palette stays.
- **piece.json:** `{"title": "...", "author": "...", "license": "...", "notes": "..."}`. Every field is optional.

The repository ships one sample piece. Other folders under `pieces/` are ignored by git, so your own pieces stay out of the repository; `--dir` (or `TTYSKIN_PIECES`) points the command at pieces kept anywhere else.

## 3. The command

Requires Python 3.8 or newer (standard library only), util-linux `agetty` 2.36+, and `setvtrgb` for palettes. Changes need root; `list`, `show` and `check` don't.

| command | what it does |
| --- | --- |
| `ttyskin list` | lists the pieces, marking the one in use |
| `ttyskin show <name>` | prints the piece in the current terminal, with live values filled in from this machine |
| `ttyskin check <name>` | checks shapes, colour codes, characters against the console font, and width against the console's size |
| `ttyskin use <name>` | installs the piece and its palette, then redraws the login prompt |
| `ttyskin off` | removes the art, restores the palette saved before the first `use`, and redraws |
| `ttyskin status` | the piece in use, the palette in use, and where the files are |
| `ttyskin font export` | writes the machine's console font as JSON for the page (§4) |

- **Dry run:** `use` and `off` take `--dry-run`, which prints every file they would write and every command they would run.
- **Pieces folder:** `--dir <path>`, else `TTYSKIN_PIECES`, else `pieces_dir` in `/etc/ttyskin/config`, else the `pieces/` folder next to the command.
- **Files it owns:** `/etc/issue.d/ttyskin.issue`, `/etc/ttyskin/` (config, current palette, the palette saved before first use), and `ttyskin-palette.service`. `use` refuses to overwrite a file it didn't write.
- **Exit codes:** 0 done, 1 a piece failed `check`, 2 usage error, 3 needs root, 4 the machine is missing something (an old `agetty`, no `setvtrgb`).

## 4. The page

`ttyskin.html` is one self-contained file with no build step and no network use. It opens in Chrome or Edge from disk; other browsers can view and download but not save in place.

- **Open:** pick a pieces folder (or drop one piece's files on the page).
- **View:** the piece drawn with the console's own bitmap font, at the console's size in columns and rows, in its palette. The arrow keys flip between pieces. Toggles: the piece's palette or the default palette; the console's full screen or the art alone; a grid.
- **Edit:**
  - Brush: pick a character and a text and background colour, then click or drag to paint. Paint characters only, colours only, or both.
  - Text: click a cell and type.
  - Select, move, copy and paste a rectangle.
  - Undo and redo.
  - Palette: 16 colour pickers that recolour the art as you change them.
  - Live values: insert a token; the page shows a sample value in its place.
  - Characters the font lacks are outlined in red and listed.
- **Save:** writes `art.txt`, `fg.txt`, `bg.txt` and `palette.txt` back into the piece's folder. Without folder access, it downloads them instead. **New** makes a piece folder; **Duplicate** copies the current one.
- **Font:** the page includes one common console font (8×16, Uni2 Fixed). `ttyskin font export` on a machine produces that machine's font for the page to load instead.
- **Console size:** presets (80×25, 160×50, 240×67, 320×90) or columns and rows typed in.

Later, not in the first version: turning an image into a piece in the page.

## 5. Repository layout

```
ttyskin                        the command (Python, one file)
ttyskin.html                   the page
fonts/uni2-fixed16.json        the default font for the page
systemd/ttyskin-palette.service
pieces/sample/                 the sample piece
docs/SPEC.md                   this file
README.md                      what it does, install, use (Debian/Ubuntu and others in equal sections)
LICENSE
```

Install is copying files: the command to `/usr/local/bin`, the unit to `/etc/systemd/system`. The README gives the exact commands.

## 6. To verify before the first release

On a real console, not in a terminal emulator:

- Which colour sequences the console honours for bright text (`1;3x` or `9x`).
- That `agetty --reload` redraws every console, and what to do when it doesn't (restart the `getty@` units).
- That the palette survives a reboot with the unit ordered after the distribution's own palette unit.
- The default font's licence for bundling.
