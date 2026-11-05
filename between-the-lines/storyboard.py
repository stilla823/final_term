"""Programmatic SVG storyboard panels for Between the Lines.

A panel is schematic: silhouettes labeled A and B. It is drawn from two choices:

* a composition template (what is in the frame), and
* a camera angle (where the camera is: low, eye level or high).

The angle changes the drawing the way it changes a real shot. A low camera looks
up, so figures loom, the ceiling shows and verticals lean. A high camera looks
down, so figures shrink and the floor takes over the frame. The same code draws
the saved demo and live results.
"""
from __future__ import annotations

import math

W, H = 320, 180
ANGLE_IDS = ("low", "eye_level", "high")

WALL, WALL_DARK, CEILING, FLOOR = "#E4E8EC", "#D7DDE4", "#EEF0F3", "#CBD2DA"
EDGE, TILE, GLASS, DOOR_LEAF, DOOR_FRAME = "#AEB8C3", "#B9C2CC", "#CFE3F5", "#A3AEBB", "#8E9AA8"
INK, ACCENT, GHOST = "#18212C", "#C0392B", "#7F8B99"
CHAR_COLOR = {"A": "#1E2733", "B": "#35598F"}

# Head and body proportions (fractions of figure height). Seen from below the head
# is small and the body tapers upward; seen from above the head is large and the
# shoulders look wide over narrow feet.
_BODY = {
    "low": {"head": 0.100, "wt": 0.25, "wb": 0.34},
    "eye_level": {"head": 0.115, "wt": 0.30, "wb": 0.26},
    "high": {"head": 0.150, "wt": 0.36, "wb": 0.22},
}


def _n(v: float) -> str:
    return f"{v:.1f}"


def _check_angle(angle: str) -> None:
    if angle not in ANGLE_IDS:
        raise ValueError(f"unknown angle: {angle!r}")


def _label(cx: float, cy: float, text: str, r: float) -> str:
    return (
        f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="#fff"/>'
        f'<text x="{_n(cx)}" y="{_n(cy + r * 0.38)}" text-anchor="middle" font-family="sans-serif" '
        f'font-size="{_n(r * 1.25)}" font-weight="700" fill="{INK}">{text}</text>'
    )


def _figure(cx, base, h, char, angle, face=0, ghost=False, shadow=False) -> str:
    """A full-length silhouette. `base` may be below the frame (cropped figure)."""
    b = _BODY[angle]
    r = h * b["head"]
    cy = base - h + r
    sy = cy + r * 1.25
    wt, wb = h * b["wt"], h * b["wb"]
    rr = wt * 0.28
    body = (
        f"M{_n(cx - wb / 2)} {_n(base)} L{_n(cx - wt / 2)} {_n(sy + rr)} "
        f"Q{_n(cx - wt / 2)} {_n(sy)} {_n(cx - wt / 2 + rr)} {_n(sy)} L{_n(cx + wt / 2 - rr)} {_n(sy)} "
        f"Q{_n(cx + wt / 2)} {_n(sy)} {_n(cx + wt / 2)} {_n(sy + rr)} L{_n(cx + wb / 2)} {_n(base)} Z"
    )
    if ghost:
        out = [f'<g fill="none" stroke="{GHOST}" stroke-width="1.5" stroke-dasharray="4 3">']
    else:
        out = [f'<g fill="{CHAR_COLOR.get(char, "#444")}">']
        if shadow and base <= H - 2:
            out.insert(0, f'<ellipse cx="{_n(cx)}" cy="{_n(base)}" rx="{_n(wb * 0.9)}" ry="3.5" fill="#000" opacity=".13"/>')
        out.append(f'<rect x="{_n(cx - r * 0.38)}" y="{_n(cy)}" width="{_n(r * 0.76)}" height="{_n(sy - cy + 2)}"/>')
    out.append(f'<path d="{body}"/>')
    out.append(f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}"/>')
    if face and not ghost:
        out.append(
            f'<polygon points="{_n(cx + face * r * 0.85)},{_n(cy - r * 0.2)} {_n(cx + face * r * 1.3)},{_n(cy + r * 0.25)} '
            f'{_n(cx + face * r * 0.85)},{_n(cy + r * 0.35)}"/>'
        )
    out.append("</g>")
    if not ghost:
        ly = sy + (min(base, 172) - sy) * 0.32
        out.append(_label(cx, min(ly, 166), char, max(6.5, min(11.0, h * 0.06))))
    return "".join(out)


# ---------------------------------------------------------------- backgrounds

def _tiles(top: float) -> str:
    """Floor tiles seen from above: lines converge toward the top of the frame."""
    out = []
    for x in range(-160, 481, 60):
        x_top = 160 + (x - 160) * 0.3
        out.append(f'<line x1="{_n(x_top)}" y1="{_n(top)}" x2="{x}" y2="{H}" stroke="{TILE}" stroke-width="1.2"/>')
    for dy in (14, 34, 62, 98, 142):
        y = top + dy
        if y < H:
            out.append(f'<line x1="0" y1="{_n(y)}" x2="{W}" y2="{_n(y)}" stroke="{TILE}" stroke-width="1.2"/>')
    return "".join(out)


def _wall_bg(angle: str, props, close: bool = False) -> str:
    """A flat wall behind the characters. The angle decides what else is visible."""
    door = "door" in props
    p = [f'<rect width="{W}" height="{H}" fill="{WALL}"/>']
    if angle == "eye_level":
        if not close:
            p.append(f'<rect y="120" width="{W}" height="60" fill="{FLOOR}"/>')
            p.append(f'<line x1="0" y1="120" x2="{W}" y2="120" stroke="{EDGE}" stroke-width="2"/>')
        if door and not close:
            p.append(f'<rect x="238" y="22" width="66" height="98" fill="{GLASS}" stroke="{DOOR_FRAME}" stroke-width="3"/>')
            p.append(f'<polygon points="238,22 262,31 262,118 238,120" fill="{DOOR_LEAF}" stroke="#7F8B99" stroke-width="2"/>')
        if close:
            p.append(f'<rect x="270" width="50" height="{H}" fill="{GLASS}"/>')
    elif angle == "low":
        ceil_y = (22, 38) if close else (28, 48)
        p.append(f'<polygon points="0,0 {W},0 {W},{ceil_y[0]} 0,{ceil_y[1]}" fill="{CEILING}"/>')
        p.append(f'<line x1="0" y1="{ceil_y[1]}" x2="{W}" y2="{ceil_y[0]}" stroke="{EDGE}" stroke-width="2"/>')
        p.append(f'<rect x="128" y="8" width="64" height="7" rx="2" fill="#fff"/>')
        if door and not close:
            p.append(f'<polygon points="238,58 298,58 306,{H} 228,{H}" fill="{GLASS}" stroke="{DOOR_FRAME}" stroke-width="3"/>')
            p.append(f'<polygon points="238,58 258,68 256,{H} 228,{H}" fill="{DOOR_LEAF}" stroke="#7F8B99" stroke-width="2"/>')
        if close:
            p.append(f'<polygon points="276,40 {W},40 {W},{H} 270,{H}" fill="{GLASS}"/>')
    else:  # high
        p = [f'<rect width="{W}" height="{H}" fill="{FLOOR}"/>']
        wall_h = 16 if close else 30
        p.append(f'<rect width="{W}" height="{wall_h}" fill="{WALL}"/>')
        p.append(_tiles(wall_h))
        p.append(f'<line x1="0" y1="{wall_h}" x2="{W}" y2="{wall_h}" stroke="{EDGE}" stroke-width="2"/>')
        if door and not close:
            p.append(f'<rect x="240" y="0" width="62" height="{wall_h}" fill="{GLASS}" stroke="{DOOR_FRAME}" stroke-width="2"/>')
    return "".join(p)


def _corridor(angle: str, spec: dict) -> tuple[str, float, float]:
    """A hallway in one-point perspective. Returns (svg, vanishing_y, half_floor_width_at_base)."""
    hy, c, u = spec["hy"], spec["c"], spec["u"]
    fl, fr = 124.0, 196.0
    floor_y, ceil_y = hy + c * u, hy - (2.6 - c) * u
    t = 160.0 / (160.0 - fl)

    def edge(y_far: float) -> float:
        return hy + (y_far - hy) * t

    yc0, yf0 = edge(ceil_y), edge(floor_y)
    p = [f'<rect width="{W}" height="{H}" fill="{WALL}"/>']
    p.append(f'<polygon points="0,{_n(yc0)} {_n(fl)},{_n(ceil_y)} {_n(fr)},{_n(ceil_y)} {W},{_n(yc0)} {W},-40 0,-40" fill="{CEILING}"/>')
    p.append(f'<polygon points="0,{_n(yc0)} {_n(fl)},{_n(ceil_y)} {_n(fl)},{_n(floor_y)} 0,{_n(yf0)}" fill="#E1E6EB"/>')
    p.append(f'<polygon points="{W},{_n(yc0)} {_n(fr)},{_n(ceil_y)} {_n(fr)},{_n(floor_y)} {W},{_n(yf0)}" fill="{WALL_DARK}"/>')
    p.append(f'<polygon points="0,{_n(yf0)} {_n(fl)},{_n(floor_y)} {_n(fr)},{_n(floor_y)} {W},{_n(yf0)} {W},260 0,260" fill="{FLOOR}"/>')
    p.append(f'<rect x="{_n(fl)}" y="{_n(ceil_y)}" width="{_n(fr - fl)}" height="{_n(floor_y - ceil_y)}" fill="#D6DCE3" stroke="{EDGE}" stroke-width="1.5"/>')
    door_top = floor_y - 2.0 * u
    p.append(f'<rect x="146" y="{_n(door_top)}" width="28" height="{_n(floor_y - door_top)}" fill="{GLASS}" stroke="{DOOR_FRAME}" stroke-width="2"/>')
    for x, y in ((0, yc0), (W, yc0), (0, yf0), (W, yf0)):
        far_x = fl if x == 0 else fr
        far_y = ceil_y if y == yc0 else floor_y
        p.append(f'<line x1="{x}" y1="{_n(y)}" x2="{_n(far_x)}" y2="{_n(far_y)}" stroke="{EDGE}" stroke-width="1.5"/>')
    return "".join(p), hy, (floor_y - hy)


# ------------------------------------------------------------------ templates

_MED = {"low": (200.0, 232.0), "eye_level": (156.0, 212.0), "high": (118.0, 172.0)}


def _draw_medium(by_role: dict, angle: str, props, slots: dict) -> str:
    h, base = _MED[angle]
    scale = 1.06 if len(slots) == 1 else 1.0
    out = [_wall_bg(angle, props)]
    for role, (cx, face) in slots.items():
        char = by_role.get(role)
        if char:
            out.append(_figure(cx, base + (h * scale - h) * 0.4, h * scale, char, angle, face=face, shadow=angle == "high"))
    return "".join(out)


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


def _draw_ots(by_role: dict, angle: str, props) -> str:
    g = _OTS[angle]
    subject, fg = by_role.get("subject", "B"), by_role.get("foreground", "A")
    cx, cy, rx, ry = g["head"]
    nx, ny, nw, nh = g["neck"]
    fx, fy, frx, fry = g["fg"]
    sc, fc = CHAR_COLOR.get(subject, "#444"), CHAR_COLOR.get(fg, "#444")
    return "".join([
        _wall_bg(angle, props, close=True),
        f'<g fill="{sc}"><path d="{g["sh"]}"/><rect x="{nx}" y="{ny}" width="{nw}" height="{nh}"/>'
        f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>'
        f'<polygon points="{cx - rx + 2},{cy} {cx - rx - 14},{cy + 14} {cx - rx + 2},{cy + 20}"/></g>',
        f'<g fill="{fc}"><ellipse cx="{fx}" cy="{fy}" rx="{frx}" ry="{fry}"/><path d="{g["fgsh"]}"/></g>',
        _label(*g["lab"], subject, 11),
        _label(*g["fglab"], fg, 11),
    ])


# Wide shot geometry. hy = horizon (vanishing point) height in the frame, c = camera height in
# metres, u = pixels per metre at the far end, base/h = where the figures stand and how tall they are.
_WIDE = {
    "low": {"hy": 128.0, "c": 0.6, "u": 30.0, "base": 176.0, "h": 94.0},
    "eye_level": {"hy": 84.0, "c": 1.6, "u": 28.0, "base": 158.0, "h": 62.0},
    "high": {"hy": 40.0, "c": 2.3, "u": 24.0, "base": 150.0, "h": 44.0},
}


def _draw_wide(by_role: dict, angle: str) -> str:
    spec = _WIDE[angle]
    svg, hy, floor_below_horizon = _corridor(angle, spec)
    base, h = spec["base"], spec["h"]
    s = (base - hy) / floor_below_horizon          # how far the floor edge has spread at this depth
    half = 36.0 * s                                 # half the floor width at the figures' depth
    left_x, right_x = 160 - 0.7 * half, 160 + 0.7 * half
    out = [svg]
    figure, absent = by_role.get("figure"), by_role.get("absent")
    if absent:
        out.append(_figure(right_x, base, h, absent, angle, ghost=True))
        out.append(
            f'<text x="{_n(right_x)}" y="{_n(base - h - 7)}" text-anchor="middle" font-family="sans-serif" '
            f'font-size="10" font-weight="700" fill="{ACCENT}">빈 자리</text>'
        )
    if figure:
        out.append(_figure(left_x, base, h, figure, angle, shadow=angle == "high"))
    return "".join(out)


def render_panel(template_id: str, angle_id: str, roles: dict, props=(), alt: str = "") -> str:
    """Return one storyboard panel as an SVG string.

    `roles` maps character ID to a template role, for example {"B": "left", "A": "right"}.
    """
    _check_angle(angle_id)
    by_role = {role: char for char, role in roles.items()}
    if template_id == "medium_two_shot":
        body = _draw_medium(by_role, angle_id, props, {"left": (98, 1), "right": (214, -1)})
    elif template_id == "single_medium":
        body = _draw_medium(by_role, angle_id, props, {"figure": (160, 0)})
    elif template_id == "ots_close_up":
        body = _draw_ots(by_role, angle_id, props)
    elif template_id == "wide_empty_space":
        body = _draw_wide(by_role, angle_id)
    else:
        raise ValueError(f"unknown template: {template_id!r}")
    label = alt.replace('"', "&quot;")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">{body}</svg>'
    )


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
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 84" aria-hidden="true">'
        f'<line x1="6" y1="{_n(ground)}" x2="144" y2="{_n(ground)}" stroke="{EDGE}" stroke-width="2"/>'
        f'<line x1="{_n(cam_x)}" y1="30" x2="{_n(sx)}" y2="30" stroke="{EDGE}" stroke-width="1" stroke-dasharray="2 3"/>'
        f'<line x1="{_n(cam_x)}" y1="{_n(cam_y + 5)}" x2="{_n(cam_x)}" y2="{_n(ground)}" stroke="{DOOR_FRAME}" stroke-width="1.5"/>'
        f'<g fill="{CHAR_COLOR["B"]}"><circle cx="{_n(sx)}" cy="30" r="6"/>'
        f'<path d="M{_n(sx - 8)} {_n(ground)} L{_n(sx - 7)} 41 Q{_n(sx)} 36 {_n(sx + 7)} 41 L{_n(sx + 8)} {_n(ground)} Z"/></g>'
        f'<g transform="translate({_n(cam_x)} {_n(cam_y)}) rotate({_n(deg)})" fill="{INK}">'
        '<rect x="-9" y="-5" width="18" height="10" rx="2"/><polygon points="9,-3 15,-6 15,6 9,3"/></g>'
        f'<line x1="{_n(start[0])}" y1="{_n(start[1])}" x2="{_n(end[0])}" y2="{_n(end[1])}" stroke="{ACCENT}" stroke-width="1.6" stroke-dasharray="4 3"/>'
        f'<polygon points="{_n(end[0])},{_n(end[1])} {_n(left[0])},{_n(left[1])} {_n(right[0])},{_n(right[1])}" fill="{ACCENT}"/>'
        "</svg>"
    )
