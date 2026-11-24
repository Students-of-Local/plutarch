# Decisions and hard rules

Why the kit works the way it does, and the mistakes it was built to prevent.

## Decisions (and why)

- **Sound first, picture second.** Every picture event is timed from the finished sound. That is why captions
  and impacts land exactly: `plan.py` and `mix.py` run before any frame is drawn.
- **Real voice for feeling, narrator for facts.** A synthetic voice saying emotional lines sounds fake; a real
  person saying them is the whole reason people watch.
- **No photos or video of the person.** Original motion graphics only: no image-rights problems, and the film
  looks like one designed piece instead of a slideshow.
- **Word-by-word captions on every quote.** Most viewers watch muted, and a word that appears as it is spoken
  proves the quote is real.
- **Vertical 1080x1920, at most 140 s, about -14 LUFS.** That is what X plays best for normal accounts.
- **Cold open on real sound, music enters at the title.** The first two seconds decide whether anyone stays.
- **Local, free tools by default** (Kokoro voice, built-in score). Better engines are a swap in `film.json`,
  never a reason to stall.

## Don't

- Don't trust a quote from memory or from an article. If it is not in a recording in `src/`, it is not in the film.
- Don't put a quote under a date it is not about. (A line about one year once played over a card for another.)
- Don't make the subject "say" anything with a voice model, and don't feed any real person's voice to a
  cloning model. Narrator = stock voice.
- Don't type caption or scene times, and don't trust word times in a noisy clip without `"live": true`.
  (A caption once ran 4 seconds early because speech was hidden in crowd noise.)
- Don't keep another creator's music under a quote: use `"isolate": true`.
- Don't let the narrator praise or summarize feelings. No "legendary", "visionary", "iconic".
- Don't add a closing line the facts don't support. (An end-card line about "investigations" had to be removed.)
- Don't start on a black frame. Scene 1 is an `arena` with `reveal: hits`, or a card that starts with a clip.
- Don't run a full render to change only sound: `mix.py` then `render.py --mux`.
- Don't raise `max_seconds` above 140 unless the user says the account has Premium.
- Don't say "done", "verified" or "synced" unless `check.py` printed `ALL CHECKS PASSED` after your last change.

## Verify before you say you're done

Run `python3 scripts/check.py` **after your last change** and paste its table. It measures the finished file:
format, length, loudness, peak, dead air, black first frame, empty scenes, every line's position against the
plan (to 0.1 s), spoken words against caption words, voice over music, credits, that every quote is
verified with a year and context, that real voice is at least half of the talking, and that the subject
speaks last. Then read `story.md` once more: every fact on screen has two sources.
