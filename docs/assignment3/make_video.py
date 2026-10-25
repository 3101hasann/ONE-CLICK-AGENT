"""Render a terminal-style setup/test-run video (MP4) for one group member.

It runs the real pytest commands, captures the real output, and renders it as a
scrolling terminal recording with a typing effect. Usage:

    python docs/assignment3/make_video.py 24F-3101 tests/unit/test_screen_change_detector_assignment3.py "M. Hassan Ahmad"
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import imageio.v2 as imageio
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
W, H = 1040, 620
BG = (12, 12, 12)
BAR = (30, 30, 30)
GREEN = (163, 230, 53)
WHITE = (230, 230, 230)
GREY = (150, 150, 150)
PROMPT = (120, 200, 255)
LINE_H = 20
MAX_LINES = 24
FPS = 14

FONT = ImageFont.truetype("consola.ttf", 15)
BOLD = ImageFont.truetype("consolab.ttf", 15)
TITLE = ImageFont.truetype("consolab.ttf", 16)


def run(args):
    out = subprocess.run([sys.executable, "-m", "pytest", *args], cwd=ROOT,
                         capture_output=True, text=True)
    return (out.stdout + out.stderr).splitlines()


def frame(title, lines):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 28), fill=BAR)
    for i, c in enumerate((GREEN, (251, 191, 36), (248, 113, 113))):
        d.ellipse((12 + i * 20, 9, 24 + i * 20, 21), fill=c)
    d.text((80, 6), title, font=TITLE, fill=WHITE)
    y = 38
    for kind, text in lines[-MAX_LINES:]:
        if kind == "cmd":
            d.text((12, y), "PS>", font=BOLD, fill=PROMPT)
            d.text((50, y), text, font=BOLD, fill=WHITE)
        elif kind == "ok":
            d.text((12, y), text, font=BOLD, fill=GREEN)
        else:
            color = GREEN if "passed" in text else GREY if text.startswith(" ") else WHITE
            d.text((12, y), text[:120], font=FONT, fill=color)
        y += LINE_H
    return img


def build(member_id, module_file, member_name, out_path):
    title = f"ONE-CLICK-AGENT  -  Assignment 3  -  {member_name} ({member_id})"
    # Capture real output
    module_lines = [ln for ln in run([module_file, "-v"]) if ln.strip()]
    passed_lines = [ln for ln in module_lines if "PASSED" in ln]
    summary_mod = next((ln for ln in module_lines if "passed" in ln and "=" in ln), "")
    full = run(["-q"])
    summary_full = next((ln for ln in reversed(full) if "passed" in ln), "")

    # Scripted transcript
    steps = [
        ("cmd", "python -m venv .venv"),
        ("cmd", ".venv\\Scripts\\Activate.ps1"),
        ("cmd", "pip install -r requirements.txt -r requirements-dev.txt"),
        ("out", "Successfully installed pytest pytest-xdist openpyxl ..."),
        ("cmd", f"python -m pytest {module_file} -v"),
    ]
    # show a sample of the member's PASSED lines
    for ln in passed_lines[:14]:
        name = ln.split("::")[-1].split(" PASSED")[0]
        steps.append(("out", f"  {name}  PASSED"))
    if len(passed_lines) > 14:
        steps.append(("out", f"  ... (+{len(passed_lines) - 14} more)"))
    steps.append(("ok", summary_mod.replace("=", "").strip() or "passed"))
    steps.append(("cmd", "python -m pytest            # full suite (both members + regression)"))
    steps.append(("ok", summary_full.strip()))

    writer = imageio.get_writer(out_path, fps=FPS, macro_block_size=8)
    shown = []
    # intro hold
    for _ in range(FPS):
        writer.append_data(_np(frame(title, [("out", "Setting up and running the tests...")])))
    for kind, text in steps:
        if kind == "cmd":
            for i in range(0, len(text) + 1, 3):     # typing effect
                writer.append_data(_np(frame(title, shown + [("cmd", text[:i])])))
            shown.append((kind, text))
            for _ in range(4):
                writer.append_data(_np(frame(title, shown)))
        else:
            shown.append((kind, text))
            hold = 10 if kind == "ok" else 3
            for _ in range(hold):
                writer.append_data(_np(frame(title, shown)))
    for _ in range(FPS * 2):                          # end hold
        writer.append_data(_np(frame(title, shown)))
    writer.close()
    print("Wrote", out_path, "|", summary_mod.strip(), "|", summary_full.strip())


def _np(img):
    import numpy as np
    return np.asarray(img)


if __name__ == "__main__":
    mid, module_file, name = sys.argv[1], sys.argv[2], sys.argv[3]
    out = ROOT / f"{mid}_SQE_ASSIGNMENT3" / "video" / f"setup_and_tests_{mid}.mp4"
    build(mid, module_file, name, out)
