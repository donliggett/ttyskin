# ttyskin guide

How to make a piece in `ttyskin.html`, use live values, import an image, and put the result on a machine. The README covers installing; the spec ([SPEC.md](SPEC.md)) is the full reference.

## 1. Open your pieces

Open `ttyskin.html` in a browser. It runs from disk, with no server and no network.

- **Open folder** (Chrome, Edge and other Chromium browsers): pick a folder of pieces, or a single piece's folder. **Save** (Ctrl+S) then writes straight back into the piece's files.
- **Open read-only** (any browser): you can view and edit, and **Download** saves the current piece as a `.zip` of its files.
- **New** starts an empty piece, **Duplicate** copies the current one, and **Import image…** makes one from a picture (section 5). With a folder open, each gets its own folder when you save.
- `←` and `→` flip between pieces.

## 2. See it the way the console will

The **View** panel controls the preview:

- **Palette:** the piece's own 16 colors, the Linux default or Ubuntu's.
- **Whole console:** shows the screen at its real size in columns and rows, with the distribution's line above the art and the login prompt below it. Set the size to match your machine (`ttyskin status` on the machine prints it).
- **Grid** and **zoom** for close work.
- **Live values** fills in sample values (section 4).

The page draws with the console's own bitmap font, so what you see is what the console shows. If your machine uses a different console font, run `ttyskin font export -o font.json` there and load the file with **Font…**.

## 3. Draw

Pick a tool from the panel or with its key:

| Tool | Key | Use |
|---|---|---|
| Brush | `B` | Click or drag to paint. Right-click erases. Alt+click picks up a cell's character and colors. |
| Text | `T` | Click a cell and type. Enter goes to the next line at the column you started from; the arrow keys move; Esc stops. |
| Select | `S` | Drag a rectangle. Drag inside it to move it. Ctrl+C, Ctrl+X and Ctrl+V copy, cut and paste; Delete clears it; Esc deselects. |
| Pick | `I` | Click a cell to take its character and colors for the brush. |

- **The brush character:** type it in the box, or click it in **Characters in the font**, which shows everything the console can draw. With the Text tool active and a cursor placed, clicking a character types it.
- **What the brush changes:** characters and colors, characters only (to redraw shapes without touching color), or colors only (to recolor existing art).
- **Text color:** one of the 16 palette slots, or the default (the console's normal text color).
- **Background:** one of slots 0–7, or none. The console only has 8 background colors.
- **Undo and redo:** Ctrl+Z and Ctrl+Y.
- **Pasting text from elsewhere** brings it in with the brush's colors.

### Colors and the palette

A piece can carry its own palette: the 16 colors themselves. **Make piece palette** starts one from the colors on screen; then change any slot with its color picker and watch the art update. **Remove** drops it, and the console's own colors are used.

A palette recolors the whole console, not only the art. Slot 0 is the screen's background and slot 7 the normal text color, so after login the shell uses them too. Keep slot 7 readable on slot 0.

### Checking as you go

The **Check** panel lists anything the console can't show: characters missing from the font (also outlined in red on the art), art wider than the console, tabs, and text in braces that isn't a live value. A piece with nothing listed will pass `ttyskin check`.

## 4. Live values

Live values are filled in on the machine. The login prompt fills in most of them every time it is drawn; ttyskin fills in the IP addresses itself (see below):

| Write | Shows |
|---|---|
| `{host}` | the host name |
| `{ipv4}` | the first IPv4 address: the first global address on an interface that is up and not loopback |
| `{ipv4:eth0}` | the first IPv4 address of one interface (use your interface's name) |
| `{date}`, `{time}` | the date and time |
| `{users}` | the number of logged-in users |
| `{tty}` | the terminal's name, like `tty1` |
| `{os}` | the OS name |

**Addresses are written by ttyskin and kept current by the watcher.** `ttyskin use` writes each address into the art as text. Then `ttyskin-watch.service` (see the README) listens for address changes; when an address shown on screen actually changes, it waits a few seconds for things to settle and redraws the login prompt, at most once every 10 seconds. A Wi-Fi reconnect that comes back with the same address redraws nothing. An interface without an IPv4 address shows `-`. Without the watcher, the addresses stay as they were at the last `use`.

To add one, choose the **Text** tool, click where it should start, and pick it from **insert live value…** (or type it). The value takes the colors of the token's first cell; to color it, paint that cell.

**The value replaces the token, and the two are rarely the same length.** `{host}` is 6 characters, but the host name might be 12. Everything after the value on the same row moves by the difference. So:

- The easy way: put live values at the end of a row, or on a row of their own. Nothing follows them, so nothing moves.
- When something must follow, a border for example, leave room for the real value's length.
- To see the real result, fill in **Sample values** with your machine's actual values (host name, addresses, OS, terminal, users) and turn on **Live values** in View. The page then shows each row exactly as the console will. The page remembers your sample values.

## 5. Import an image

**Import image…**, or dropping an image file on the page, turns a picture into a piece. The dialog shows a live preview in the console font.

**Before you import:**

- **Negative space comes from transparency.** Transparent pixels get no background, and fully transparent cells become plain spaces, so the art sits directly on the console's background. A solid backdrop (white, black or anything else) is treated as part of the picture and painted cell by cell. To leave the background out, remove it first and save a PNG with transparency.
- **Crop first.** The importer scales the whole picture and never cuts anything off. Transparent margins become spaces, but solid margins become colored cells.
- **Bold shapes convert best.** Fine detail and text turn into noise at console resolution; logos, silhouettes and pixel art work well.

**In the dialog:**

- **Width** in columns. The height follows the picture's shape. If that would be taller than the console, the height stops at the console's rows and the width shrinks to match; the dialog says so.
- **Palette:**
  - *From the image* picks the 16 colors that best represent the picture. Pixel art with 16 colors or fewer keeps its colors exactly.
  - *This piece's palette* matches against the open piece's colors and leaves them unchanged.
  - *Linux default* or *Ubuntu default* matches against that palette.
  - Whichever you choose, the piece keeps that palette, so the console shows what the preview showed.
- **Characters:** *blocks* (solid and shaded blocks) suits photos and pixel art; *blocks and lines* adds line and corner shapes for cleaner edges on logos; *every character in the font* tries everything and is slow at large widths.
- **Into:** a new piece, or replace the open one. Ctrl+Z undoes a replace in one step.
- **Pixel art:** set the width to twice the picture's width in pixels. Each pixel then becomes 2 columns by 1 row, which is square on screen.

**After importing,** the result is an ordinary piece. Clean stray cells with the brush, add live values around it, and use Select to move the art if you want it further right or lower than the top-left corner.

## 6. Put it on a machine

On the machine, with your pieces in the folder ttyskin reads (see the README):

```sh
ttyskin list                     # the pieces; * marks the one in use
ttyskin check <name>             # against this machine's font and console size
sudo ttyskin use <name> --dry-run
sudo ttyskin use <name>
```

`use` installs the art and the piece's palette. Then it clears every console waiting at a login prompt and redraws it, so the new art appears at the top straight away. A console where someone is logged in is never cleared; it shows the art the next time its prompt is drawn.

- **Switch:** run `use` with another piece.
- **Turn it off:** `sudo ttyskin off` removes the art and restores the palette the console had before ttyskin first changed it.
- **See what's in use:** `ttyskin status`, including the addresses on screen and whether the watcher is running.

## 7. Keys

| Key | Does |
|---|---|
| `←` `→` | previous / next piece |
| `B` `T` `S` `I` | brush, text, select, pick |
| Ctrl+Z / Ctrl+Y | undo / redo |
| Ctrl+S | save |
| Ctrl+C / Ctrl+X / Ctrl+V | copy / cut / paste (Select) |
| Delete | clear the selection |
| Esc | deselect, or stop typing |
