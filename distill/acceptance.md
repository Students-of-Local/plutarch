# What "as good as the reference" means

Reference: the 2:38 vertical film made in the teacher session (11 scenes, 11 real-voice clips from 4 sources,
8 narrator lines). Each item below is something you can observe in a trial. "script" = `checks.sh` decides.
"teacher" = you open the film and judge. Outcomes, not method: a student that reaches these another way passes.

| # | observable | how it is checked |
|---|---|---|
| 1 | Plays on X as posted: 1080x1920, 30 fps, H.264 + AAC, at most `max_seconds`, about -14 LUFS, peak under -1 dB | script (check.py rows 1-5) |
| 2 | Every quote is real and exact: cut from a recording in `src/`, the words re-heard in the final file match the captions, each has a year and context, every source is credited on screen | script (check.py) + teacher listens to 2 quotes against the source |
| 3 | Captions land with the voice: every line within 0.10 s of the plan, word times from verified alignment. Watch the noisiest clip: this is where the reference first failed | script + teacher watches the live clip |
| 4 | Voices are always clear: every line at least 8 dB over the music, no dead air over 1.5 s | script |
| 5 | It is mostly the subject: 6 or more real-voice clips from 2 or more sources, real voice is at least half of all speaking time, and the subject has the last word | script (from out/plan.json) |
| 6 | It has the shape: cold open on real sound with a non-black first frame, a title, a turn, a payoff line, the title echoed on the end card | script (first/last scene, title, end) + teacher judges the turn and payoff |
| 7 | Facts are true and under the right date: 3 narrator/screen facts picked at random match two sources in `story.md`; no quote sits under a date it is not about | teacher |
| 8 | It looks designed: no empty or cut-off frames, one accent color, text readable at phone size | script (frame table) + teacher compares `contact.jpg` with the reference |
| 9 | The user would post it | user (distill step 8) |

Known weak spot of the reference itself (do not hold a trial to a higher bar without saying so): one quote
about an earlier year plays in the scene before its own date card.
