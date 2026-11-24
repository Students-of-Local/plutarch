#!/usr/bin/env python3
"""Check this machine can run the kit, and start a film project.

  python3 <skill>/scripts/setup.py                    # report what is installed and what is missing
  python3 <skill>/scripts/setup.py --install          # also pip-install what is missing (use inside a virtualenv)
  python3 <skill>/scripts/setup.py --init ~/films/x   # make the project folder: links scripts/, copies film.json + story.md

After --init, cd into the project. Every other command is then exactly:  python3 scripts/<name>.py"""
import sys, os, shutil, subprocess, importlib, argparse

ap = argparse.ArgumentParser(); ap.add_argument("--install", action="store_true"); ap.add_argument("--init", metavar="FOLDER"); a = ap.parse_args()
KIT = os.path.dirname(os.path.realpath(__file__))

def init(folder):
    folder = os.path.abspath(os.path.expanduser(folder)); skill = os.path.dirname(KIT)
    if os.path.realpath(folder + os.sep).startswith(os.path.realpath(skill) + os.sep):
        print(f"ERROR: {folder} is inside the skill folder {skill}.\nFIX: make the film in the folder the user asked "
              "for: leave the skill folder (or start a fresh shell) and run this command from there."); sys.exit(1)
    os.makedirs(folder, exist_ok=True)
    for d in ("src", "tx", "clips", "narr", "music", "sfx", "out"): os.makedirs(os.path.join(folder, d), exist_ok=True)
    link = os.path.join(folder, "scripts")
    if os.path.islink(link): os.unlink(link)
    if not os.path.exists(link):
        try: os.symlink(KIT, link)
        except OSError: shutil.copytree(KIT, link, ignore=shutil.ignore_patterns("__pycache__")); shutil.copytree(os.path.join(KIT, "..", "fonts"), os.path.join(folder, "fonts"), dirs_exist_ok=True)
    for f in ("film.json", "story.md"):
        dst = os.path.join(folder, f)
        if os.path.exists(dst): print(f"kept  {f} (already there)")
        else: shutil.copy(os.path.join(KIT, "..", "templates", f), dst); print(f"made  {f}")
    print(f"\nPROJECT READY: {folder}\nNext:  cd {folder}   then  python3 scripts/next.py\nFrom inside that folder every command is:  python3 scripts/<name>.py")
NEED = [("numpy", "numpy"), ("scipy", "scipy"), ("soundfile", "soundfile"), ("pyloudnorm", "pyloudnorm"), ("librosa", "librosa"),
        ("skia", "skia-python"), ("PIL", "pillow"), ("faster_whisper", "faster-whisper"), ("yt_dlp", "yt-dlp"), ("kokoro_onnx", "kokoro-onnx")]
NICE = [("demucs", "demucs", "separates a voice from music/noise: needed for exact word timing on anything but clean interviews"),
        ("torchaudio", "torchaudio", "forced alignment for noisy live clips"),
        ("piper", "piper-tts", "second local narrator voice engine"), ("ddgs", "ddgs", "web search with no API key")]
ok = True
if sys.version_info < (3, 10): print("FAIL python 3.10+ needed, you have", sys.version.split()[0]); ok = False
else: print("ok   python", sys.version.split()[0])
for tool in ("ffmpeg", "ffprobe"):
    if shutil.which(tool): print("ok  ", tool)
    else: print(f"FAIL {tool} not found. Install ffmpeg (apt install ffmpeg / brew install ffmpeg / pacman -S ffmpeg)"); ok = False
def have(mod):
    try: importlib.import_module(mod); return True
    except Exception: return False
missing = [pip for mod, pip in NEED if not have(mod)]
if missing and a.install:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q"] + missing)
    if r.returncode != 0:
        print("pip failed. Make a virtualenv first:  python3 -m venv .venv && . .venv/bin/activate   then run setup.py --install again")
    missing = [pip for mod, pip in NEED if not have(mod)]
for mod, pip in NEED: print(("ok   " if have(mod) else "FAIL ") + pip)
if missing: ok = False; print("\nInstall the missing ones:  python3 -m pip install " + " ".join(missing) + "   (or: python3 scripts/setup.py --install)")
for mod, pip, why in NICE: print(("ok   " if have(mod) else "opt  ") + f"{pip:<12} {'' if have(mod) else '(optional) ' + why}")
fonts = os.path.join(KIT, "..", "fonts"); want = ["Antonio-VF.ttf", "CormorantGaramond-VF.ttf", "CormorantGaramond-Italic-VF.ttf", "JetBrainsMono-VF.ttf"]
miss_f = [f for f in want if not os.path.exists(os.path.join(fonts, f))]
print("ok   fonts" if not miss_f else f"FAIL fonts missing in {fonts}: {miss_f} (copy the skill's fonts/ folder; the film will use a plain fallback font without them)")
gpu = shutil.which("nvidia-smi")
if gpu:
    r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    print("gpu  " + (r or "nvidia-smi present"))
else: print("gpu  none found: use narrator engine kokoro or piper, and score.py synth (or a music server on another machine)")
ready = ok and not miss_f
print("\nSETUP OK." if ready else "\nSETUP NOT READY: fix the FAIL lines above, then run setup.py again.")
if a.init:
    if ready: init(a.init)
    else: print("Project not created yet: fix setup first.")
elif ready: print("Next: python3 " + os.path.join(KIT, "setup.py") + " --init <new project folder>")
sys.exit(0 if ready else 1)
