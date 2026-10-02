"""Record the README's real terminal GIFs from real runs of voiceprint on the shipped sample.

    docs/demo.gif        the Quick start: ingest, analyze, check the AI draft (FAIL), check a rewrite (PASS)
    docs/voice-file.gif  render, then what the voice file and the prompt block actually say

It runs the commands for real in a scratch copy, writes their actual stdout and exit codes
to demo_session.json and voice_session.json, then renders each frame of demo.html with
Playwright and joins them with ffmpeg. No output line is typed in by hand. The terminal
window is the same one gdoc-surgical's GIF uses.

    pip install playwright && python -m playwright install chromium   (ffmpeg and grep on PATH)
    python docs/src/demo.py              # both
    python docs/src/demo.py voice        # just one: demo | voice
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
FPS = 12
# The rewrite carries the same news as examples/draft.md, in Sari's voice.
REWRITE = "pay button to bottom, bayar sekarang?"
VP = "python3 scripts/voiceprint.py "

# Each step: (command after the prompt, typed?, hold ms, expected exit or None).
# A step starting with "voiceprint " runs scripts/voiceprint.py; anything else runs as a shell tool.
RECORDINGS = {
    "demo": {
        "out": "demo.gif",
        "session": "demo_session.json",
        "title": "voiceprint, sample corpus of 300 sent messages",
        "setup": [],
        "steps": [
            ("voiceprint ingest --source jsonl --path examples/sample_sent.jsonl --out corpus.json", False, 0, 0),
            ("voiceprint analyze corpus.json --out profile.json", False, 2000, 0),
            ("head -n 3 examples/draft.md", True, 900, None),
            ("voiceprint check --profile profile.json --file examples/draft.md", True, 2200, 1),
            (f'voiceprint check --profile profile.json --text "{REWRITE}"', True, 2600, 0),
        ],
    },
    "voice": {
        "out": "voice-file.gif",
        "session": "voice_session.json",
        "title": "voiceprint render, the sample writer Sari",
        "setup": [
            "ingest --source jsonl --path examples/sample_sent.jsonl --out corpus.json",
            "analyze corpus.json --out profile.json",
        ],
        "steps": [
            ('voiceprint render profile.json --out-dir voice --name "Sari"', True, 1600, 0),
            ("head -n 5 voice/voice_prompt.txt", True, 2200, 0),
            ('grep -A4 "Last word of a sentence" voice/voice.md', True, 3200, 0),
        ],
    },
}


def run_vp(cwd, args):
    p = subprocess.run([sys.executable, "scripts/voiceprint.py"] + shlex.split(args), cwd=cwd,
                       capture_output=True, text=True)
    return p.stdout.rstrip("\n"), p.returncode


def capture(rec):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "scripts", tmp / "scripts")
    shutil.copytree(ROOT / "examples", tmp / "examples")
    for args in rec["setup"]:
        out, rc = run_vp(tmp, args)
        assert rc == 0, (args, rc, out)
    session = []
    for args, typed, hold, want in rec["steps"]:
        if args.startswith("voiceprint "):
            out, rc = run_vp(tmp, args[len("voiceprint "):])
            shown = VP + args[len("voiceprint "):]
        else:
            argv = shlex.split(args)
            argv[0] = shutil.which(argv[0]) or argv[0]
            p = subprocess.run(argv, cwd=tmp, capture_output=True, text=True)
            out, rc, shown = p.stdout.rstrip("\n"), p.returncode, args
        if want is not None:
            assert rc == want, (args, rc, out)
        if args.startswith("voiceprint check"):
            out += f"\nexit {rc}"
        session.append({"cmd": shown, "out": out, "typed": typed, "hold": hold})
    shutil.rmtree(tmp, ignore_errors=True)
    (HERE / rec["session"]).write_text(json.dumps(session, indent=1), encoding="utf-8")
    return session


def render(rec, session):
    from playwright.sync_api import sync_playwright
    out = ROOT / "docs" / rec["out"]
    html = ((HERE / "demo.html").read_text(encoding="utf-8")
            .replace("__SESSION__", json.dumps(session)).replace("__TITLE__", rec["title"]))
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
                    "-loop", "0", str(out)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out}: {n} frames, {n / FPS:.1f}s, {out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    for name in sys.argv[1:] or list(RECORDINGS):
        rec = RECORDINGS[name]
        render(rec, capture(rec))
