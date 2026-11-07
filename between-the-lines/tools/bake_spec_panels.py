"""Rebuild the storyboard drawings inside docs/index.html (the GitHub Pages Design Spec).

GitHub Pages cannot run the app, and the Design Spec page should not need JavaScript. This script
draws the three demo panels and the three camera-angle diagrams with the same code the app uses,
lets Rough.js redraw them in a headless Chromium, and stores the finished SVG in the page as
<symbol> elements. Rough.js uses a fixed seed, so the result is the same every time.

Needs Playwright and Chromium. Run from the project folder:  python tools/bake_spec_panels.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pipeline  # noqa: E402
import sketch  # noqa: E402
import storyboard  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = ROOT / "docs" / "index.html"
CREDIT = ('Hand-drawn look: <a href="https://github.com/rough-stuff/rough">Rough.js</a> '
          "(MIT License, Copyright (c) 2019 Preet Shihn), applied once when the page was built.")


def drawings(cat):
    shots = cat["demo"]["result"]["shots"]
    items = {}
    for i, shot in enumerate(shots, start=1):
        items[f"panel-{i}"] = (storyboard.render_panel(
            shot["template_id"], shot["angle_id"], shot["roles"], shot.get("props", ()),
            gaze=shot.get("gaze"), actions=shot.get("actions")), 320, 180)
    for key, angle in (("low", "low"), ("eye", "eye_level"), ("high", "high")):
        items[f"diag-{key}"] = (storyboard.angle_diagram(angle), 150, 84)
    return items


def bake(items):
    source = sketch.rough_source()
    if source is None:
        raise SystemExit("rough_bundle.py is missing or does not match the pinned checksum.")
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for name, (svg, w, h) in items.items():
            page.set_content(f"<body>{svg}<script>{source}</script><script>{sketch.SCRIPT}</script></body>")
            if page.evaluate("document.documentElement.getAttribute('data-sketch')") != "rough":
                raise SystemExit(f"Rough.js did not finish for {name}.")
            inner = page.evaluate("document.querySelector('svg').innerHTML")
            out[name] = (inner, w, h)
        browser.close()
    return out


def main():
    cat = pipeline.load_catalogs(ROOT / "data")
    baked = bake(drawings(cat))
    html = PAGE.read_text(encoding="utf-8")
    for name, (inner, w, h) in baked.items():
        pattern = re.compile(rf'(<symbol id="{name}" viewBox="0 0 {w} {h}">).*?(</symbol>)', re.DOTALL)
        html, n = pattern.subn(lambda m: m.group(1) + inner + m.group(2), html)
        if n != 1:
            raise SystemExit(f"Could not find the symbol {name} in {PAGE}.")
    if "rough-stuff/rough" not in html:
        html = html.replace("    <footer>\n", f"    <footer>\n      <p>{CREDIT}</p>\n", 1)
    PAGE.write_text(html, encoding="utf-8")
    print("updated", PAGE, "with", ", ".join(baked))


if __name__ == "__main__":
    main()
