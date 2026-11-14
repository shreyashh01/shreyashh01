"""Composite the transparent koi GIF onto an animated pond background."""
import sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageSequence

src, dst = sys.argv[1], sys.argv[2]
koi = Image.open(src)
W, H = koi.size
N = koi.n_frames
dur = koi.info.get("duration", 70)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
# deep water gradient (top-left lighter -> bottom-right darker)
t = (xx / W * 0.4 + yy / H * 0.6)
base = np.stack([12 + 10 * (1 - t), 48 + 40 * (1 - t), 78 + 50 * (1 - t)], -1)

# static decor: lily pads + blossoms, drawn once at 2x then downsampled
S = 2
deco = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
d = ImageDraw.Draw(deco)
def pad(cx, cy, r, notch):
    box = [(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S]
    d.pieslice(box, notch + 25, notch + 335, fill=(36, 120, 78, 255), outline=(22, 84, 56, 255), width=2)
for cx, cy, r, n in [(64, 70, 34, 30), (440, 90, 26, 200), (96, 440, 40, 110), (430, 430, 30, 300), (470, 250, 20, 60)]:
    pad(cx, cy, r, n)
for cx, cy in [(100, 435), (437, 428)]:
    for a in range(0, 360, 45):
        px, py = cx + 11 * math.cos(math.radians(a)), cy + 11 * math.sin(math.radians(a))
        d.ellipse([(px - 6) * S, (py - 6) * S, (px + 6) * S, (py + 6) * S], fill=(255, 140, 190, 255))
    d.ellipse([(cx - 5) * S, (cy - 5) * S, (cx + 5) * S, (cy + 5) * S], fill=(255, 226, 120, 255))
deco = deco.resize((W, H), Image.LANCZOS)
# soft drop shadow under the decor
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
shadow.putalpha(deco.getchannel("A").filter(ImageFilter.GaussianBlur(4)).point(lambda v: int(v * 0.45)))

# rounded-corner mask
mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=28, fill=255)

frames = []
for i, f in enumerate(ImageSequence.Iterator(koi)):
    ph = 2 * math.pi * i / N
    # looping caustic light: integer spatial frequencies keep it seamless
    c = (np.sin(xx / 23 + ph) + np.sin(yy / 19 - ph) + np.sin((xx + yy) / 31 + 2 * ph)
         + np.sin((xx - yy) / 27 - 2 * ph))
    c = np.clip((c - 1.2) / 2.8, 0, 1) ** 2
    img = base + c[..., None] * np.array([40, 70, 70])
    bg = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    bg.alpha_composite(shadow, (2, 3))
    bg.alpha_composite(deco)
    # expanding ripple rings, one per loop
    ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    for k, (rx, ry) in enumerate([(150, 340), (360, 180)]):
        p = ((i / N) + k * 0.5) % 1
        r = 8 + 60 * p
        rd.ellipse([rx - r, ry - r * 0.6, rx + r, ry + r * 0.6], outline=(200, 235, 255, int(110 * (1 - p))), width=2)
    bg.alpha_composite(ring)
    bg.alpha_composite(f.convert("RGBA"))
    frames.append(bg)

# one shared palette so colours don't flicker between frames
sheet = Image.new("RGB", (W, H * 4))
for j, k in enumerate([0, N // 4, N // 2, 3 * N // 4]):
    sheet.paste(frames[k].convert("RGB"), (0, j * H))
pal = sheet.quantize(255, method=Image.MEDIANCUT, dither=Image.NONE)
out = []
for fr in frames:
    q = fr.convert("RGB").quantize(palette=pal, dither=Image.NONE)
    # transparent corners: use palette index 255
    arr = np.array(q)
    arr[np.array(mask) == 0] = 255
    p = Image.fromarray(arr, "P")
    p.putpalette(pal.getpalette()[:765] + [0, 0, 0])
    out.append(p)
out[0].save(dst, save_all=True, append_images=out[1:], duration=dur, loop=0, transparency=255, disposal=2)
