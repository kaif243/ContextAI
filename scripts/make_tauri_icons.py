"""One-off helper to create a minimal valid set of Tauri icons.

We do not bundle real brand assets in the repo; these placeholders let the
Tauri config validate and the bundler run. Replace with real icons before a
production release.
"""
import os
import struct
import zlib

OUT = os.path.join(os.path.dirname(__file__), "..", "src", "tauri", "icons")
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)


def make_png(w, h, rgba=(20, 184, 166, 255)):
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t, d):
        c = zlib.crc32(t + d)
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", c)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    raw = b""
    for _ in range(h):
        raw += b"\x00" + bytes(list(rgba) * w)
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_ico(w=32, h=32, rgba=(20, 184, 166, 255)):
    header = struct.pack("<HHH", 0, 1, 1)
    data = b""
    for _ in range(h):
        data += bytes(list(rgba) * w)
    bmp_size = 40 + len(data)
    entry = struct.pack("<BBBBHHII", w & 0xFF, h & 0xFF, 0, 0, 1, 32, bmp_size, 22)
    dib = struct.pack(
        "<IIIHHIIIIII", 40, w, h * 2, 1, 32, 0, len(data), 0, 0, 0, 0
    )
    return header + entry + dib + data


for name, sz in (
    ("32x32.png", (32, 32)),
    ("128x128.png", (128, 128)),
    ("128x128@2x.png", (256, 256)),
):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(make_png(*sz))

with open(os.path.join(OUT, "icon.ico"), "wb") as f:
    f.write(make_ico())

png128 = make_png(128, 128)
icns_header = b"icns" + struct.pack(">I", 8 + 8 + len(png128))
entry = b"ic07" + struct.pack(">I", 8 + len(png128)) + png128
with open(os.path.join(OUT, "icon.icns"), "wb") as f:
    f.write(icns_header + entry)

print("wrote:", sorted(os.listdir(OUT)))
