"""
Generate app icons for Articulate desktop app.

Outputs:
  build-resources/icon.png   — 1024x1024 source PNG
  build-resources/icon.ico   — multi-resolution Windows icon
  build-resources/icon.icns  — macOS icon set

Run from project root:
  python scripts/create_icons.py
"""

import io
import struct
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow not found. Install it: uv pip install Pillow")
    sys.exit(1)

try:
    import icnsutil
except ImportError:
    print("icnsutil not found. Install it: uv pip install icnsutil")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "build-resources"
OUT_DIR.mkdir(exist_ok=True)

SIZE = 1024
BG_COLOR = (79, 70, 229)       # indigo-600  #4F46E5
BUBBLE_COLOR = (255, 255, 255)  # white
TEXT_COLOR = (79, 70, 229)      # indigo — matches bg so "A" pops from bubble


# ---------------------------------------------------------------------------
# Draw the 1024x1024 source image
# ---------------------------------------------------------------------------
def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # --- Rounded-square background ---
    radius = size // 5
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG_COLOR)

    # --- Speech bubble ---
    # Bubble occupies ~65% of the canvas, centred slightly above middle
    pad = int(size * 0.17)
    tail_h = int(size * 0.12)
    bx0 = pad
    by0 = pad
    bx1 = size - pad
    by1 = size - pad - tail_h
    br = int(size * 0.08)
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=br, fill=BUBBLE_COLOR)

    # Tail: a small triangle at the bottom-left of the bubble
    tail_x = bx0 + int(size * 0.14)
    tail_points = [
        (tail_x, by1),                        # left attach on bubble bottom
        (tail_x + int(size * 0.12), by1),      # right attach
        (bx0 + int(size * 0.06), by1 + tail_h),  # tip
    ]
    draw.polygon(tail_points, fill=BUBBLE_COLOR)

    # --- Letter "A" centred in the bubble ---
    bubble_cx = (bx0 + bx1) // 2
    bubble_cy = (by0 + by1) // 2

    font_size = int(size * 0.38)
    font = None
    # Try system fonts; fall back to Pillow's default
    for candidate in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(candidate).exists():
            try:
                font = ImageFont.truetype(candidate, font_size)
                break
            except Exception:
                pass

    letter = "A"
    if font:
        bbox = draw.textbbox((0, 0), letter, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = bubble_cx - tw // 2 - bbox[0]
        ty = bubble_cy - th // 2 - bbox[1] - int(size * 0.02)
        draw.text((tx, ty), letter, font=font, fill=TEXT_COLOR)
    else:
        # Pillow default font — tiny but better than nothing
        draw.text((bubble_cx, bubble_cy), letter, fill=TEXT_COLOR, anchor="mm")

    return img


# ---------------------------------------------------------------------------
# Save PNG
# ---------------------------------------------------------------------------
png_path = OUT_DIR / "icon.png"
src = draw_icon(SIZE)
src.save(png_path, format="PNG")
print(f"  icon.png   -> {png_path}")


# ---------------------------------------------------------------------------
# Save ICO (multi-resolution)
# Draw each size independently for crisp results, then bundle.
# ---------------------------------------------------------------------------
ico_sizes = [16, 24, 32, 48, 64, 128, 256]
ico_frames = [draw_icon(s).convert("RGBA") for s in ico_sizes]
ico_path = OUT_DIR / "icon.ico"

# Write a raw ICO container manually so all sizes are included.
# Format: 6-byte header + N * 16-byte dir entries + N * image data blobs

def _png_blob(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

blobs = [_png_blob(f) for f in ico_frames]
n = len(blobs)
header = struct.pack("<HHH", 0, 1, n)  # reserved=0, type=1 (ICO), count=n

dir_entries = b""
offset = 6 + n * 16
for img, blob in zip(ico_frames, blobs):
    w, h = img.size
    w_byte = w if w < 256 else 0
    h_byte = h if h < 256 else 0
    dir_entries += struct.pack("<BBBBHHII",
        w_byte, h_byte,  # width, height (0 = 256)
        0,               # color count (0 = no palette)
        0,               # reserved
        1,               # color planes
        32,              # bits per pixel
        len(blob),       # size of image data
        offset,          # offset of image data
    )
    offset += len(blob)

with open(ico_path, "wb") as f:
    f.write(header + dir_entries + b"".join(blobs))

print(f"  icon.ico  -> {ico_path}")


# ---------------------------------------------------------------------------
# Save ICNS
# ---------------------------------------------------------------------------
# icnsutil expects a dict of {size_label: PIL.Image or bytes}
# Standard macOS sizes: 16, 32, 64, 128, 256, 512, 1024
icns_sizes = {
    "ic04": 16,
    "ic05": 32,
    "ic07": 128,
    "ic08": 256,
    "ic09": 512,
    "ic10": 1024,
    "ic11": 32,   # @2x of ic04 (32px)
    "ic12": 64,   # @2x of ic05 (64px)
    "ic13": 256,  # @2x of ic07 (256px)
    "ic14": 512,  # @2x of ic08 (512px)
}

icns_img = icnsutil.IcnsFile()
seen: dict[int, bytes] = {}


for key, px in icns_sizes.items():
    if px not in seen:
        frame = draw_icon(px).convert("RGBA")
        buf = io.BytesIO()
        frame.save(buf, format="PNG")
        seen[px] = buf.getvalue()
    icns_img.add_media(key, data=seen[px])

icns_path = OUT_DIR / "icon.icns"
icns_img.write(str(icns_path))
print(f"  icon.icns -> {icns_path}")

print("\nDone. All icons written to build-resources/")
