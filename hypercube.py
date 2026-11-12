#!/usr/bin/env python3
"""ASCII-art screensaver: a rotating 4D hypercube (tesseract) in the terminal.

Press any key to exit.
"""
import argparse
import curses
import math
import time

# 16 vertices: every combination of (+-1, +-1, +-1, +-1).
VERTICES = [tuple(1.0 if (i >> b) & 1 else -1.0 for b in range(4)) for i in range(16)]
# 32 edges: vertex pairs that differ in exactly one coordinate.
EDGES = [(i, j) for i in range(16) for j in range(i + 1, 16) if bin(i ^ j).count("1") == 1]

# Rotation planes (axis pair) and their angular speeds in rad/s. Speeds are
# mutually irrational-ish so the motion doesn't visibly repeat.
ROTATIONS = [((0, 1), 0.31), ((2, 3), 0.47), ((0, 3), 0.23), ((1, 2), 0.17)]

RAMP = ".,-~:;=!*#$@"   # far -> near
D4 = 3.5                # 4D camera distance
D3 = 5.0                # 3D camera distance
CHAR_ASPECT = 2.0       # terminal cells are roughly twice as tall as wide
# Blue -> cyan -> white gradient (xterm-256 indices), far -> near.
GRADIENT_256 = [17, 18, 19, 25, 31, 32, 38, 39, 45, 51, 87, 123, 159, 195, 231]


def rotate(v, t):
    v = list(v)
    for (i, j), w in ROTATIONS:
        c, s = math.cos(w * t), math.sin(w * t)
        v[i], v[j] = v[i] * c - v[j] * s, v[i] * s + v[j] * c
    return v


def project(v, width, height):
    """4D -> 3D -> 2D perspective. Returns (col, row, depth); larger depth is nearer."""
    x, y, z, w = v
    f4 = D4 / (D4 - w)
    x, y, z = x * f4, y * f4, z * f4
    f3 = D3 / (D3 - z)
    scale = min(width / CHAR_ASPECT, height) * 0.16
    col = width / 2 + x * f3 * scale * CHAR_ASPECT
    row = height / 2 - y * f3 * scale
    return col, row, z + 0.5 * w


def render(t, width, height):
    """Return {(row, col): (char, shade)} for the frame at time t; shade is 0 (far) .. 1 (near)."""
    pts = [project(rotate(v, t), width, height) for v in VERTICES]
    dmin = min(p[2] for p in pts)
    dspan = max(p[2] for p in pts) - dmin or 1.0
    cells = {}
    zbuf = {}

    def plot(r, c, d, ch=None):
        if 0 <= r < height and 0 <= c < width and d > zbuf.get((r, c), -1.0):
            zbuf[(r, c)] = d
            cells[(r, c)] = (ch or RAMP[min(int(d * len(RAMP)), len(RAMP) - 1)], d)

    for i, j in EDGES:
        (x0, y0, d0), (x1, y1, d1) = pts[i], pts[j]
        d0, d1 = (d0 - dmin) / dspan, (d1 - dmin) / dspan
        steps = max(int(max(abs(x1 - x0), abs(y1 - y0))), 1)
        for k in range(steps + 1):
            u = k / steps
            plot(round(y0 + (y1 - y0) * u), round(x0 + (x1 - x0) * u), d0 + (d1 - d0) * u)

    for x, y, d in pts:
        d = (d - dmin) / dspan
        plot(round(y), round(x), d + 1e-6, "O" if d > 0.5 else "o")
    return cells


def setup_colors(enabled):
    """Return a function mapping shade (0..1) to a curses attribute."""
    if enabled and curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        if curses.COLORS >= 256:
            for n, color in enumerate(GRADIENT_256, start=1):
                curses.init_pair(n, color, bg)
            pairs = [curses.color_pair(n) for n in range(1, len(GRADIENT_256) + 1)]
            pairs[-1] |= curses.A_BOLD
        else:
            for n, color in enumerate((curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_WHITE), start=1):
                curses.init_pair(n, color, bg)
            pairs = [curses.color_pair(1), curses.color_pair(2), curses.color_pair(3) | curses.A_BOLD]
    else:
        pairs = [curses.A_DIM, curses.A_NORMAL, curses.A_BOLD]
    return lambda shade: pairs[min(int(shade * len(pairs)), len(pairs) - 1)]


def main(stdscr, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    attr_for = setup_colors(not args.no_color)
    frame_time = 1.0 / args.fps
    start = time.monotonic()

    while True:
        frame_start = time.monotonic()
        key = stdscr.getch()
        if key not in (-1, curses.KEY_RESIZE):
            return

        height, width = stdscr.getmaxyx()
        stdscr.erase()
        for (r, c), (ch, shade) in render((frame_start - start) * args.speed, width, height).items():
            try:
                stdscr.addstr(r, c, ch, attr_for(shade))
            except curses.error:
                pass  # writing the bottom-right cell raises; harmless
        stdscr.refresh()

        time.sleep(max(0.0, frame_time - (time.monotonic() - frame_start)))


def cli():
    parser = argparse.ArgumentParser(description="Rotating ASCII tesseract screensaver. Press any key to exit.")
    parser.add_argument("--fps", type=float, default=30.0, help="frames per second (default: 30)")
    parser.add_argument("--speed", type=float, default=1.0, help="rotation speed multiplier (default: 1.0)")
    parser.add_argument("--no-color", action="store_true", help="disable colors")
    args = parser.parse_args()
    if args.fps <= 0:
        parser.error("--fps must be positive")
    try:
        curses.wrapper(main, args)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
