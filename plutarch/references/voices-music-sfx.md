# Narrator voice, music and sound effects: what to use

Read this at steps 6 and 7. **The defaults need no GPU, no account and no key.** Use something better only if
it is already installed or the user asks. Do not spend the session installing models.

"Checked" column: **run** = ran for real while this skill was built. **mock** = the client code ran against a
fake server shaped like the documented API. **docs** = taken from the project's README (Nov 2026), not run.
If a "docs" recipe fails, fall back to the row above it; do not debug it for more than 10 minutes.

## 1. Narrator voice (`film.json` → `"narrator"`)

| you have | set `"narrator"` to | checked |
|---|---|---|
| nothing (CPU only) | `{"engine": "kokoro", "voice": "am_michael", "speed": 0.95}` | run |
| nothing, want it faster | `{"engine": "piper", "voice": "en_US-ryan-high"}` | run |
| a local TTS server that speaks the OpenAI API (Kokoro-FastAPI, LocalAI, vLLM-Omni ...) | `{"engine": "openai", "base_url": "http://localhost:8880/v1", "model": "kokoro", "voice": "am_michael"}` | mock |
| an OpenAI key (`OPENAI_API_KEY`) | `{"engine": "openai", "model": "gpt-4o-mini-tts", "voice": "onyx"}` | mock |
| an ElevenLabs key (`ELEVENLABS_API_KEY`) | `{"engine": "elevenlabs", "voice": "<voice_id>", "model": "eleven_multilingual_v2"}` | docs |
| any other TTS (Chatterbox, Qwen3-TTS, VoxCPM, Cartesia CLI ...) | `{"engine": "cmd"}`, and `PLUTARCH_NARRATOR_CMD='python3 ~/tts.py --text {text} --out {out}' python3 scripts/narrate.py` | run (with a Kokoro wrapper script, when the command was still in film.json) |

- List voices: `python3 scripts/narrate.py --voices`. Good Kokoro documentary voices: `am_michael`, `am_onyx`,
  `bm_george`, `af_heart`. Pick ONE voice for the whole film. After changing it: `narrate.py --redo`.
- film.json never holds a command or names a key, because a project can come from somebody else. `narrator.cmd` and
  `narrator.api_key_env` are refused. `{text}` and `{out}` go in `PLUTARCH_NARRATOR_CMD` without quotes around them.
  The command runs in the home folder, so give it full paths. It must not hand `{text}` to another shell (`ssh`,
  `eval`, `sh -c`): that shell would parse the line. Set the variables in front of the command, as above, because a
  fresh shell forgets an `export`, or have the user put them in their shell profile.
- `OPENAI_API_KEY` is sent only to `https://api.openai.com`. The user's own server's key goes in `PLUTARCH_TTS_KEY` and
  is sent only to servers in `PLUTARCH_TTS_HOSTS`: `PLUTARCH_TTS_KEY=... PLUTARCH_TTS_HOSTS=https://tts.example`
  (commas between servers; `https://` unless it says `http://`; a port other than the usual one has to be there).
- Start a local OpenAI-style Kokoro server (CPU): `docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest`.
- `narrate.py` listens to every line it makes. `MISREAD` means the voice said something else: spell the hard
  word the way it sounds ("Nguyen" → "Win") with the `film.py reword` line it prints, and run it again.

### Bigger local voices through `"engine": "cmd"` (docs, not run here)

Save one of these as `~/tts.py`, outside the project, so a project can't bring its own. Both need a GPU.

```python
# Chatterbox (MIT), built-in voice.  pip install chatterbox-tts
import argparse, torchaudio as ta
from chatterbox.tts import ChatterboxTTS
a = argparse.ArgumentParser(); a.add_argument("--text"); a.add_argument("--out"); a = a.parse_args()
m = ChatterboxTTS.from_pretrained(device="cuda")        # "cpu" and "mps" also work, slowly
ta.save(a.out, m.generate(a.text), m.sr)
```

```python
# Qwen3-TTS (Apache-2.0).  pip install -U qwen-tts
import argparse, torch, soundfile as sf
from qwen_tts import Qwen3TTSModel
a = argparse.ArgumentParser(); a.add_argument("--text"); a.add_argument("--out"); a = a.parse_args()
m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", device_map="cuda:0", dtype=torch.bfloat16)
wavs, sr = m.generate_custom_voice(text=a.text, language="English", speaker="Ryan", instruct="Calm documentary narrator, low and steady.")
sf.write(a.out, wavs[0], sr)
```

**Voice rule (never break it):** the narrator is a stock voice, or the user's own voice if the user gives you a
recording of themselves. Never give a cloning model a recording of the subject or of any other real person.
The subject is heard only in real recordings.

## 2. Music (`film.json` → `"music"`)

Run `python3 scripts/plan.py` first: the music is made to the film's exact length and shape.

| you have | do this | checked |
|---|---|---|
| nothing | `python3 scripts/score.py synth` → `"music": {"synth": true}`. Plain but always works. | run |
| ACE-Step 1.5 running locally (`uv run acestep-api`, port 8001) | `python3 scripts/score.py acestep` (makes 3 tracks) → `score.py pick music/acestep_*.mp3` | mock |
| any other generator, local or web (YuE, DiffRhythm, MusicGen, Stable Audio, Suno, ElevenLabs Music ...) | `python3 scripts/score.py prompt` prints the exact seconds and a timed prompt. Generate 2-3 instrumental tracks, save them in `music/`, then `python3 scripts/score.py pick music/*.mp3` | run (`prompt`, `pick`) |

- `pick` ranks the tracks by how well their loud and quiet parts follow the film and prints which to use.
  Put the winner in `"music": {"file": "music/<name>"}`. `TOO SHORT` means generate again at the printed length.
- Install ACE-Step 1.5 (MIT, under 4 GB of VRAM, Python 3.11-3.12). Docs:
  `git clone https://github.com/ACE-Step/ACE-Step-1.5.git && cd ACE-Step-1.5 && uv sync && uv run acestep-api`
- Always instrumental. No lyrics, no vocals: they fight the voices.
- The mixer does the rest: it lowers the music under every voice, goes silent just before each impact, and
  follows each scene's `energy`. Do not edit audio files by hand.

## 3. Sound effects

The mixer already makes every effect in code (run): title/end impact, riser before impacts, heartbeat for
`"bg": "pulse"`, drum hits on crowd beats for `"drums": true`. You need nothing.

To replace one with a better sound, put a file here and rerun `mix.py`:

| file | replaces | good prompt for a generator |
|---|---|---|
| `sfx/impact.wav` | the boom on the title and end card | "deep cinematic sub boom impact, long dark tail, no melody", 3-4 s |
| `sfx/riser.wav` | the swell into each impact | "tense reverse cymbal riser building to a cut", 2-3 s |

Local generators (docs): Stable Audio Open 1.0 (up to 47 s; check its license for commercial use),
MOSS-SoundEffect (Apache-2.0), Woosh (Sony), AudioGen, TangoFlux. Free libraries: Freesound (license differs
per file: check it), Kenney (CC0), Sonniss GDC bundles (royalty-free), Pixabay. BBC Sound Effects are for
non-commercial use only. Write where each file came from in `story.md`.

## After any change here

`narrate.py` (if the voice changed) → `plan.py` → `mix.py` → `render.py --mux` (sound only, takes seconds) →
`check.py`. If the narrator changed, line lengths changed too: do a full `render.py`, not `--mux`.
