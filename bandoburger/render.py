"""Dessin du burger avec Pillow.

render_burger(state) -> bytes PNG
state : dict {cle_ingredient: "free" | "taken" | "done"}
Les couches libres sont dessinées en fantôme, les prises en couleur,
les achetées en couleur avec une petite pastille verte.
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
    "sauce": (222, 82, 38),
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


def draw_oignon(c, ghost):
    lay, d = c.layer()
    color = GHOST_LINE if ghost else COL["oignon"] + (255,)
    for x in (150, 222, 294, 366, 438, 500):
        d.ellipse(_s((x - 30, 230, x + 30, 252)), outline=color, width=7 * S)
    c.put(lay)


def draw_sauce(c, ghost):
    lay, d = c.layer()
    pts = [(110, 212), (530, 212), (530, 226), (496, 228), (482, 246), (466, 228),
           (360, 228), (344, 250), (328, 228), (230, 228), (212, 244), (196, 228), (110, 228)]
    d.polygon(_pts(pts), fill=_fill(ghost, COL["sauce"]),
              outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    c.put(lay)


def draw_top_bun(c, ghost):
    lay, d = c.layer()
    fill = _fill(ghost, COL["pain"])
    d.pieslice(_s((100, 50, 540, 330)), 180, 360, fill=fill,
               outline=GHOST_LINE if ghost else None, width=3 * S if ghost else 0)
    d.rounded_rectangle(_s((100, 178, 540, 214)), radius=_s(16), fill=fill, **_line(ghost))
    if not ghost:
        d.arc(_s((140, 80, 500, 320)), 200, 250, fill=COL["pain_hi"] + (220,), width=12 * S)
        for x, y, a in ((210, 120, -20), (270, 96, -8), (330, 88, 0), (390, 98, 10),
                        (450, 124, 22), (240, 150, -12), (310, 132, 0), (380, 140, 8), (460, 162, 16)):
            seed = Image.new("RGBA", (_s(16), _s(8)), (0, 0, 0, 0))
            ImageDraw.Draw(seed).ellipse((0, 0, _s(16) - 1, _s(8) - 1), fill=COL["sesame"] + (255,))
            seed = seed.rotate(a, expand=True, resample=Image.BICUBIC)
            lay.alpha_composite(seed, (_s(x), _s(y)))
    c.put(lay)


def draw_check(c, x, y):
    lay, d = c.layer()
    d.ellipse(_s((x - 13, y - 13, x + 13, y + 13)), fill=(46, 160, 67, 255), outline=(255, 255, 255, 255), width=2 * S)
    d.line(_pts([(x - 6, y), (x - 1, y + 5), (x + 7, y - 6)]), fill=(255, 255, 255, 255), width=4 * S, joint="curve")
    c.put(lay)


# ordre de dessin : du bas vers le haut, (clé, fonction, y de la pastille)
STACK = [
    ("pain", draw_bottom_bun, 398),
    ("salade", draw_salade, 366),
    ("steak", draw_steak, 327),
    ("cheddar", draw_cheddar, 289),
    ("bacon", draw_bacon, 264),
    ("oignon", draw_oignon, 241),
    ("sauce", draw_sauce, 220),
]


def render_burger(state):
    c = Canvas()
    # ombre portée
    shadow = Image.new("RGBA", c.img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse(_s((110, 414, 530, 444)), fill=(0, 0, 0, 90))
    c.put(shadow.filter(ImageFilter.GaussianBlur(8 * S)))

    for key, fn, _ in STACK:
        fn(c, state.get(key, "free") == "free")
    draw_top_bun(c, state.get("pain", "free") == "free")

    checks = [(k, y) for k, _, y in STACK if state.get(k) == "done"]
    for k, y in checks:
        draw_check(c, 566, y)
    if state.get("pain") == "done":
        draw_check(c, 566, 130)

    out = c.img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
