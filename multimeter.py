"""Renderiza un multímetro 3D en ASCII girando 360° y lo empaqueta como SVG animado.

Ray marching sobre SDFs (numpy), sombreado lambert -> rampa de caracteres.
Uso:  py multimeter.py   ->  multimeter.svg
"""
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "multimeter.svg"

FONT = "'Fira Code','JetBrains Mono','Cascadia Code',Consolas,'Courier New',monospace"
BG = "#020a09"
DIM = "#0d4d45"
MID = "#00c896"
GREEN = "#00ff9c"
CYAN = "#00e5ff"
ICE = "#b8fcff"

READING = "115V~"    # lo que muestra el display: 115 V de corriente alterna (~ = AC)

COLS, ROWS = 72, 48
CW, CH = 7, 12            # px por celda
FRAMES = 36
DURATION = 5.4            # s por vuelta
VIEW_W = 4.4              # unidades de mundo visibles a lo ancho
VIEW_H = VIEW_W / COLS * ROWS * CH / CW
CENTER_Y = -0.38
TILT = np.radians(14)

# materiales
BODY, SCREEN, DIAL, BUTTON, JACK, RED, BLACK, BUMPER, POINTER = range(1, 10)

# rampa de caracteres y clases de color por material (de oscuro a claro)
MATERIAL_LOOK = {
    BODY:   (".,:;+*", ["d", "d", "m", "m", "b"]),
    SCREEN: (":;+", ["d"]),
    BUMPER: (":;+*#%@", ["yd", "yd", "y", "y"]),
    DIAL:   ("+*#%@@", ["b", "b", "h", "h"]),
    BUTTON: (";+*#%", ["m", "b", "h"]),
    JACK:   ("oO@", ["j"]),
    RED:    (":+*#%@", ["r"]),
    BLACK:  (":+*#%@", ["k"]),
}

# fuente 3x5 para el display
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
        g = GLYPHS[ch]
        for r in range(5):
            rows[r] += g[r] + "."
    pad = "." * len(rows[0])
    return [pad] + rows + [pad]


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


SCR_C, SCR_B = (0.0, 0.95, 0.30), (0.672, 0.39, 0.09)  # 22x7 celdas: 1 pixel del LCD por carácter


def scene(p):
    """Devuelve (distancia, material) en espacio objeto."""
    body = sd_round_box(p, (0, 0.2, 0), (0.98, 1.53, 0.30), 0.12)
    recess = sd_box(p, SCR_C, SCR_B)
    shell = np.maximum(body, -recess)
    mat = np.where(-recess > body, SCREEN, BODY)
    d = shell

    def add(dist, m):
        nonlocal d, mat
        mat = np.where(dist < d, m, mat)
        d = np.minimum(d, dist)

    add(sd_round_box(p, (0, 0.2, 0), (1.1, 1.65, 0.17), 0.15), BUMPER)
    add(sd_round_box(p, (0, 0.05, -0.3), (0.72, 1.0, 0.06), 0.04), BUTTON)  # tapa de batería
    add(sd_round_box(p, (0, 1.25, -0.33), (0.5, 0.08, 0.05), 0.03), DIAL)   # soporte
    add(sd_cyl_z(p, 0, -0.28, 0.56, 0.0, 0.34), BUTTON)            # aro de la perilla
    add(sd_cyl_z(p, 0, -0.28, 0.46, 0.0, 0.44), DIAL)
    add(sd_box(p, (0, -0.06, 0.46), (0.05, 0.2, 0.04)), POINTER)
    for x in (-0.48, 0.0, 0.48):
        add(sd_round_box(p, (x, 0.43, 0.3), (0.16, 0.06, 0.05), 0.03), BUTTON)
    for x in (-0.6, 0.0, 0.6):
        add(sd_cyl_z(p, x, -1.07, 0.11, 0.0, 0.38), JACK)
    # puntas de prueba: cable + mango
    for sx, m in ((-1, RED), (1, BLACK)):
        jack = (0.6 * sx, -1.07, 0.38)
        knee = (0.95 * sx, -1.85, 0.75)
        tip = (1.05 * sx, -2.45, 0.95)
        add(sd_capsule(p, jack, knee, 0.05), m)
        add(sd_capsule(p, knee, tip, 0.1), m)
    return d, mat


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def render(theta, reading):
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
    for _ in range(120):
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
    light = np.array([-0.6, 0.5, 0.65])
    light /= np.linalg.norm(light)
    shade = np.clip(0.1 + 0.9 * np.clip(n @ light, 0, 1), 0, 0.999)

    po = p @ world_to_obj.T
    no = n @ world_to_obj.T
    bmp = lcd_bitmap(reading)
    bh, bw = len(bmp), len(bmp[0])

    chars, classes = [], []
    for i in range(len(ro)):
        if not hit[i]:
            chars.append(" ")
            classes.append("")
            continue
        m, s = mat[i], shade[i]
        if m == SCREEN and no[i, 2] > 0.7:
            u = (po[i, 0] - (SCR_C[0] - SCR_B[0])) / (2 * SCR_B[0])
            v = ((SCR_C[1] + SCR_B[1]) - po[i, 1]) / (2 * SCR_B[1])
            lit = bmp[min(bh - 1, max(0, int(v * bh)))][min(bw - 1, max(0, int(u * bw)))] == "#"
            ch, cls = ("#", "g") if lit else (".", "s")
        elif m == POINTER:
            ch, cls = "#", "g"
        else:
            # cada material tiene su propia rampa: así las piezas se distinguen
            # aunque reciban la misma luz
            ramp, tones = MATERIAL_LOOK.get(m, MATERIAL_LOOK[BODY])
            ch = ramp[int(s * len(ramp))]
            cls = tones[int(s * len(tones))]
        chars.append(ch)
        classes.append(cls)
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
        theta = 2 * np.pi * i / FRAMES
        frames.append(frame_svg(*render(theta, READING), i))
        print(f"\rframe {i + 1}/{FRAMES}", end="", flush=True)
    print()

    ox, oy = 48, 64
    w, h = COLS * CW + ox * 2, ROWS * CH + oy + 56
    pct = 100 / FRAMES
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Multímetro en ASCII girando 360 grados">
<title>Multímetro ASCII — spin 360°</title>
<defs>
  <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>
    <stop offset=".5" stop-color="{CYAN}" stop-opacity=".14"/>
    <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="glow" cx=".5" cy=".5" r=".5">
    <stop offset="0" stop-color="{CYAN}" stop-opacity=".09"/>
    <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
  </radialGradient>
  <pattern id="lines" width="4" height="4" patternUnits="userSpaceOnUse">
    <rect width="4" height="1" fill="#000" opacity=".35"/>
  </pattern>
  <clipPath id="c"><rect width="{w}" height="{h}" rx="14"/></clipPath>
</defs>
<style>
  text {{ font-family: {FONT}; font-size: 11px; font-weight: 700; fill: {MID}; }}
  .d {{ fill: {DIM}; }} .m {{ fill: {MID}; }} .b {{ fill: {CYAN}; }} .h {{ fill: {ICE}; }}
  .s {{ fill: #0a3a33; }} .g {{ fill: {GREEN}; }} .j {{ fill: #8a9a98; }}
  .y {{ fill: #ffc531; }} .yd {{ fill: #8a6410; }}
  .r {{ fill: #ff4d6d; }} .k {{ fill: #3f7f76; }}
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
  <text class="lbl" x="24" y="{h - 20}">// AC VOLTAGE · 115 V · 60 Hz · AUTO RANGE</text>
  <text class="lbl" x="{w - 24}" y="{h - 20}" text-anchor="end">{FRAMES} FRAMES</text>
  <rect class="scan" width="{w}" height="120" fill="url(#scan)"/>
  <rect width="{w}" height="{h}" fill="url(#lines)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="{DIM}"/>
</svg>
'''
    OUT.write_text(svg, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT).as_posix()}  ({len(svg.encode()) // 1024} KB)")


if __name__ == "__main__":
    main()
