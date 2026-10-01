"""Record docs/demo.gif from a real run of voiceprint on the shipped sample.

It runs the Quick start commands for real in a scratch copy, writes their
actual stdout and exit codes to demo_session.json, then renders each frame of
demo.html with Playwright and joins them with ffmpeg. No output line is typed
in by hand. The terminal window is the same one gdoc-surgical's GIF uses.

    pip install playwright && python -m playwright install chromium
    python docs/src/demo.py
"""
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "demo.gif"
SESSION = HERE / "demo_session.json"
FPS = 12
# The rewrite carries the same news as examples/draft.md, in Sari's voice.
REWRITE = "pay button to bottom, bayar sekarang?"


def run(cwd, argv):
    p = subprocess.run([sys.executable] + argv, cwd=cwd, capture_output=True, text=True)
    return p.stdout.rstrip("\n"), p.returncode


def capture():
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "scripts", tmp / "scripts")
    shutil.copytree(ROOT / "examples", tmp / "examples")
    vp = "python3 scripts/voiceprint.py "
    # (command after the prompt, typed?, hold ms, expected exit or None)
    steps = [
        ("ingest --source jsonl --path examples/sample_sent.jsonl --out corpus.json", False, 0, 0),
        ("analyze corpus.json --out profile.json", False, 2000, 0),
        ("head -n 3 examples/draft.md", True, 900, None),
        ("check --profile profile.json --file examples/draft.md", True, 2200, 1),
        (f'check --profile profile.json --text "{REWRITE}"', True, 2600, 0),
    ]
    session = []
    for args, typed, hold, want in steps:
        if args.startswith("head "):
            lines = (tmp / "examples" / "draft.md").read_text(encoding="utf-8").splitlines()[:3]
            session.append({"cmd": args, "out": "\n".join(lines), "typed": typed, "hold": hold})
            continue
        out, rc = run(tmp, ["scripts/voiceprint.py"] + shlex.split(args))
        assert rc == want, (args, rc, out)
        if args.startswith("check"):
            out += f"\nexit {rc}"
        session.append({"cmd": vp + args, "out": out, "typed": typed, "hold": hold})
    shutil.rmtree(tmp, ignore_errors=True)
    SESSION.write_text(json.dumps(session, indent=1), encoding="utf-8")
    return session


def render(session):
    from playwright.sync_api import sync_playwright
    html = (HERE / "demo.html").read_text(encoding="utf-8").replace("__SESSION__", json.dumps(session))
    tmp = Path(tempfile.mkdtemp(prefix="voiceprint_demo_"))
    page_path = tmp / "demo.html"
    page_path.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 800, "height": 450})
        page.goto(page_path.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready")
        total = page.evaluate("window.TOTAL_MS")
        n = int(total / 1000 * FPS) + 1
        for i in range(n):
            page.evaluate("renderAt(%d)" % int(i * 1000 / FPS))
            page.screenshot(path=str(tmp / ("f%04d.png" % i)))
        browser.close()
    pattern, palette = str(tmp / "f%04d.png"), str(tmp / "palette.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern,
                    "-vf", "palettegen=max_colors=64:stats_mode=diff", palette], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", pattern,
                    "-i", palette, "-lavfi", "paletteuse=dither=none:diff_mode=rectangle",
                    "-loop", "0", str(OUT)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {OUT}: {n} frames, {n / FPS:.1f}s, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    render(capture())
