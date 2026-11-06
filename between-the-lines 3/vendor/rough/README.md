# Rough.js (bundled, unmodified)

| | |
| --- | --- |
| Project | Rough.js, a library for hand-drawn style graphics |
| Official source | https://github.com/rough-stuff/rough |
| Version | 4.6.6 (upstream commit `56a2762171b1294d643501e8d14f120db6b27bd7`) |
| File | `rough.js`, the self-contained minified browser build from the official `roughjs` npm package (`bundled/rough.js`). It defines the global `rough` and has its four small dependencies built in. |
| SHA-256 | `6853af8619532f3939b156cd16824d2e14f31e71d3df306ad5558eeafacab194` |
| License | MIT, Copyright (c) 2019 Preet Shihn. See `LICENSE` in this folder. |

The file is committed exactly as published. Do not edit it; `tests/test_checks.py` checks the hash above.

## How it was checked

The upstream GitHub repository only holds the TypeScript source, not the built bundle. To confirm that this bundle matches the source, the source at the commit above was compiled and the same shapes
(rectangle, circle with hachure fill, ellipse, dashed line, polygon, SVG path) were generated with a fixed seed by both builds. The generated path data was identical in all six cases.

## How to update

1. Get the new official release of `roughjs` and copy `bundled/rough.js` here.
2. Replace `LICENSE` with the one from the same release.
3. Update the version, commit and SHA-256 above and in `tests/test_checks.py`, then run the tests.
