"""Programmatic SVG storyboard panels for Between the Lines.

A panel is a quick film storyboard sketch. It is drawn from three things:

* a composition template (what is in the frame),
* a camera angle (where the camera is: low, eye level or high), and
* what each character does: where they look (`gaze`) and what they are doing (`actions`).

The angle changes the drawing the way it changes a real shot. A low camera looks up, so figures
loom, the ceiling shows and verticals lean. A high camera looks down, so figures shrink and the
floor takes over the frame. Gaze is a dashed red eyeline with an arrowhead, and actions are
visible poses (holding a door, reaching out, arms pulled in, head lowered, turned away).

This module only produces plain SVG. Shapes carry `data-sk` attributes. In the browser,
`sketch.py` redraws those shapes with Rough.js so they look hand-drawn. Without Rough.js the same
SVG is still a clean, readable drawing. The saved demo and live results share this code.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

W, H = 320, 180
ANGLE_IDS = ("low", "eye_level", "high")
TEMPLATE_IDS = ("medium_two_shot", "single_medium", "ots_close_up", "wide_empty_space")

PAPER = "#FBFAF7"
WALL, WALL_DARK, CEILING, FLOOR = "#EEF0F2", "#E1E5EA", "#F6F7F9", "#D5DAE0"
PENCIL, TILE, GLASS, DOOR_LEAF = "#69737F", "#A9B2BD", "#D5E8F7", "#B7C0CB"
INK, ACCENT, GHOST = "#18212C", "#C0392B", "#7F8B99"
SKIN, HAIR = "#F3E6D8", "#2B2F36"
CHAR_COLOR = {"A": "#7A808A", "B": "#6F95CC"}

# Head and body proportions (fractions of figure height). Seen from below the head
# is small and the body tapers upward; seen from above the head is large and the
# shoulders look wide over narrow feet.
_BODY = {
    "low": {"head": 0.100, "wt": 0.25, "wb": 0.34},
    "eye_level": {"head": 0.115, "wt": 0.30, "wb": 0.26},
    "high": {"head": 0.150, "wt": 0.36, "wb": 0.22},
}
_SHOT_TAG = {"medium_two_shot": "MS", "single_medium": "MS", "ots_close_up": "OTS CU", "wide_empty_space": "WS"}
_ANGLE_TAG = {"low": "LOW", "eye_level": "EYE", "high": "HIGH"}

# Where a hand grips the door, and where a character looks when told to look at it.
_DOOR_HAND = {"eye_level": (262.0, 74.0), "low": (257.0, 118.0), "high": (271.0, 24.0)}
_DOOR_EYE = {"eye_level": (272.0, 36.0), "low": (270.0, 50.0), "high": (271.0, 24.0)}


# ------------------------------------------------------------- element helpers

def _f(v) -> str:
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def _el(tag: str, sk: str | None, fs: str | None, **attrs) -> str:
    out = [f"<{tag}"]
    if sk:
        out.append(f' data-sk="{sk}"')
    if fs:
        out.append(f' data-fs="{fs}"')
    for key, value in attrs.items():
        if value is not None:
            out.append(f' {key.replace("_", "-")}="{_f(value)}"')
    out.append("/>")
    return "".join(out)


def _pts(points) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def rect(x, y, w, h, fill="none", stroke=None, sw=1.6, sk="bg", fs=None, **kw):
    return _el("rect", sk, fs, x=float(x), y=float(y), width=float(w), height=float(h), fill=fill,
               stroke=stroke, stroke_width=float(sw) if stroke else None, **kw)


def poly(points, fill="none", stroke=None, sw=1.6, sk="bg", fs=None, **kw):
    return _el("polygon", sk, fs, points=_pts(points), fill=fill, stroke=stroke,
               stroke_width=float(sw) if stroke else None, **kw)


def circ(cx, cy, r, fill="none", stroke=None, sw=1.6, sk="s", fs=None, **kw):
    return _el("circle", sk, fs, cx=float(cx), cy=float(cy), r=float(r), fill=fill,
               stroke=stroke, stroke_width=float(sw) if stroke else None, **kw)


def ell(cx, cy, rx, ry, fill="none", stroke=None, sw=1.6, sk="s", fs=None, **kw):
    return _el("ellipse", sk, fs, cx=float(cx), cy=float(cy), rx=float(rx), ry=float(ry), fill=fill,
               stroke=stroke, stroke_width=float(sw) if stroke else None, **kw)


def line(x1, y1, x2, y2, stroke=PENCIL, sw=1.6, dash=None, sk="bg", **kw):
    return _el("line", sk, None, x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), stroke=stroke,
               stroke_width=float(sw), stroke_dasharray=dash, **kw)


def path(d, fill="none", stroke=None, sw=1.6, sk="s", fs=None, **kw):
    return _el("path", sk, fs, d=d, fill=fill, stroke=stroke, stroke_width=float(sw) if stroke else None, **kw)


def text(x, y, content, size=9.0, fill=INK, anchor="middle", weight=700):
    return (
        f'<text x="{_f(float(x))}" y="{_f(float(y))}" text-anchor="{anchor}" font-family="sans-serif" '
        f'font-size="{_f(float(size))}" font-weight="{weight}" fill="{fill}">{content}</text>'
    )


def _check_angle(angle: str) -> None:
    if angle not in ANGLE_IDS:
        raise ValueError(f"unknown angle: {angle!r}")


def _unit(dx: float, dy: float) -> tuple[float, float]:
    d = math.hypot(dx, dy)
    return (dx / d, dy / d) if d else (0.0, 0.0)


def _label(cx: float, cy: float, letter: str, r: float) -> str:
    return circ(cx, cy, r, "#fff", INK, 1.3, sk="fine") + text(cx, cy + r * 0.38, letter, r * 1.25)


# --------------------------------------------------------------- figure drawing

@dataclass
class _Fig:
    """Where one standing character is in the panel."""
    cx: float
    base: float
    h: float
    angle: str

    def __post_init__(self):
        b = _BODY[self.angle]
        self.r = self.h * b["head"]
        self.cy = self.base - self.h + self.r              # head centre
        self.sy = self.cy + self.r * 1.25                  # shoulder line
        self.wt, self.wb = self.h * b["wt"], self.h * b["wb"]
        self.hip = self.sy + (self.base - self.sy) * 0.52
        self.wh = (self.wt + self.wb) / 2 * 0.85


def _limb(p0, p1, w):
    nx, ny = _unit(p1[1] - p0[1], -(p1[0] - p0[0]))
    return [(p0[0] + nx * w / 2, p0[1] + ny * w / 2), (p1[0] + nx * w / 2, p1[1] + ny * w / 2),
            (p1[0] - nx * w / 2, p1[1] - ny * w / 2), (p0[0] - nx * w / 2, p0[1] - ny * w / 2)]


def _arm(points, w, fill) -> str:
    out = [poly(_limb(a, b, w), fill, INK, 1.4, sk="fine") for a, b in zip(points, points[1:])]
    out.append(circ(points[-1][0], points[-1][1], w * 0.62, SKIN, INK, 1.3, sk="fine"))
    return "".join(out)


def _nose(cx, cy, rx, ry, ux, uy) -> str:
    """A small wedge on the head that shows which way the face points, plus an eye."""
    ang = math.atan2(uy, ux)

    def edge(a, k):
        return cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k

    out = [poly([edge(ang - 0.45, 0.98), edge(ang, 1.34), edge(ang + 0.45, 0.98)], SKIN, INK, 1.4, sk="fine")]
    if rx >= 7:
        ex, ey = edge(ang - 0.35, 0.55)
        out.append(circ(ex, ey, max(1.1, rx * 0.075), INK, sk="fine"))
    return "".join(out)


def _gaze_arrow(f: _Fig, look, action: str = "stand") -> str:
    """A dashed red eyeline from the head to `look` = (x, y, stop_distance)."""
    if not look:
        return ""
    tx, ty, stop = look
    if action == "head_down":
        ty += abs(tx - f.cx) * 0.3
    ux, uy = _unit(tx - f.cx, ty - f.cy)
    sx, sy = f.cx + ux * f.r * 1.55, f.cy + uy * f.r * 1.55
    ex, ey = tx - ux * stop, ty - uy * stop
    if math.hypot(ex - sx, ey - sy) < 9:
        return ""
    head = 7.5
    bx, by = ex - ux * head, ey - uy * head
    return (
        line(sx, sy, bx, by, ACCENT, 1.7, "5 4", sk="s")
        + poly([(ex, ey), (bx - uy * head * 0.42, by + ux * head * 0.42), (bx + uy * head * 0.42, by - ux * head * 0.42)],
               ACCENT, sk="fine")
    )


def _figure(f: _Fig, char: str, look=None, action: str = "stand", reach=None, ghost: bool = False, shadow: bool = True) -> str:
    """One full-length character. `base` may be below the frame (cropped figure)."""
    cx, r, sy, base, hip = f.cx, f.r, f.sy, f.base, f.hip
    turn = action == "turn_away"
    wt = f.wt * (0.8 if turn else 1.0)
    wh, wb = f.wh, f.wb
    aw = max(3.0, f.h * 0.075)
    cloth = "none" if ghost else CHAR_COLOR.get(char, "#777")
    ink = GHOST if ghost else INK
    dash = "4 3" if ghost else None
    sw = 1.5 if ghost else 1.9

    ux, uy = _unit(look[0] - cx, look[1] - f.cy) if look else (0.0, 0.0)
    hx, hy = cx, f.cy
    if action == "head_down":
        hy += r * 0.3
        hx += (1 if ux >= 0 else -1) * r * 0.18

    out: list[str] = []
    if shadow and not ghost and base <= H - 2:
        out.append(ell(cx, base, wb * 0.95, max(3.0, f.h * 0.035), "#000", sk="s", opacity=0.13))

    gap_h, gap_b = wh * 0.12, wb * 0.18
    for s in (-1, 1):
        out.append(poly([(cx + s * wh / 2, hip), (cx + s * gap_h / 2, hip), (cx + s * gap_b / 2, base), (cx + s * wb / 2, base)],
                        cloth, ink, sw, sk="fine" if ghost else "s", stroke_dasharray=dash))
    rr = wt * 0.28
    out.append(rect(cx - r * 0.36, f.cy, r * 0.72, sy - f.cy + 2, "none" if ghost else SKIN, ink, sw, sk="fine", stroke_dasharray=dash))
    out.append(path(
        f"M{_f(cx - wh / 2)} {_f(hip)} L{_f(cx - wt / 2)} {_f(sy + rr)} Q{_f(cx - wt / 2)} {_f(sy)} {_f(cx - wt / 2 + rr)} {_f(sy)} "
        f"L{_f(cx + wt / 2 - rr)} {_f(sy)} Q{_f(cx + wt / 2)} {_f(sy)} {_f(cx + wt / 2)} {_f(sy + rr)} L{_f(cx + wh / 2)} {_f(hip)} Z",
        cloth, ink, sw, sk="fine" if ghost else "s", stroke_dasharray=dash))

    if not ghost:
        sh_l = (cx - wt / 2 + aw * 0.45, sy + aw * 0.6)
        sh_r = (cx + wt / 2 - aw * 0.45, sy + aw * 0.6)
        hang_y = min(hip, sy + f.h * 0.30)
        hang = {-1: (cx - wt / 2 - aw * 0.1, hang_y), 1: (cx + wt / 2 + aw * 0.1, hang_y)}
        shoulder = {-1: sh_l, 1: sh_r}
        busy = None
        if action in ("hold_door", "reach_out"):
            tx, ty = reach if reach else (cx + (1 if ux >= 0 else -1) * f.h * 0.5, sy + f.h * 0.2)
            busy = 1 if tx >= cx else -1
            sx0, sy0 = shoulder[busy]
            dx, dy = tx - sx0, ty - sy0
            length = min(math.hypot(dx, dy), f.h * 0.62)
            vx, vy = _unit(dx, dy)
            hand = (sx0 + vx * length, sy0 + vy * length)
            elbow = (sx0 + vx * length * 0.5, sy0 + vy * length * 0.5 + aw * 0.9)
            out.append(_arm([shoulder[-busy], hang[-busy]], aw, cloth))
            out.append(_arm([shoulder[busy], elbow, hand], aw, cloth))
        elif action == "hug_self":
            ey = sy + (hip - sy) * 0.42
            out.append(_arm([sh_l, (cx + wt * 0.24, ey)], aw, cloth))
            out.append(_arm([sh_r, (cx - wt * 0.24, ey + aw * 0.9)], aw, cloth))
        else:
            out.append(_arm([sh_l, hang[-1]], aw, cloth))
            out.append(_arm([sh_r, hang[1]], aw, cloth))
            if action == "walk_away":
                d = 1 if ux > 0 else -1 if ux < 0 else 1
                y = sy + (hip - sy) * 0.3
                x0 = cx + d * (wt / 2 + aw * 1.6)
                out.append(line(x0, y, x0 + d * f.h * 0.3, y, ACCENT, 2.0, sk="s"))
                tip = x0 + d * f.h * 0.3
                out.append(poly([(tip + d * 7, y), (tip, y - 4), (tip, y + 4)], ACCENT, sk="fine"))

    out.append(circ(hx, hy, r, "none" if ghost else (HAIR if turn else SKIN), ink, sw, sk="fine" if ghost else "s", stroke_dasharray=dash))
    if look and not ghost and not turn:
        out.append(_nose(hx, hy, r, r, ux, uy))
    if not ghost:
        ly = min(sy + (min(base, 172) - sy) * 0.32, 166)
        out.append(_label(cx, ly, char, max(6.5, min(11.0, f.h * 0.06))))
    return "".join(out)


# ---------------------------------------------------------------- backgrounds

def _tiles(top: float) -> str:
    """Floor tiles seen from above: lines converge toward the top of the frame."""
    out = []
    for x in range(-160, 481, 60):
        x_top = 160 + (x - 160) * 0.3
        out.append(line(x_top, top, x, H, TILE, 1.0))
    for dy in (14, 34, 62, 98, 142):
        y = top + dy
        if y < H:
            out.append(line(0, y, W, y, TILE, 1.0))
    return "".join(out)


def _wall_bg(angle: str, props, close: bool = False) -> str:
    """A flat wall behind the characters. The angle decides what else is visible."""
    door = "door" in props
    p = [rect(0, 0, W, H, WALL)]
    if angle == "eye_level":
        if not close:
            p.append(rect(0, 120, W, 60, FLOOR))
            p.append(rect(0, 120, W, 60, "#8E99A6", sk="bg", fs="hachure", opacity=0.45))
            p.append(line(0, 120, W, 120, PENCIL, 2.0))
        if door and not close:
            p.append(rect(238, 22, 66, 98, GLASS, PENCIL, 2.4))
            p.append(poly([(238, 22), (262, 31), (262, 118), (238, 120)], DOOR_LEAF, PENCIL, 2.0))
        if close:
            p.append(rect(270, 0, 50, H, GLASS))
    elif angle == "low":
        ceil_y = (22, 38) if close else (28, 48)
        p.append(poly([(0, 0), (W, 0), (W, ceil_y[0]), (0, ceil_y[1])], CEILING))
        p.append(poly([(0, 0), (W, 0), (W, ceil_y[0]), (0, ceil_y[1])], "#8E99A6", sk="bg", fs="hachure", opacity=0.35))
        p.append(line(0, ceil_y[1], W, ceil_y[0], PENCIL, 2.0))
        p.append(rect(128, 8, 64, 7, "#fff", PENCIL, 1.4, sk="fine"))
        if door and not close:
            p.append(poly([(238, 58), (298, 58), (306, H), (228, H)], GLASS, PENCIL, 2.4))
            p.append(poly([(238, 58), (258, 68), (256, H), (228, H)], DOOR_LEAF, PENCIL, 2.0))
        if close:
            p.append(poly([(276, 40), (W, 40), (W, H), (270, H)], GLASS))
    else:  # high
        p = [rect(0, 0, W, H, FLOOR)]
        wall_h = 16 if close else 30
        p.append(rect(0, 0, W, wall_h, WALL))
        p.append(_tiles(wall_h))
        p.append(line(0, wall_h, W, wall_h, PENCIL, 2.0))
        if door and not close:
            p.append(rect(240, 0, 62, wall_h, GLASS, PENCIL, 2.0))
    return "".join(p)


def _corridor(spec: dict) -> tuple[str, float, float, tuple[float, float]]:
    """A hallway in one-point perspective.

    Returns (svg, vanishing_y, floor_below_horizon, door_centre)."""
    hy, c, u = spec["hy"], spec["c"], spec["u"]
    fl, fr = 124.0, 196.0
    floor_y, ceil_y = hy + c * u, hy - (2.6 - c) * u
    t = 160.0 / (160.0 - fl)

    def edge(y_far: float) -> float:
        return hy + (y_far - hy) * t

    yc0, yf0 = edge(ceil_y), edge(floor_y)
    p = [rect(0, 0, W, H, WALL)]
    p.append(poly([(0, yc0), (fl, ceil_y), (fr, ceil_y), (W, yc0), (W, -40), (0, -40)], CEILING))
    p.append(poly([(0, yc0), (fl, ceil_y), (fl, floor_y), (0, yf0)], "#E6EAEE"))
    p.append(poly([(W, yc0), (fr, ceil_y), (fr, floor_y), (W, yf0)], WALL_DARK))
    p.append(poly([(0, yf0), (fl, floor_y), (fr, floor_y), (W, yf0), (W, 260), (0, 260)], FLOOR))
    p.append(poly([(0, yf0), (fl, floor_y), (fr, floor_y), (W, yf0), (W, 260), (0, 260)], "#8E99A6", sk="bg", fs="hachure", opacity=0.4))
    p.append(rect(fl, ceil_y, fr - fl, floor_y - ceil_y, "#D6DCE3", PENCIL, 1.6))
    door_top = floor_y - 2.0 * u
    p.append(rect(146, door_top, 28, floor_y - door_top, GLASS, PENCIL, 1.8, sk="fine"))
    for x, y in ((0, yc0), (W, yc0), (0, yf0), (W, yf0)):
        far_x = fl if x == 0 else fr
        far_y = ceil_y if y == yc0 else floor_y
        p.append(line(x, y, far_x, far_y, PENCIL, 1.6))
    return "".join(p), hy, floor_y - hy, (160.0, floor_y - u)


# ------------------------------------------------------------------ gaze logic

def _look_at(kind, me: _Fig, partner: _Fig | None, door, away: int):
    """Turn a gaze ID into an arrow target (x, y, stop_distance), or None."""
    if kind == "door" and door is None:
        kind = "away"
    if kind == "partner":
        return (partner.cx, partner.cy, partner.r * 1.75) if partner else None
    if kind == "door":
        return (door[0], door[1], 0.0)
    if kind == "away":
        return (me.cx + away * 95.0, me.cy + 6.0, 0.0)
    if kind == "down":
        return (me.cx + away * me.r * 1.5, me.cy + me.r * 4.4, 0.0)
    return None


def _hints(gaze, actions):
    return dict(gaze or {}), dict(actions or {})


# ------------------------------------------------------------------ templates

_MED = {"low": (200.0, 232.0), "eye_level": (156.0, 212.0), "high": (118.0, 172.0)}


def _draw_medium(by_role: dict, angle: str, props, slots: dict, gaze, actions) -> str:
    h, base = _MED[angle]
    scale = 1.06 if len(slots) == 1 else 1.0
    door_on = "door" in props
    figs = {}
    for role, cx in slots.items():
        char = by_role.get(role)
        if char:
            figs[char] = _Fig(cx, base + (h * scale - h) * 0.4, h * scale, angle)
    out = [_wall_bg(angle, props)]
    arrows, bodies, on_top = [], [], []
    for char, f in figs.items():
        partner = next((g for c, g in figs.items() if c != char), None)
        away = (1 if f.cx > partner.cx else -1) if partner else 1
        kind = gaze.get(char, "partner" if partner else None)
        action = actions.get(char, "stand")
        look = _look_at(kind, f, partner, _DOOR_EYE[angle] if door_on else None, away)
        if action == "turn_away" and look is None:
            look = _look_at("away", f, partner, None, away)
        reach = None
        if action == "hold_door" and door_on:
            reach = _DOOR_HAND[angle]
        elif action == "reach_out" and partner:
            reach = (partner.cx, partner.sy + partner.h * 0.12)
        # An eyeline that goes sideways passes behind the other figure; one that points down lies over the body.
        (on_top if kind == "down" else arrows).append(_gaze_arrow(f, look, action))
        bodies.append(_figure(f, char, look, action, reach, shadow=True))
    return "".join(out + arrows + bodies + on_top)


# per-angle close-up geometry: subject head (cx, cy, rx, ry), shoulders path, neck, foreground head and shoulder
_OTS = {
    "eye_level": {
        "head": (205, 84, 42, 50), "neck": (186, 122, 28, 24),
        "sh": "M92 180Q96 140 148 130H252Q304 140 308 180Z",
        "fg": (22, 58, 32, 44), "fgsh": "M0 100Q62 94 88 126Q106 150 110 180H0Z",
        "lab": (204, 162), "fglab": (40, 156),
    },
    "low": {
        "head": (205, 66, 48, 58), "neck": (184, 114, 32, 30),
        "sh": "M84 180Q90 148 146 140H264Q312 148 316 180Z",
        "fg": (16, 44, 38, 52), "fgsh": "M0 92Q70 90 98 124Q116 150 120 180H0Z",
        "lab": (204, 166), "fglab": (42, 150),
    },
    "high": {
        "head": (200, 106, 36, 40), "neck": (186, 134, 28, 14),
        "sh": "M52 180Q62 150 122 142H278Q318 150 322 180Z",
        "fg": (26, 98, 26, 34), "fgsh": "M0 128Q44 126 66 148Q80 162 82 180H0Z",
        "lab": (200, 166), "fglab": (34, 164),
    },
}


def _draw_ots(by_role: dict, angle: str, props, gaze, actions) -> str:
    g = _OTS[angle]
    subject, fg = by_role.get("subject", "B"), by_role.get("foreground", "A")
    cx, cy, rx, ry = g["head"]
    nx, ny, nw, nh = g["neck"]
    fx, fy, frx, fry = g["fg"]
    kind = gaze.get(subject, "partner")
    action = actions.get(subject, "stand")
    ax, ay = cx, cy
    if action == "head_down":
        ay += 7
        ax -= 4
    target = {
        "partner": (fx, fy),
        "door": (W - 18.0, cy - 10),
        "away": (cx + 95.0, cy + 8),
        "down": (cx - rx * 0.95, cy + ry * 2.1),
    }.get(kind)
    if action == "turn_away" and target is None:
        target = (cx + 95.0, cy + 8)
    ux = uy = 0.0
    arrow = ""
    if target:
        tx, ty = target
        if action == "head_down":
            ty += abs(tx - cx) * 0.3
        ux, uy = _unit(tx - cx, (ty - ay))
        stop = frx * 0.95 if kind == "partner" else 0.0
        sx, sy_ = cx + ux * rx * 1.45, ay + uy * ry * 1.45
        ex, ey = tx - ux * stop, ty - uy * stop
        if math.hypot(ex - sx, ey - sy_) >= 9:
            head = 8.0
            bx, by = ex - ux * head, ey - uy * head
            arrow = line(sx, sy_, bx, by, ACCENT, 1.8, "5 4", sk="s") + poly(
                [(ex, ey), (bx - uy * head * 0.42, by + ux * head * 0.42), (bx + uy * head * 0.42, by - ux * head * 0.42)],
                ACCENT, sk="fine")
    sc, fc = CHAR_COLOR.get(subject, "#777"), CHAR_COLOR.get(fg, "#777")
    turn = action == "turn_away"
    parts = [
        _wall_bg(angle, props, close=True),
        "" if kind == "down" else arrow,
        rect(nx, ny, nw, nh, SKIN, INK, 1.9, sk="fine"),
        path(g["sh"], sc, INK, 2.0),
        ell(ax, ay, rx, ry, HAIR if turn else SKIN, INK, 2.0),
    ]
    if target and not turn:
        parts.append(_nose(ax, ay, rx, ry, ux, uy))
    parts += [
        path(g["fgsh"], fc, INK, 2.0),
        ell(fx, fy, frx, fry, HAIR, INK, 2.0),
        _label(*g["lab"], subject, 11),
        _label(*g["fglab"], fg, 11),
        arrow if kind == "down" else "",
    ]
    return "".join(parts)


# Wide shot geometry. hy = horizon (vanishing point) height in the frame, c = camera height in
# metres, u = pixels per metre at the far end, base/h = where the figures stand and how tall they are.
_WIDE = {
    "low": {"hy": 128.0, "c": 0.6, "u": 30.0, "base": 176.0, "h": 94.0},
    "eye_level": {"hy": 84.0, "c": 1.6, "u": 28.0, "base": 158.0, "h": 62.0},
    "high": {"hy": 40.0, "c": 2.3, "u": 24.0, "base": 150.0, "h": 44.0},
}


def _draw_wide(by_role: dict, angle: str, gaze, actions) -> str:
    spec = _WIDE[angle]
    svg, hy, floor_below_horizon, door_c = _corridor(spec)
    base, h = spec["base"], spec["h"]
    s = (base - hy) / floor_below_horizon          # how far the floor edge has spread at this depth
    half = 36.0 * s                                 # half the floor width at the figures' depth
    left_x, right_x = 160 - 0.7 * half, 160 + 0.7 * half
    figure, absent = by_role.get("figure"), by_role.get("absent")
    out = [svg]
    me = _Fig(left_x, base, h, angle) if figure else None
    ghost = _Fig(right_x, base, h, angle) if absent else None
    if me:
        kind = gaze.get(figure, "partner" if ghost else None)
        action = actions.get(figure, "stand")
        look = _look_at(kind, me, ghost, (door_c[0], door_c[1], ), -1)
        if action == "turn_away" and look is None:
            look = _look_at("away", me, None, None, -1)
        if kind != "down":
            out.append(_gaze_arrow(me, look, action))
    if ghost:
        out.append(_figure(ghost, absent, ghost=True))
        out.append(text(right_x, base - h - 7, "빈 자리", 10, ACCENT))
    if me:
        out.append(_figure(me, figure, look, action, shadow=True))
        if kind == "down":
            out.append(_gaze_arrow(me, look, action))
    return "".join(out)


def _tag(template_id: str, angle_id: str) -> str:
    label = f"{_SHOT_TAG[template_id]} · {_ANGLE_TAG[angle_id]}"
    w = 6.0 * len(label) + 8
    x, y = W - w - 4, H - 18
    return rect(x, y, w, 14, "#fff", INK, 1.3, sk="fine") + text(x + w / 2, y + 10.3, label, 8.6)


def render_panel(template_id: str, angle_id: str, roles: dict, props=(), alt: str = "", gaze=None, actions=None) -> str:
    """Return one storyboard panel as an SVG string.

    `roles` maps character ID to a template role, for example {"B": "left", "A": "right"}.
    `gaze` maps character ID to a gaze ID and `actions` to an action ID (see scene.GAZE_TARGETS
    and scene.ACTIONS). Both are optional: a character with no entry looks at the other character.
    """
    _check_angle(angle_id)
    by_role = {role: char for char, role in roles.items()}
    gaze, actions = _hints(gaze, actions)
    props = tuple(props or ())
    if template_id == "medium_two_shot":
        body = _draw_medium(by_role, angle_id, props, {"left": 98.0, "right": 214.0}, gaze, actions)
    elif template_id == "single_medium":
        body = _draw_medium(by_role, angle_id, props, {"figure": 160.0}, gaze, actions)
    elif template_id == "ots_close_up":
        body = _draw_ots(by_role, angle_id, props, gaze, actions)
    elif template_id == "wide_empty_space":
        body = _draw_wide(by_role, angle_id, gaze, actions)
    else:
        raise ValueError(f"unknown template: {template_id!r}")
    label = alt.replace('"', "&quot;")
    seed = zlib.crc32(f"{template_id}|{angle_id}".encode()) % 997 + 1
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{label}" data-seed="{seed}">'
        f'{rect(0, 0, W, H, PAPER, sk=None)}{body}{_tag(template_id, angle_id)}</svg>'
    )


# ------------------------------------------------------------------- diagrams

def angle_diagram(angle_id: str) -> str:
    """A small side view: where the camera stands relative to the person it films."""
    _check_angle(angle_id)
    cam_x, cam_y = 26.0, {"low": 62.0, "eye_level": 30.0, "high": 8.0}[angle_id]
    sx, ground = 128.0, 72.0
    head = (sx, 30.0)
    dx, dy = head[0] - 9 - cam_x, head[1] + 1 - cam_y
    deg = math.degrees(math.atan2(dy, dx))
    rad = math.radians(deg)
    start = (cam_x + 18 * math.cos(rad), cam_y + 18 * math.sin(rad))
    end = (head[0] - 9, head[1] + 1)
    left = (end[0] - 7 * math.cos(rad - 0.45), end[1] - 7 * math.sin(rad - 0.45))
    right = (end[0] - 7 * math.cos(rad + 0.45), end[1] - 7 * math.sin(rad + 0.45))
    body = [
        line(6, ground, 144, ground, PENCIL, 2.0),
        line(cam_x, 30, sx, 30, TILE, 1.0, "2 3"),
        line(cam_x, cam_y + 5, cam_x, ground, PENCIL, 1.5),
        circ(sx, 30, 6, SKIN, INK, 1.5, sk="fine"),
        path(f"M{_f(sx - 8)} {_f(ground)} L{_f(sx - 7)} 41 Q{_f(sx)} 36 {_f(sx + 7)} 41 L{_f(sx + 8)} {_f(ground)} Z",
             CHAR_COLOR["B"], INK, 1.5, sk="fine"),
        f'<g transform="translate({_f(cam_x)} {_f(cam_y)}) rotate({_f(deg)})">'
        + rect(-9, -5, 18, 10, INK, sk="fine") + poly([(9, -3), (15, -6), (15, 6), (9, 3)], INK, sk="fine") + "</g>",
        line(start[0], start[1], end[0], end[1], ACCENT, 1.6, "4 3", sk="fine"),
        poly([end, left, right], ACCENT, sk="fine"),
    ]
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 84" aria-hidden="true" data-seed="11">'
            + "".join(body) + "</svg>")


def _camera(x: float, y: float, deg: float, fov: float, reach: float) -> str:
    """A camera icon with its field of view, seen from above. `deg` is the direction it points (0 = right, -90 = up)."""
    a0, a1 = math.radians(deg - fov / 2), math.radians(deg + fov / 2)
    cone = poly([(x, y), (x + reach * math.cos(a0), y + reach * math.sin(a0)),
                 (x + reach * math.cos(a1), y + reach * math.sin(a1))], ACCENT, sk="bg", opacity=0.13)
    edges = line(x, y, x + reach * math.cos(a0), y + reach * math.sin(a0), ACCENT, 1.0, "3 3", sk="fine") + \
        line(x, y, x + reach * math.cos(a1), y + reach * math.sin(a1), ACCENT, 1.0, "3 3", sk="fine")
    icon = (f'<g transform="translate({_f(x)} {_f(y)}) rotate({_f(deg)})">'
            + rect(-7, -4.5, 12, 9, INK, sk="fine") + poly([(5, -2.5), (10, -5.5), (10, 5.5), (5, 2.5)], INK, sk="fine") + "</g>")
    return cone + edges + icon


def blocking_diagram(template_id: str, angle_id: str, roles: dict, props=(), gaze=None) -> str:
    """A small plan view: where the camera and the characters stand, which way each one faces."""
    _check_angle(angle_id)
    by_role = {role: char for char, role in roles.items()}
    gaze = dict(gaze or {})
    props = tuple(props or ())
    spots: dict[str, tuple[float, float]] = {}
    ghosts: dict[str, tuple[float, float]] = {}
    door_pos = None
    if template_id == "medium_two_shot":
        slots = {"left": (46.0, 44.0), "right": (100.0, 44.0)}
        cam = (73.0, 78.0, -90.0, 100.0, 62.0)
        door_pos = (141.0, 44.0, "v") if "door" in props else None
    elif template_id == "single_medium":
        slots = {"figure": (75.0, 44.0)}
        cam = (75.0, 78.0, -90.0, 62.0, 56.0)
        door_pos = (141.0, 44.0, "v") if "door" in props else None
    elif template_id == "ots_close_up":
        slots = {"foreground": (42.0, 56.0), "subject": (108.0, 46.0)}
        cam = (12.0, 64.0, -9.0, 44.0, 112.0)
    elif template_id == "wide_empty_space":
        slots = {"figure": (42.0, 42.0)}
        cam = (75.0, 80.0, -90.0, 112.0, 66.0)
        door_pos = (75.0, 8.0, "h") if "door" in props else None
    else:
        raise ValueError(f"unknown template: {template_id!r}")
    for role, pos in slots.items():
        if role in by_role:
            spots[by_role[role]] = pos
    if template_id == "wide_empty_space" and "absent" in by_role:
        ghosts[by_role["absent"]] = (108.0, 42.0)

    parts = [rect(2, 2, 146, 80, "#fff", TILE, 1.0, sk="bg")]
    if door_pos:
        dx, dy, orient = door_pos
        w, h_ = (6, 26) if orient == "v" else (26, 6)
        parts.append(rect(dx - w / 2, dy - h_ / 2, w, h_, GLASS, PENCIL, 1.4, sk="fine"))
        parts.append(text(dx - 9 if orient == "v" else dx + 21, dy + 3 if orient == "v" else dy + 3, "문", 7.5, PENCIL))
    parts.append(_camera(*cam))
    for char, (x, y) in ghosts.items():
        parts.append(circ(x, y, 7, "none", GHOST, 1.3, sk="fine", stroke_dasharray="3 2"))
        parts.append(text(x, y + 2.8, char, 8, GHOST))
    for char, (x, y) in spots.items():
        others = [p for c, p in {**spots, **ghosts}.items() if c != char]
        kind = gaze.get(char, "partner" if others else None)
        if kind == "partner" and others:
            tx, ty = others[0]
        elif kind == "door" and door_pos:
            tx, ty = door_pos[0], door_pos[1]
        elif kind == "away" and others:
            tx, ty = 2 * x - others[0][0], 2 * y - others[0][1]
        elif kind == "down":
            tx, ty = x, y + 20
        else:
            tx = ty = None
        parts.append(circ(x, y, 7, CHAR_COLOR.get(char, "#777"), INK, 1.5, sk="fine"))
        if tx is not None:
            parts.append(_nose(x, y, 7, 7, *_unit(tx - x, ty - y)))
        parts.append(text(x, y + 2.8, char, 8, "#fff"))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 84" aria-hidden="true" data-seed="23">'
            + "".join(parts) + "</svg>")
