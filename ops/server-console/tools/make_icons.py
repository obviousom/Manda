"""Renders the C.O.R.E. arc-reactor icon set (PNG) for the web manifest and the Android app."""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

BG = (2, 7, 13, 255)
CYAN = (0, 212, 255, 255)
CYAN2 = (125, 246, 255, 255)
WHITE = (233, 253, 255, 255)


def reactor(size, scale=1.0, background=True):
    """Draw at 4x then downsample for smooth edges. scale < 1 leaves a safe margin (maskable)."""
    S = size * 4
    img = Image.new("RGBA", (S, S), BG if background else (0, 0, 0, 0))
    c = S / 2
    R = S * 0.46 * scale
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse([c - R * .62, c - R * .62, c + R * .62, c + R * .62], fill=(0, 212, 255, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(S * 0.05)))
    d = ImageDraw.Draw(img)
    # outer segmented ring
    for i in range(10):
        a0 = i * 36 + 4
        d.arc([c - R, c - R, c + R, c + R], a0, a0 + 26, fill=CYAN, width=int(R * 0.13))
    # inner thin ring
    r2 = R * 0.72
    d.ellipse([c - r2, c - r2, c + r2, c + r2], outline=CYAN2, width=max(2, int(R * 0.035)))
    # spokes
    for i in range(3):
        a = math.radians(90 + i * 120)
        d.line([c + math.cos(a) * R * 0.32, c - math.sin(a) * R * 0.32,
                c + math.cos(a) * R * 0.66, c - math.sin(a) * R * 0.66], fill=CYAN, width=int(R * 0.06))
    # core
    r3 = R * 0.3
    d.ellipse([c - r3, c - r3, c + r3, c + r3], fill=CYAN2)
    r4 = R * 0.17
    d.ellipse([c - r4, c - r4, c + r4, c + r4], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    reactor(192).save(os.path.join(out, "icon-192.png"))
    reactor(512).save(os.path.join(out, "icon-512.png"))
    reactor(512, scale=0.72).save(os.path.join(out, "icon-maskable-512.png"))
    print("icons written to", out)
