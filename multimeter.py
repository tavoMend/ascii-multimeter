"""Renderiza un multímetro digital 3D en ASCII girando 360° y lo empaqueta como SVG animado.

Modelo inspirado en un multímetro de bolsillo clásico: carcasa naranja, panel gris,
LCD azul retroiluminado, selector rotativo y puntas de prueba conectadas.
Ray marching sobre SDFs (numpy) + sombreado lambert -> rampa de caracteres por material.

Uso:  py multimeter.py   ->  multimeter.svg
"""
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "multimeter.svg"
OUT_TERMINAL = ROOT / "multimeter-terminal.svg"

FONT = "'Fira Code','JetBrains Mono','Cascadia Code',Consolas,'Courier New',monospace"
BG = "#020a09"
DIM = "#0d4d45"
MID = "#00c896"
GREEN = "#00ff9c"
CYAN = "#00e5ff"
ICE = "#b8fcff"

READING = "115.0 V~"   # lo que muestra el LCD: 115 V de corriente alterna

COLS, ROWS = 80, 56
CW, CH = 7, 12            # px por celda en el SVG
FRAMES = 36
DURATION = 5.4            # s por vuelta
VIEW_W = 4.3              # unidades de mundo visibles a lo ancho
VIEW_H = VIEW_W / COLS * ROWS * CH / CW
CENTER_Y = -0.2
TILT = np.radians(10)
CELL_X = VIEW_W / COLS                      # ancho de una columna sobre el panel
CELL_Y = VIEW_H / ROWS / np.cos(TILT)       # alto de una fila sobre el panel (compensa la inclinación)

# ---------- materiales y colores ----------
HOUSING, FACE, LCD, KNOB, KNOB_BAR, BLUE, JACK_RED, JACK_BLACK, PROBE_RED, PROBE_BLACK = range(1, 11)

COLORS = {
    "od": "#7a3a06", "o": "#ff8a1f", "oh": "#ffc07a",      # carcasa y perilla naranja
    "f": "#26302f", "f2": "#3e4b4d",                       # panel gris oscuro
    "lcd": "#3d6bff", "lcdd": "#0a1550",                   # LCD azul y sus dígitos
    "bl": "#2f6bff", "blh": "#8fb0ff",                     # botones azules
    "w": "#e8eef0", "y": "#ffd23f",                        # serigrafía
    "jr": "#d81e3a", "jk": "#55605f",                      # jacks
    "r": "#ff3b4f", "rd": "#a3172a", "k": "#7d8b8e", "kd": "#3a4446",  # puntas
}

# rampa de caracteres y clases de color por material (de oscuro a claro)
MATERIAL_LOOK = {
    HOUSING:     (":;+*#%@", ["od", "od", "o", "o", "oh"]),
    FACE:        ("..:", ["f", "f", "f2"]),
    LCD:         (".:;", ["f", "f2"]),           # paredes del hueco del LCD
    KNOB:        ("=+*#", ["od", "o", "o"]),
    KNOB_BAR:    ("#%@@", ["o", "oh", "oh"]),
    BLUE:        ("+*#%@", ["bl", "bl", "blh"]),
    JACK_RED:    ("oO@", ["jr"]),
    JACK_BLACK:  ("oO@", ["jk"]),
    PROBE_RED:   (":+*#%@", ["rd", "r", "r"]),
    PROBE_BLACK: (":+*#%@", ["kd", "k", "k"]),
}

# ---------- LCD: fuente 3x5 ----------
GLYPHS = {
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
    ".": [".", ".", ".", ".", "#"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "~": [".....", ".#...", "#.#.#", "...#.", "....."],
    " ": ["."] * 5,
}


def lcd_bitmap(text):
    rows = [""] * 5
    for ch in text:
        for r in range(5):
            rows[r] += GLYPHS[ch][r] + "."
    rows = ["." + r for r in rows]
    if len(rows[0]) % 2:  # ancho par: el LCD queda alineado con la rejilla de columnas
        rows = [r + "." for r in rows]
    pad = "." * len(rows[0])
    return [pad] + rows + [pad]


LCD_BMP = lcd_bitmap(READING)
LCD_Y = 1.0
LCD_HX = len(LCD_BMP[0]) * CELL_X / 2
LCD_HY = len(LCD_BMP) * CELL_Y / 2
DIAL_Y = -0.42
JACK_Y = -1.4
POINTER_DEG = 35  # la perilla apunta a V~ 200


# ---------- serigrafía (decals) sobre el panel, botones y perilla ----------
def build_decals():
    decals = {FACE: {}, BLUE: {}, KNOB_BAR: {}}

    def put(mat, text, x, y, cls, align="c"):
        x0 = x - len(text) * CELL_X / 2 if align == "c" else x - len(text) * CELL_X if align == "r" else x
        ix0, iy = int(np.floor(x0 / CELL_X + 0.5)), int(np.floor(y / CELL_Y))
        for k, ch in enumerate(text):
            decals[mat][(ix0 + k, iy)] = (ch, cls)

    put(FACE, "tavoMend", -0.42, 1.5, "o")
    put(FACE, "DMM-115", 0.5, 1.5, "w")
    put(BLUE, "H", -0.6, 0.42, "w")
    put(BLUE, "*", 0.62, 0.44, "w")
    for deg in np.linspace(215, -35, 16):  # puntos de las posiciones del selector
        a = np.radians(deg)
        put(FACE, "•", 0.64 * np.cos(a), DIAL_Y + 0.64 * np.sin(a), "w")

    def label(text, deg, r, cls, align="c"):
        a = np.radians(deg)
        put(FACE, text, r * np.cos(a), DIAL_Y + r * np.sin(a), cls, align)

    label("OFF", 90, 0.82, "y")
    label("V~", 35, 0.84, "w", "l")
    label("V=", 145, 0.84, "w", "r")
    label("A", -5, 0.8, "w", "l")
    label("Ω", 192, 0.8, "w", "r")
    label("°C", -40, 0.8, "w", "l")
    put(FACE, "CAT II", -0.55, -1.0, "w")
    put(FACE, "10A", -0.55, -1.16, "y")
    put(FACE, "COM", 0.0, -1.16, "w")
    put(FACE, "VΩmA", 0.55, -1.16, "y")
    a = np.radians(POINTER_DEG)
    put(KNOB_BAR, "•", 0.36 * np.cos(a), DIAL_Y + 0.36 * np.sin(a), "w")
    return decals


DECALS = build_decals()


# ---------- SDF primitivas ----------
def length(v):
    return np.sqrt((v * v).sum(-1))


def sd_round_box(p, c, b, r):
    q = np.abs(p - c) - (np.array(b) - r)
    return length(np.maximum(q, 0)) + np.minimum(q.max(-1), 0) - r


def sd_box(p, c, b):
    return sd_round_box(p, c, b, 0.0)


def sd_cyl_z(p, cx, cy, r, z0, z1):
    q = p - np.array([cx, cy, (z0 + z1) / 2])
    d = np.stack([length(q[:, :2]) - r, np.abs(q[:, 2]) - (z1 - z0) / 2], -1)
    return np.minimum(d.max(-1), 0) + length(np.maximum(d, 0))


def sd_capsule(p, a, b, r):
    a, b = np.array(a), np.array(b)
    pa, ba = p - a, b - a
    h = np.clip((pa @ ba) / (ba @ ba), 0, 1)
    return length(pa - h[:, None] * ba) - r


def rotate_xy(q, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.stack([c * q[:, 0] + s * q[:, 1], -s * q[:, 0] + c * q[:, 1], q[:, 2]], -1)


def rotate_yz(q, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    return np.stack([q[:, 0], c * q[:, 1] + s * q[:, 2], -s * q[:, 1] + c * q[:, 2]], -1)


def scene(p):
    """Devuelve (distancia, material) en espacio objeto. El frente mira a +z."""
    outer = sd_round_box(p, (0, 0, 0), (1.1, 1.85, 0.3), 0.22)
    face_cut = sd_box(p, (0, 0.02, 0.45), (0.9, 1.68, 0.19))       # panel hundido: piso en z=0.26
    d = np.maximum(outer, -face_cut)
    mat = np.where(-face_cut > outer, FACE, HOUSING)
    lcd_cut = sd_box(p, (0, LCD_Y, 0.26), (LCD_HX, LCD_HY, 0.05))
    mat = np.where(-lcd_cut > d, LCD, mat)
    d = np.maximum(d, -lcd_cut)

    def add(dist, m):
        nonlocal d, mat
        mat = np.where(dist < d, m, mat)
        d = np.minimum(d, dist)

    # botones H y luz
    add(sd_round_box(p, (-0.6, 0.42, 0.28), (0.17, 0.12, 0.05), 0.04), BLUE)
    add(sd_cyl_z(p, 0.62, 0.44, 0.11, 0.2, 0.33), BLUE)
    # selector: disco + barra apuntando a V~
    add(sd_cyl_z(p, 0, DIAL_Y, 0.5, 0.2, 0.36), KNOB)
    bar = rotate_xy(p - np.array([0, DIAL_Y, 0.42]), POINTER_DEG - 90)
    add(sd_round_box(bar, (0, 0, 0), (0.11, 0.48, 0.07), 0.04), KNOB_BAR)
    # jacks 10A / COM / VΩmA
    for x, m in ((-0.55, JACK_RED), (0.0, JACK_BLACK), (0.55, JACK_RED)):
        add(sd_cyl_z(p, x, JACK_Y, 0.12, 0.2, 0.31), m)
    # puntas: negra en COM, roja en VΩmA
    for x, end, m in ((0.0, (-0.45, -2.3, 0.85), PROBE_BLACK), (0.55, (0.95, -2.3, 0.85), PROBE_RED)):
        knee = (x, JACK_Y - 0.08, 0.62)
        add(sd_capsule(p, (x, JACK_Y, 0.3), knee, 0.085), m)
        add(sd_capsule(p, knee, end, 0.045), m)
    # soporte trasero abierto
    stand = rotate_yz(p - np.array([0, -0.55, -0.52]), -14.8)
    add(sd_round_box(stand, (0, 0, 0), (0.5, 0.88, 0.03), 0.02), HOUSING)
    return d, mat


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def render(theta):
    world_to_obj = rot_y(-theta) @ rot_x(-TILT)

    def sdf(pw):
        return scene(pw @ world_to_obj.T)

    xs = (np.arange(COLS) + 0.5) / COLS * VIEW_W - VIEW_W / 2
    ys = CENTER_Y + VIEW_H / 2 - (np.arange(ROWS) + 0.5) / ROWS * VIEW_H
    gx, gy = np.meshgrid(xs, ys)
    ro = np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 6.0)], -1)
    rd = np.array([0, 0, -1.0])

    t = np.zeros(len(ro))
    hit = np.zeros(len(ro), bool)
    for _ in range(140):
        p = ro + t[:, None] * rd
        d, _ = sdf(p)
        hit |= d < 1e-3
        t = np.where(hit, t, t + d * 0.9)
        if (hit | (t > 12)).all():
            break

    p = ro + t[:, None] * rd
    _, mat = sdf(p)
    e = 2e-3
    n = np.stack([
        sdf(p + [e, 0, 0])[0] - sdf(p - [e, 0, 0])[0],
        sdf(p + [0, e, 0])[0] - sdf(p - [0, e, 0])[0],
        sdf(p + [0, 0, e])[0] - sdf(p - [0, 0, e])[0],
    ], -1)
    n /= np.maximum(length(n)[:, None], 1e-9)
    light = np.array([-0.55, 0.5, 0.67])
    light /= np.linalg.norm(light)
    shade = np.clip(0.1 + 0.9 * np.clip(n @ light, 0, 1), 0, 0.999)

    po = p @ world_to_obj.T
    no = n @ world_to_obj.T
    bh, bw = len(LCD_BMP), len(LCD_BMP[0])

    chars, classes = [], []
    for i in range(len(ro)):
        if not hit[i]:
            chars.append(" ")
            classes.append("")
            continue
        m, s = mat[i], shade[i]
        front = no[i, 2] > 0.6
        if m == LCD and front:
            col = int((po[i, 0] + LCD_HX) / (2 * LCD_HX) * bw)
            row = int((LCD_Y + LCD_HY - po[i, 1]) / (2 * LCD_HY) * bh)
            lit = LCD_BMP[min(bh - 1, max(0, row))][min(bw - 1, max(0, col))] == "#"
            chars.append("█")
            classes.append("lcdd" if lit else "lcd")
            continue
        if front and m in DECALS:
            key = (int(np.floor(po[i, 0] / CELL_X)), int(np.floor(po[i, 1] / CELL_Y)))
            if key in DECALS[m]:
                ch, cls = DECALS[m][key]
                chars.append(ch)
                classes.append(cls)
                continue
        ramp, tones = MATERIAL_LOOK[m]
        chars.append(ramp[int(s * len(ramp))])
        classes.append(tones[int(s * len(tones))])
    return chars, classes


def frame_svg(chars, classes, idx):
    rows = []
    for r in range(ROWS):
        row_c = chars[r * COLS:(r + 1) * COLS]
        row_k = classes[r * COLS:(r + 1) * COLS]
        if all(c == " " for c in row_c):
            continue
        spans, cur, buf = [], None, ""
        for c, k in zip(row_c, row_k):
            if c != " " and k != cur:
                if buf:
                    spans.append((cur, buf))
                cur, buf = k, ""
            buf += c
        spans.append((cur, buf.rstrip()))
        lead = len(spans[0][1]) - len(spans[0][1].lstrip())
        spans[0] = (spans[0][0], spans[0][1].lstrip())
        body = "".join(
            f'<tspan class="{k}">{escape(s)}</tspan>' if k else escape(s) for k, s in spans if s
        )
        width = sum(len(s) for _, s in spans)
        rows.append(
            f'<text x="{lead * CW}" y="{(r + 1) * CH}" textLength="{width * CW}" '
            f'lengthAdjust="spacing" xml:space="preserve">{body}</text>'
        )
    delay = idx * DURATION / FRAMES - DURATION
    return f'<g class="f" style="animation-delay:{delay:.3f}s">{"".join(rows)}</g>'


def main():
    frames = []
    for i in range(FRAMES):
        frames.append(frame_svg(*render(2 * np.pi * i / FRAMES), i))
        print(f"\rframe {i + 1}/{FRAMES}", end="", flush=True)
    print()

    ox, oy = 44, 64
    w, h = COLS * CW + ox * 2, ROWS * CH + oy + 56
    pct = 100 / FRAMES
    palette = " ".join(f".{k} {{ fill: {v}; }}" for k, v in COLORS.items())
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Multímetro digital en ASCII girando 360 grados, marcando 115 V de corriente alterna">
<title>Multímetro ASCII — 115.0 V~ — spin 360°</title>
<defs>
  <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>
    <stop offset=".5" stop-color="{CYAN}" stop-opacity=".12"/>
    <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="glow" cx=".5" cy=".45" r=".5">
    <stop offset="0" stop-color="#ff8a1f" stop-opacity=".07"/>
    <stop offset="1" stop-color="#ff8a1f" stop-opacity="0"/>
  </radialGradient>
  <pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#000" opacity=".3"/>
  </pattern>
  <clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>
</defs>
<style>
  text {{ font-family: {FONT}; font-size: 11px; font-weight: 700; fill: {MID}; }}
  {palette}
  .f {{ opacity: 0; animation: show {DURATION}s steps(1) infinite; }}
  @keyframes show {{ 0% {{ opacity: 1; }} {pct:.4f}% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
  .scan {{ animation: sweep 4s linear infinite; }}
  @keyframes sweep {{ from {{ transform: translateY(-120px); }} to {{ transform: translateY({h}px); }} }}
  .ui {{ font-size: 13px; fill: {MID}; font-weight: 400; }}
  .ui .c {{ fill: {CYAN}; }}
  .lbl {{ font-size: 11px; fill: {DIM}; letter-spacing: 2px; font-weight: 400; }}
  .cur {{ fill: {GREEN}; animation: blink 1s steps(1) infinite; }}
  @keyframes blink {{ 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .f, .scan, .cur {{ animation: none; }} .f:first-of-type {{ opacity: 1; }}
  }}
</style>
<g clip-path="url(#c)">
  <rect width="{w}" height="{h}" fill="{BG}"/>
  <rect width="{w}" height="{h}" fill="url(#glow)"/>
  <text class="ui" x="24" y="34">~ $ <tspan class="c">./multimeter --spin 360</tspan></text>
  <rect class="cur" x="242" y="22" width="8" height="15"/>
  <g transform="translate({ox},{oy})">
{chr(10).join(frames)}
  </g>
  <text class="lbl" x="24" y="{h - 20}">// AC VOLTAGE · 115.0 V · 60 Hz · RANGE 200</text>
  <text class="lbl" x="{w - 24}" y="{h - 20}" text-anchor="end">{FRAMES} FRAMES</text>
  <rect class="scan" width="{w}" height="120" fill="url(#scan)"/>
  <rect width="{w}" height="{h}" fill="url(#lines)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{DIM}"/>
</svg>
'''
    OUT.write_text(svg, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT).as_posix()}  ({len(svg.encode()) // 1024} KB)")

    # versión terminal: lo mismo que muestra multimeter_cli.py, sin efectos encima
    tw, th = (COLS + 4) * CW, (ROWS + 5) * CH
    plain = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{tw}" height="{th}" viewBox="0 0 {tw} {th}" role="img" aria-label="Multímetro digital en ASCII girando 360 grados, marcando 115 V de corriente alterna">
<title>Multímetro ASCII — 115.0 V~ — spin 360°</title>
<style>
  text {{ font-family: {FONT}; font-size: 11px; font-weight: 700; fill: {MID}; }}
  {palette}
  .f {{ opacity: 0; animation: show {DURATION}s steps(1) infinite; }}
  @keyframes show {{ 0% {{ opacity: 1; }} {pct:.4f}% {{ opacity: 0; }} 100% {{ opacity: 0; }} }}
  .c {{ fill: {CYAN}; }}
  .ft {{ fill: {DIM}; }}
  @media (prefers-reduced-motion: reduce) {{ .f {{ animation: none; }} .f:first-of-type {{ opacity: 1; }} }}
</style>
<rect width="{tw}" height="{th}" fill="#0c0c0c"/>
<text x="{2 * CW}" y="{CH}" xml:space="preserve">~ $ <tspan class="c">./multimeter --spin 360</tspan></text>
<g transform="translate({2 * CW},{2 * CH})">
{chr(10).join(frames)}
</g>
<text class="ft" x="{2 * CW}" y="{(ROWS + 4) * CH}">// AC 115.0 V - 60 Hz - RANGE 200</text>
</svg>
'''
    OUT_TERMINAL.write_text(plain, encoding="utf-8")
    print(f"{OUT_TERMINAL.relative_to(ROOT).as_posix()}  ({len(plain.encode()) // 1024} KB)")


if __name__ == "__main__":
    main()
