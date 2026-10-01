"""Record docs/demo.gif from a real run of voiceprint on the shipped sample.

It runs the Quick start commands for real in a scratch copy and draws their
actual output; no output line is typed in by hand. Needs Pillow (pip install pillow).

    python docs/src/demo.py
"""
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "demo.gif"
REWRITE = "pay button goes to the bottom, label is bayar sekarang. ok ya?"

# Shared visual system.
INK, FIELD, PAPER, SIGNAL = "#072B27", "#0D453E", "#F1F3EE", "#C8F751"
DIM, FAIL, NOTE = "#8FB0A8", "#FF9E8A", "#E9D98B"

W, H = 960, 600
PAD, TOP, LH, COLS = 28, 62, 23, 80


def font(names, size):
    for n in names:
        for base in ("", "C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", "/Library/Fonts/"):
            try:
                return ImageFont.truetype(base + n, size)
            except OSError:
                continue
    return ImageFont.load_default()


MONO = font(["CascadiaMono.ttf", "consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"], 16)
MONO_B = font(["consolab.ttf", "DejaVuSansMono-Bold.ttf", "CascadiaMono.ttf"], 16)


def run(cwd, args):
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True)
    return p.stdout.strip().splitlines(), p.returncode


def color_for(line):
    if line.startswith("FAIL"):
        return FAIL
    if line.startswith("PASS"):
        return SIGNAL
    if line.startswith("note"):
        return NOTE
    if line.startswith("exit"):
        return DIM
    return PAPER


def wrap(line):
    return textwrap.wrap(line, COLS, subsequent_indent="      ") or [""]


class Term:
    def __init__(self):
        self.lines = []  # (text, colour, bold)
        self.frames, self.durations = [], []

    def draw(self, cursor=None):
        im = Image.new("RGB", (W, H), PAPER)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 10, W - 4, H - 4], 16, fill=FIELD)  # offset shadow
        d.rounded_rectangle([4, 4, W - 10, H - 10], 16, fill=INK, outline=FIELD, width=2)
        for i, c in enumerate(("#3E6A63", "#3E6A63", "#3E6A63")):
            d.ellipse([24 + i * 22, 22, 36 + i * 22, 34], fill=c)
        d.text((W // 2, 28), "voiceprint", font=MONO, fill=DIM, anchor="mm")
        d.line([4, 48, W - 10, 48], fill=FIELD, width=2)
        rows = (H - TOP - 24) // LH
        view = self.lines[-rows:]
        for i, (t, c, b) in enumerate(view):
            y = TOP + i * LH
            if t.startswith("$ ") or (c == PAPER and b and t.startswith("  ")):
                if t.startswith("$ "):
                    d.text((PAD, y), "$", font=MONO_B, fill=SIGNAL)
                d.text((PAD + 20, y), t[2:], font=MONO_B, fill=PAPER)
            else:
                d.text((PAD, y), t, font=MONO_B if b else MONO, fill=c)
        if cursor is not None and view:
            t = view[-1][0]
            x = PAD + int(d.textlength(t, font=MONO_B)) + 2
            y = TOP + (len(view) - 1) * LH
            d.rectangle([x, y + 2, x + 9, y + 19], fill=SIGNAL)
        return im

    def snap(self, ms, cursor=None):
        self.frames.append(self.draw(cursor))
        self.durations.append(ms)

    def type(self, cmd):
        start = len(self.lines)
        self.lines.append(["$ ", PAPER, True])
        self.snap(250, cursor=True)
        step = 7
        for i in range(0, len(cmd), step):
            parts = textwrap.wrap("$ " + cmd[: i + step], COLS + 6) or ["$ "]
            del self.lines[start:]
            for j, part in enumerate(parts):
                self.lines.append([part if j == 0 else "  " + part, PAPER, True])
            self.snap(35, cursor=True)
        self.snap(250, cursor=True)

    def out(self, lines, per_line=110):
        for line in lines:
            for part in wrap(line):
                self.lines.append([part, color_for(line), line.startswith(("FAIL", "PASS"))])
            self.snap(per_line)


def main():
    # Run exactly the Quick start commands, in a scratch copy, so the
    # output carries relative paths and nothing is written into the repo.
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "scripts", tmp / "scripts")
    shutil.copytree(ROOT / "examples", tmp / "examples")
    vp = "python3 scripts/voiceprint.py "
    steps = [
        ("ingest --source jsonl --path examples/sample_sent.jsonl --out corpus.json", 60, 600),
        ("analyze corpus.json --out profile.json", 120, 1000),
        ("check --profile profile.json --file examples/draft.md", 150, 2400),
        (f'check --profile profile.json --text "{REWRITE}"', 220, 3000),
    ]
    t = Term()
    fail_frame = 0
    for i, (args, per_line, hold) in enumerate(steps):
        if i == 2:
            t.type("cat examples/draft.md")
            draft = (tmp / "examples" / "draft.md").read_text(encoding="utf-8").splitlines()
            t.out(draft, per_line=40)
            t.snap(800)
            t.lines.append(["", PAPER, False])
        out, rc = run(tmp, ["scripts/voiceprint.py"] + shlex.split(args))
        if i == 2:
            assert rc == 1, rc
        if i == 3:
            assert rc == 0, rc
        t.type(vp + args)
        t.out(out, per_line=per_line)
        if i >= 2:
            t.out([f"exit {rc}"])
        t.snap(hold)
        if i == 2:
            fail_frame = len(t.frames) - 1
        t.lines.append(["", PAPER, False])

    # Shared palette keeps the GIF small and the colours exact.
    sheet = Image.new("RGB", (W * 2, H))
    sheet.paste(t.frames[fail_frame], (0, 0))
    sheet.paste(t.frames[-1], (W, 0))
    pal = sheet.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    frames = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in t.frames]
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=t.durations, loop=0, optimize=True)
    total = sum(t.durations) / 1000
    print(f"wrote {OUT}: {len(frames)} frames, {total:.1f}s, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
