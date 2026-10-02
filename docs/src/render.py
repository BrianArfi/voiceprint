"""Render the README illustrations from the HTML sources in this folder.

    pip install playwright && python -m playwright install chromium   (and ffmpeg on PATH)
    python docs/src/render.py            # everything
    python docs/src/render.py hero       # just one: hero | before-after | how-it-works

Outputs:
    docs/hero.png          hero.html frozen at 7 s, 1600x800 CSS px at 2x (also the social preview)
    docs/hero.gif          hero.html played through, 1600x800 at 1x
    docs/before-after.gif  before-after.html, 1200x680
    docs/how-it-works.gif  how-it-works.html, 1200x640

The real terminal recordings (docs/demo.gif, docs/voice-file.gif) come from demo.py instead.
The numbers in these illustrations are the real ones for the shipped sample writer: run the
Quick start in the README and compare.
"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
DOCS = SRC.parent
REC = SRC / "record_html.py"

# name: (html, gif, width, height, seconds, fps, colors)
GIFS = {
    "hero": ("hero.html", "hero.gif", 1600, 800, 9.2, 12, 96),
    "before-after": ("before-after.html", "before-after.gif", 1200, 680, 10.0, 12, 96),
    "how-it-works": ("how-it-works.html", "how-it-works.gif", 1200, 640, 10.0, 12, 96),
}


def hero_png():
    out = DOCS / "hero.png"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 800}, device_scale_factor=2)
        page.goto((SRC / "hero.html").as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        page.evaluate("for (const a of document.getAnimations()) { a.pause(); a.currentTime = 7000; }")
        page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1600, "height": 800})
        browser.close()
    print(f"wrote {out}")


def gif(name):
    html, out, w, h, dur, fps, colors = GIFS[name]
    subprocess.run([sys.executable, str(REC), str(SRC / html), str(DOCS / out), "--w", str(w), "--h", str(h),
                    "--dur", str(dur), "--fps", str(fps), "--colors", str(colors)], check=True)


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(GIFS)
    for name in wanted:
        if name == "hero":
            hero_png()
        gif(name)
