#!/usr/bin/env python3
"""Draw the show cover (3000x3000 RGB PNG) into docs/cover.png.

  python tools/make_cover.py            # paper style, matching the video (default)
  python tools/make_cover.py --dark     # the original dark network style
  python tools/make_cover.py --reel     # 1080x1920 Instagram Reel cover (docs/cover-reel.png),
                                        # key content inside the 3:4 grid crop
  python tools/make_cover.py --banners  # LinkedIn Page cover (1128x191 at 3x) and YouTube
                                        # channel banner (2560x1440, safe area 1546x423)

Run locally; needs Pillow, the Inter / Inter Display fonts (dark) and Liberation Sans,
the metric twin of the video's Arimo (paper). The PNG is committed, so the GitHub
workflow never has to run this.
"""
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "cover.png"
FONTS = Path("/usr/share/fonts/opentype/inter")
S = 3000
TAGLINE = "Supply chain planning & design news  ·  Nordics, DACH & beyond"
LIB = Path("/usr/share/fonts/truetype/liberation")

INK = (12, 20, 33)
INK_2 = (20, 34, 54)
WHITE = (244, 241, 234)
AMBER = (242, 163, 58)
TEAL = (59, 196, 180)
MUTED = (138, 152, 170)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def dark():
    img = Image.new("RGB", (S, S), INK)
    d = ImageDraw.Draw(img)

    # Soft vertical gradient for depth.
    for y in range(S):
        t = y / S
        c = tuple(int(INK_2[i] * (1 - t) + INK[i] * t) for i in range(3))
        d.line([(0, y), (S, y)], fill=c)

    # A three-tier supply network in the upper half: sources -> hubs -> markets.
    rnd = random.Random(43)
    tiers = [
        [(330 + i * 300, 330 + rnd.randint(-40, 40)) for i in range(8)],
        [(620 + i * 600, 820 + rnd.randint(-60, 60)) for i in range(4)],
        [(260 + i * 250, 1330 + rnd.randint(-50, 50)) for i in range(11)],
    ]
    net = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    n = ImageDraw.Draw(net)
    for a in tiers[0]:
        for b in sorted(tiers[1], key=lambda p: abs(p[0] - a[0]))[:2]:
            n.line([a, b], fill=MUTED + (90,), width=6)
    for b in tiers[1]:
        for c in sorted(tiers[2], key=lambda p: abs(p[0] - b[0]))[:4]:
            n.line([b, c], fill=MUTED + (90,), width=6)
    # One highlighted flow, source to market.
    path = [tiers[0][5], tiers[1][2], tiers[2][7]]
    n.line(path, fill=AMBER + (255,), width=16, joint="curve")
    for p in tiers[0]:
        n.ellipse([p[0] - 22, p[1] - 22, p[0] + 22, p[1] + 22], fill=TEAL + (255,))
    for p in tiers[1]:
        n.rounded_rectangle([p[0] - 46, p[1] - 46, p[0] + 46, p[1] + 46], radius=14, fill=WHITE + (255,))
    for p in tiers[2]:
        n.ellipse([p[0] - 16, p[1] - 16, p[0] + 16, p[1] + 16], outline=WHITE + (220,), width=7)
    for p in path:
        n.ellipse([p[0] - 34, p[1] - 34, p[0] + 34, p[1] + 34], fill=AMBER + (255,))
    glow = net.filter(ImageFilter.GaussianBlur(18))
    img.paste(glow, (0, 0), glow)
    img.paste(net, (0, 0), net)

    d = ImageDraw.Draw(img)
    left = 230
    d.text((left, 1640), "THE", font=font("InterDisplay-Bold.otf", 190), fill=AMBER)
    d.text((left - 18, 1810), "PLANNING", font=font("InterDisplay-Black.otf", 430), fill=WHITE)
    d.text((left - 18, 2210), "DESK", font=font("InterDisplay-Black.otf", 430), fill=WHITE)
    d.rectangle([left, 2715, left + 380, 2735], fill=AMBER)
    d.text((left, 2770), TAGLINE, font=font("Inter-Medium.otf", 80), fill=MUTED)
    return img


# Paper palette from video/src/theme.js
PAPER, PAPER2, GRID = (238, 227, 222), (230, 217, 211), (214, 201, 195)
TEAL_INK, ORANGE, SAGE, TEXT, SUB = (23, 67, 75), (232, 86, 42), (167, 188, 182), (43, 37, 35), (75, 68, 65)


def lib(bold, size):
    return ImageFont.truetype(str(LIB / ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")), size)


def paper():
    """Editorial paper style: demand columns under a stepped capacity line, the show mark
    and a big two-line title, as in the video's opening card."""
    img = Image.new("RGB", (S, S), PAPER)
    d = ImageDraw.Draw(img)
    x0, x1, base, top = 230, 2770, 1420, 300
    for g in (0.25, 0.5, 0.75):
        y = base - g * (base - top)
        d.line([(x0, y), (x1, y)], fill=GRID, width=5)
    n = 18
    step = (x1 - x0) / n
    bw = step * 0.62
    for i in range(n):
        v = 0.30 + 0.022 * i + 0.07 * math.sin(i / 1.9)
        bx = x0 + i * step + (step - bw) / 2
        hot = i == 13
        d.rectangle([bx, base - v * (base - top), bx + bw, base], fill=ORANGE if hot else (TEAL_INK if i > 13 else SAGE))
    cap = [(x0, 0.48), (x0 + 0.33 * (x1 - x0), 0.48), (x0 + 0.33 * (x1 - x0), 0.66), (x0 + 0.70 * (x1 - x0), 0.66),
           (x0 + 0.70 * (x1 - x0), 0.86), (x1, 0.86)]
    pts = [(x, base - v * (base - top)) for x, v in cap]
    for (ax, ay), (bx2, by) in zip(pts, pts[1:]):
        L = math.hypot(bx2 - ax, by - ay)
        k = 0
        while k < L:
            e = min(k + 46, L)
            d.line([(ax + (bx2 - ax) * k / L, ay + (by - ay) * k / L), (ax + (bx2 - ax) * e / L, ay + (by - ay) * e / L)], fill=TEXT, width=12)
            k += 76
    d.line([(x0, base), (x1, base)], fill=GRID, width=8)

    left = 230
    # The show mark: three staggered planning bars.
    m, u = (left, 1600), 7.2
    for bx, by, bw2 in ((2, 5, 22), (10, 16, 26), (6, 27, 16)):
        d.rounded_rectangle([m[0] + bx * u, m[1] + by * u, m[0] + (bx + bw2) * u, m[1] + (by + 8) * u], radius=12, fill=ORANGE)
    d.text((left + 330, 1645), "THE", font=lib(True, 200), fill=ORANGE)
    d.text((left - 14, 1860), "Planning", font=lib(True, 440), fill=TEAL_INK)
    d.text((left - 14, 2310), "Desk", font=lib(True, 440), fill=TEAL_INK)
    d.rectangle([left, 2790, left + 380, 2810], fill=ORANGE)
    d.text((left, 2850), TAGLINE, font=lib(False, 82), fill=SUB)
    return img


def reel():
    """9:16 Reel cover. Instagram's profile grid crops it to the middle 1080x1440 (3:4),
    so the mark, title and chart sit inside y 240..1680."""
    W, H = 1080, 1920
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    x0, x1, base, top = 90, 990, 830, 290
    for g in (0.25, 0.5, 0.75):
        y = base - g * (base - top)
        d.line([(x0, y), (x1, y)], fill=GRID, width=3)
    n = 12
    step = (x1 - x0) / n
    bw = step * 0.62
    for i in range(n):
        v = 0.30 + 0.033 * i + 0.07 * math.sin(i / 1.4)
        bx = x0 + i * step + (step - bw) / 2
        d.rectangle([bx, base - v * (base - top), bx + bw, base], fill=ORANGE if i == 8 else (TEAL_INK if i > 8 else SAGE))
    cap = [(x0, 0.50), (x0 + 0.35 * (x1 - x0), 0.50), (x0 + 0.35 * (x1 - x0), 0.68), (x0 + 0.68 * (x1 - x0), 0.68),
           (x0 + 0.68 * (x1 - x0), 0.88), (x1, 0.88)]
    pts = [(x, base - v * (base - top)) for x, v in cap]
    for (ax, ay), (bx2, by) in zip(pts, pts[1:]):
        L = math.hypot(bx2 - ax, by - ay)
        k = 0
        while k < L:
            e = min(k + 18, L)
            d.line([(ax + (bx2 - ax) * k / L, ay + (by - ay) * k / L), (ax + (bx2 - ax) * e / L, ay + (by - ay) * e / L)], fill=TEXT, width=5)
            k += 30
    d.line([(x0, base), (x1, base)], fill=GRID, width=4)

    left = 90
    m, u = (left, 935), 3.0
    for bx, by, bw2 in ((2, 5, 22), (10, 16, 26), (6, 27, 16)):
        d.rounded_rectangle([m[0] + bx * u, m[1] + by * u, m[0] + (bx + bw2) * u, m[1] + (by + 8) * u], radius=6, fill=ORANGE)
    d.text((left + 140, 952), "THE", font=lib(True, 86), fill=ORANGE)
    d.text((left - 6, 1050), "Planning", font=lib(True, 196), fill=TEAL_INK)
    d.text((left - 6, 1250), "Desk", font=lib(True, 196), fill=TEAL_INK)
    d.rectangle([left, 1500, left + 160, 1508], fill=ORANGE)
    d.text((left, 1530), "Supply chain planning & design news", font=lib(False, 40), fill=SUB)
    d.text((left, 1582), "Nordics, DACH & beyond", font=lib(False, 40), fill=SUB)
    return img


def _chart(d, x0, x1, base, top, n, hot, dash, width, line):
    for g in (0.25, 0.5, 0.75):
        y = base - g * (base - top)
        d.line([(x0, y), (x1, y)], fill=GRID, width=line)
    step = (x1 - x0) / n
    bw = step * 0.62
    for i in range(n):
        v = 0.30 + (0.5 / n) * i + 0.07 * math.sin(i / 1.6)
        bx = x0 + i * step + (step - bw) / 2
        d.rectangle([bx, base - v * (base - top), bx + bw, base], fill=ORANGE if i == hot else (TEAL_INK if i > hot else SAGE))
    cap = [(x0, 0.50), (x0 + 0.35 * (x1 - x0), 0.50), (x0 + 0.35 * (x1 - x0), 0.68), (x0 + 0.68 * (x1 - x0), 0.68),
           (x0 + 0.68 * (x1 - x0), 0.88), (x1, 0.88)]
    pts = [(x, base - v * (base - top)) for x, v in cap]
    for (ax, ay), (bx2, by) in zip(pts, pts[1:]):
        L = math.hypot(bx2 - ax, by - ay)
        k = 0
        while k < L:
            e = min(k + dash, L)
            d.line([(ax + (bx2 - ax) * k / L, ay + (by - ay) * k / L), (ax + (bx2 - ax) * e / L, ay + (by - ay) * e / L)], fill=TEXT, width=width)
            k += dash * 1.65
    d.line([(x0, base), (x1, base)], fill=GRID, width=line + 1)


def _wordmark(d, x, y, size):
    """Mark + one-line 'The Planning Desk' at font size `size`, top-left at (x, y). Returns its width."""
    u = size / 40 * 1.25
    for bx, by, bw2 in ((2, 5, 22), (10, 16, 26), (6, 27, 16)):
        d.rounded_rectangle([x + bx * u, y + by * u, x + (bx + bw2) * u, y + (by + 8) * u], radius=max(2, int(u * 1.5)), fill=ORANGE)
    d.text((x + 44 * u, y - size * 0.02), "The Planning Desk", font=lib(True, size), fill=TEAL_INK)
    return 44 * u + d.textlength("The Planning Desk", font=lib(True, size))


def linkedin_banner():
    # LinkedIn Page cover: 1128x191, drawn at 3x. The logo overlaps the bottom-left on
    # desktop, so the text starts at x=760 (at 3x) and the chart sits at the far right.
    W, H = 3384, 573
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    _wordmark(d, 760, 140, 150)
    d.text((764, 360), TAGLINE, font=lib(False, 54), fill=SUB)
    _chart(d, 2640, 3290, 500, 90, 8, 5, 22, 7, 3)
    return img


def youtube_banner():
    # YouTube: 2560x1440; only the centre 1546x423 shows on every device (TV shows all).
    W, H = 2560, 1440
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    size, tag = 116, lib(False, 46)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    w = _wordmark(probe, 0, 0, size)
    x = (W - w) / 2
    _wordmark(d, x, 610, size)
    tw = d.textlength(TAGLINE, font=tag)
    d.text(((W - tw) / 2, 800), TAGLINE, font=tag, fill=SUB)
    d.rectangle([(W - 220) / 2, 770, (W + 220) / 2, 778], fill=ORANGE)
    # Charts outside the safe area, seen on desktop and TV.
    _chart(d, 110, 470, 1000, 470, 6, 4, 16, 6, 3)
    _chart(d, 2090, 2450, 1000, 470, 6, 4, 16, 6, 3)
    return img


def main():
    if "--banners" in sys.argv:
        for name, fn in (("banner-linkedin.png", linkedin_banner), ("banner-youtube.png", youtube_banner)):
            out = ROOT / "docs" / name
            fn().save(out, "PNG", optimize=True)
            print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
        return
    img = dark() if "--dark" in sys.argv else reel() if "--reel" in sys.argv else paper()
    default = ROOT / "docs" / "cover-reel.png" if "--reel" in sys.argv else OUT
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else default
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
