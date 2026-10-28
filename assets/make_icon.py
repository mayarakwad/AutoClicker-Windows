"""Draws the app icon (a white cursor with a click burst on a blue tile) as
assets/app.ico (Windows), app.icns (macOS .app) and app.png (macOS Dock).

Run from the project folder:  .venv\\Scripts\\python assets\\make_icon.py

Pure Python (no Pillow), so it runs on any OS: each size is rasterized with
supersampling. The .ico uses 32-bit BMP entries, which every Windows version
and Tk can read; the .icns and .png hold PNG data.
"""
import functools
import math
import struct
import zlib
from pathlib import Path

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BLUE = (31, 111, 235)
WHITE = (255, 255, 255)
INK = (12, 30, 66)
TIP = (0.40, 0.27)
ARROW = [TIP, (0.40, 0.80), (0.52, 0.69), (0.61, 0.88), (0.70, 0.84), (0.61, 0.65), (0.77, 0.65)]
OUTLINE = 0.03
RAYS = [(math.cos(math.radians(a)), math.sin(math.radians(a))) for a in (180, 225, 270)]
RAY_FROM, RAY_TO, RAY_HALF_WIDTH = 0.10, 0.21, 0.028
TILE_INSET, TILE_RADIUS = 0.03, 0.22


def _segment_distance(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _inside(px, py, polygon):
    inside = False
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        if (ay > py) != (by > py) and px < ax + (py - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def _in_tile(x, y):
    lo, hi, r = TILE_INSET, 1 - TILE_INSET, TILE_RADIUS
    cx, cy = min(max(x, lo + r), hi - r), min(max(y, lo + r), hi - r)
    return lo <= x <= hi and lo <= y <= hi and math.hypot(x - cx, y - cy) <= r


def color_at(x, y):
    """Color of one point in the unit square, or None where the icon is transparent."""
    if not _in_tile(x, y):
        return None
    edges = zip(ARROW, ARROW[1:] + ARROW[:1])
    if min(_segment_distance(x, y, ax, ay, bx, by) for (ax, ay), (bx, by) in edges) <= OUTLINE:
        return INK
    if _inside(x, y, ARROW):
        return WHITE
    tx, ty = TIP
    for dx, dy in RAYS:
        if _segment_distance(x, y, tx + dx * RAY_FROM, ty + dy * RAY_FROM,
                             tx + dx * RAY_TO, ty + dy * RAY_TO) <= RAY_HALF_WIDTH:
            return WHITE
    return BLUE


@functools.cache
def render(size):
    """Rows of (r, g, b, a), top row first."""
    n = 4 if size <= 64 else 2  # samples per pixel side
    rows = []
    for py in range(size):
        row = []
        for px in range(size):
            colors = [color_at((px + (i + 0.5) / n) / size, (py + (j + 0.5) / n) / size)
                      for i in range(n) for j in range(n)]
            solid = [c for c in colors if c is not None]
            if not solid:
                row.append((0, 0, 0, 0))
                continue
            r, g, b = (round(sum(c[k] for c in solid) / len(solid)) for k in range(3))
            row.append((r, g, b, round(255 * len(solid) / len(colors))))
        rows.append(row)
    return rows


def bmp_entry(size, rows):
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = b"".join(bytes((b, g, r, a)) for row in reversed(rows) for r, g, b, a in row)
    mask = bytes(((size + 31) // 32) * 4 * size)  # all zero: the alpha channel decides
    return header + pixels + mask


def write_ico(path):
    images = [bmp_entry(size, render(size)) for size in SIZES]
    out = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    for size, data in zip(SIZES, images):
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    path.write_bytes(out + b"".join(images))


def png_bytes(rows):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    size = len(rows)
    raw = b"".join(b"\x00" + bytes(channel for pixel in row for channel in pixel) for row in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# macOS icon entries: (type, pixel size); all hold PNG data.
ICNS_ENTRIES = (("icp4", 16), ("icp5", 32), ("ic11", 32), ("ic12", 64), ("ic07", 128),
                ("ic13", 256), ("ic08", 256), ("ic14", 512), ("ic09", 512))


def write_icns(path):
    entries = b"".join(kind.encode() + struct.pack(">I", 8 + len(png)) + png
                       for kind, png in ((kind, png_bytes(render(size))) for kind, size in ICNS_ENTRIES))
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(entries)) + entries)


if __name__ == "__main__":
    here = Path(__file__).parent
    write_ico(here / "app.ico")                          # Windows exe and window icon
    (here / "app.png").write_bytes(png_bytes(render(256)))  # macOS Dock icon when run from source
    write_icns(here / "app.icns")                        # macOS .app icon
    for name in ("app.ico", "app.png", "app.icns"):
        print(f"wrote {here / name} ({(here / name).stat().st_size:,} bytes)")
