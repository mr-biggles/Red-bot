"""Dessin du burger avec Pillow.

render_burger(state) -> bytes PNG
state : dict {cle_ingredient: "free" | "taken"}
Les couches libres sont dessinées en fantôme, les prises en couleur.
"""
import io
import math

from PIL import Image, ImageDraw, ImageFilter

S = 2  # suréchantillonnage pour l'anticrénelage
W, H = 640, 470

GHOST_FILL = (150, 150, 150, 40)
GHOST_LINE = (165, 165, 165, 150)

COL = {
    "pain": (228, 150, 58),
    "pain_hi": (246, 190, 110),
    "sesame": (255, 242, 214),
    "steak": (92, 46, 24),
    "steak_line": (60, 28, 14),
    "cheddar": (246, 180, 28),
    "bacon": (190, 58, 38),
    "bacon_fat": (238, 160, 140),
    "oignon": (214, 148, 66),
    "sauce": (240, 146, 84),
    "bbq": (98, 38, 18),
    "cornichon": (104, 140, 42),
    "cornichon_in": (170, 196, 92),
    "cornichon_seed": (232, 236, 190),
    "salade": (96, 172, 58),
    "salade_dk": (66, 132, 40),
}


def _s(v):
    return [int(x * S) for x in v] if isinstance(v, (list, tuple)) else int(v * S)


def _pts(points):
    return [(x * S, y * S) for x, y in points]


def _wave(x0, x1, y, amp, period, step=6):
    pts = []
    x = x0
    while x <= x1:
        pts.append((x, y + amp * math.sin((x - x0) / period * 2 * math.pi)))
        x += step
    pts.append((x1, y + amp * math.sin((x1 - x0) / period * 2 * math.pi)))
    return pts


class Canvas:
    def __init__(self):
        self.img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))

    def layer(self):
        lay = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        return lay, ImageDraw.Draw(lay)

    def put(self, lay):
        self.img = Image.alpha_composite(self.img, lay)


def _fill(ghost, color):
    return GHOST_FILL if ghost else color + (255,)


def _line(ghost):
    return {"outline": GHOST_LINE, "width": 3 * S} if ghost else {}


def draw_bottom_bun(c, ghost):
    lay, d = c.layer()
    d.rounded_rectangle(_s((104, 372, 536, 422)), radius=_s(24), fill=_fill(ghost, COL["pain"]), **_line(ghost))
    if not ghost:
        d.rounded_rectangle(_s((120, 376, 520, 386)), radius=_s(5), fill=COL["pain_hi"] + (170,))
    c.put(lay)


def draw_salade(c, ghost):
    lay, d = c.layer()
    top = _wave(92, 548, 352, 7, 38)
    bottom = list(reversed(_wave(92, 548, 380, 6, 30)))
    d.polygon(_pts(top + bottom), fill=_fill(ghost, COL["salade"]),
              outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    if not ghost:
        for x in range(120, 530, 46):
            d.line(_pts([(x, 360), (x + 18, 372)]), fill=COL["salade_dk"] + (255,), width=3 * S)
    c.put(lay)


def draw_steak(c, ghost):
    lay, d = c.layer()
    d.rounded_rectangle(_s((112, 298, 528, 356)), radius=_s(28), fill=_fill(ghost, COL["steak"]), **_line(ghost))
    if not ghost:
        for x0, y0, x1 in ((150, 316, 210), (250, 330, 330), (370, 314, 430), (180, 340, 230), (420, 338, 490)):
            d.line(_pts([(x0, y0), (x1, y0 - 4)]), fill=COL["steak_line"] + (255,), width=5 * S)
    c.put(lay)


def draw_cheddar(c, ghost):
    lay, d = c.layer()
    pts = [(98, 278), (542, 278), (542, 292), (500, 300), (470, 326), (446, 300),
           (330, 300), (300, 334), (272, 300), (170, 300), (146, 322), (122, 300), (98, 296)]
    d.polygon(_pts(pts), fill=_fill(ghost, COL["cheddar"]),
              outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    c.put(lay)


def draw_bacon(c, ghost):
    lay, d = c.layer()
    top = _wave(108, 532, 252, 6, 70)
    bottom = list(reversed(_wave(108, 532, 276, 6, 70)))
    d.polygon(_pts(top + bottom), fill=_fill(ghost, COL["bacon"]),
              outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    if not ghost:
        d.line(_pts(_wave(118, 522, 264, 6, 70)), fill=COL["bacon_fat"] + (255,), width=4 * S)
    c.put(lay)


FRIED = [(150, 92, 30), (186, 118, 40), (214, 146, 58), (232, 174, 84), (246, 200, 118)]


def draw_oignon(c, ghost):
    """Oignons frits croustillants : un tas de petits copeaux dorés."""
    import random
    rnd = random.Random(7)  # toujours le même dessin
    lay, d = c.layer()
    # base irrégulière du tas
    top = [(x, 232 - rnd.uniform(0, 7)) for x in range(104, 537, 12)]
    base = top + [(536, 254), (104, 254)]
    if ghost:
        d.polygon(_pts(base), fill=GHOST_FILL, outline=GHOST_LINE, width=3 * S)
        c.put(lay)
        return
    d.polygon(_pts(base), fill=FRIED[0] + (255,))
    # copeaux : petits arcs courbés, du plus foncé (dessous) au plus clair (dessus)
    for layer_i, col in enumerate(FRIED[1:]):
        for _ in range(70):
            x = rnd.uniform(108, 532)
            y = rnd.uniform(228, 252) - layer_i * 1.5
            w, h = rnd.uniform(14, 26), rnd.uniform(6, 12)
            a0 = rnd.uniform(0, 360)
            d.arc(_s((x - w / 2, y - h / 2, x + w / 2, y + h / 2)), a0, a0 + rnd.uniform(120, 220),
                  fill=col + (255,), width=int(rnd.uniform(2.5, 4) * S))
    c.put(lay)


def draw_sauce(c, ghost):
    lay, d = c.layer()
    pts = [(110, 192), (530, 192), (530, 206), (496, 208), (482, 226), (466, 208),
           (360, 208), (344, 230), (328, 208), (230, 208), (212, 224), (196, 208), (110, 208)]
    d.polygon(_pts(pts), fill=_fill(ghost, COL["sauce"]),
              outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    c.put(lay)


def draw_cornichon(c, ghost):
    lay, d = c.layer()
    for x in (148, 236, 324, 412, 496):
        box = _s((x - 34, 210, x + 34, 232))
        if ghost:
            d.ellipse(box, fill=GHOST_FILL, outline=GHOST_LINE, width=3 * S)
            continue
        d.ellipse(box, fill=COL["cornichon"] + (255,))
        d.ellipse(_s((x - 27, 213, x + 27, 229)), fill=COL["cornichon_in"] + (255,))
        for dx in (-14, -5, 5, 14):
            d.ellipse(_s((x + dx - 2, 219, x + dx + 2, 223)), fill=COL["cornichon_seed"] + (255,))
    c.put(lay)


def draw_bbq(c, ghost):
    """Filet de sauce BBQ en zigzag par-dessus la sauce burger, avec deux coulures."""
    lay, d = c.layer()
    color = GHOST_LINE if ghost else COL["bbq"] + (255,)
    zig = [(x, 193 if i % 2 == 0 else 207) for i, x in enumerate(range(118, 530, 22))]
    d.line(_pts(zig), fill=color, width=(3 if ghost else 6) * S, joint="curve")
    if not ghost:
        for x in (262, 418):
            d.polygon(_pts([(x - 7, 204), (x + 7, 204), (x + 3, 220), (x, 224), (x - 3, 220)]), fill=color)
    c.put(lay)


def draw_top_bun(c, ghost):
    lay, d = c.layer()
    fill = _fill(ghost, COL["pain"])
    d.pieslice(_s((100, 30, 540, 310)), 180, 360, fill=fill,
               outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    d.rounded_rectangle(_s((100, 158, 540, 194)), radius=_s(16), fill=fill, **_line(ghost))
    if not ghost:
        d.arc(_s((140, 60, 500, 300)), 200, 250, fill=COL["pain_hi"] + (220,), width=12 * S)
        for x, y, a in ((210, 100, -20), (270, 76, -8), (330, 68, 0), (390, 78, 10),
                        (450, 104, 22), (240, 130, -12), (310, 112, 0), (380, 120, 8), (460, 142, 16)):
            seed = Image.new("RGBA", (_s(16), _s(8)), (0, 0, 0, 0))
            ImageDraw.Draw(seed).ellipse((0, 0, _s(16) - 1, _s(8) - 1), fill=COL["sesame"] + (255,))
            seed = seed.rotate(a, expand=True, resample=Image.BICUBIC)
            lay.alpha_composite(seed, (_s(x), _s(y)))
    c.put(lay)


# ordre de dessin : du bas vers le haut
STACK = [
    ("pain", draw_bottom_bun),
    ("salade", draw_salade),
    ("steak", draw_steak),
    ("cheddar", draw_cheddar),
    ("bacon", draw_bacon),
    ("oignon", draw_oignon),
    ("cornichon", draw_cornichon),
    ("sauceburger", draw_sauce),
    ("saucebbq", draw_bbq),
]


def render_burger(state):
    c = Canvas()
    # ombre portée
    shadow = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(_s((110, 414, 530, 444)), fill=(0, 0, 0, 90))
    c.put(shadow.filter(ImageFilter.GaussianBlur(8 * S)))

    for key, fn in STACK:
        fn(c, state.get(key, "free") == "free")
    draw_top_bun(c, state.get("pain", "free") == "free")


    out = c.img.resize((W, H), Image.LANCZOS)
    # recadrage serré et carré autour du burger (affiché en vignette dans Discord)
    x0, y0, x1, y1 = out.getbbox() or (0, 0, W, H)
    side = max(x1 - x0, y1 - y0) + 16
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(out.crop((x0, y0, x1, y1)), ((side - (x1 - x0)) // 2, (side - (y1 - y0)) // 2))
    out = square.resize((320, 320), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
