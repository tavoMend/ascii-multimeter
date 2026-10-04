"""Reproduce el multímetro ASCII girando dentro de la terminal (cmd, PowerShell, Windows Terminal).

Uso:  py multimeter_cli.py [--fps 8]      Ctrl+C para salir
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from multimeter import CYAN, COLS, DIM, FRAMES, GREEN, ICE, MID, READING, ROWS, render  # noqa: E402

COLORS = {
    "d": DIM, "m": MID, "b": CYAN, "h": ICE,
    "s": "#0a3a33", "g": GREEN, "j": "#8a9a98",
    "y": "#ffc531", "yd": "#8a6410", "r": "#ff4d6d", "k": "#3f7f76",
}


def ansi(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"\x1b[38;2;{r};{g};{b}m"


def build_frame(chars, classes):
    lines = [ansi(MID) + "  ~ $ " + ansi(CYAN) + "./multimeter --spin 360" + "\x1b[0m", ""]
    for r in range(ROWS):
        out, cur = ["  "], None
        for c, k in zip(chars[r * COLS:(r + 1) * COLS], classes[r * COLS:(r + 1) * COLS]):
            if c != " " and k != cur:
                out.append(ansi(COLORS.get(k, MID)))
                cur = k
            out.append(c)
        lines.append("".join(out).rstrip() + "\x1b[0m\x1b[K")
    lines.append("")
    lines.append(ansi(DIM) + "  // AC 115 V - 60 Hz  -  Ctrl+C para salir" + "\x1b[0m\x1b[K")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fps", type=float, default=FRAMES / 5.4)
    args = ap.parse_args()

    os.system("")  # activa las secuencias ANSI en la consola de Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    # caché: renderizar los 36 frames toma ~15 s; se regenera si cambia el modelo
    model = Path(__file__).resolve().parent / "multimeter.py"
    cache = Path(__file__).resolve().parent / ".multimeter_frames.json"
    frames = None
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("mtime") == model.stat().st_mtime:
            frames = data["frames"]
    if frames is None:
        frames = []
        for i in range(FRAMES):
            frames.append(build_frame(*render(2 * np.pi * i / FRAMES, READING)))
            print(f"\rcalibrando multimetro... {i + 1}/{FRAMES}", end="", flush=True)
        cache.write_text(json.dumps({"mtime": model.stat().st_mtime, "frames": frames}), encoding="utf-8")

    sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[2J")  # pantalla alterna, sin cursor
    try:
        i = 0
        while True:
            sys.stdout.write("\x1b[H" + frames[i % FRAMES])
            sys.stdout.flush()
            time.sleep(1 / args.fps)
            i += 1
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
