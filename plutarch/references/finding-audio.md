# Finding real audio of the subject

Read this at step 2. Goal: 2-4 sources in `src/`, at least one long, clean interview and (if it exists) one
"live moment" with a crowd or room sound for the cold open.

## What makes a good source (in this order)

1. **A long interview on a podcast.** Clean voice, no music under it, direct mp3 download, and people say their
   most personal lines there. One 60-90 minute interview usually gives 5-8 usable quotes.
2. **A speech or talk** (commencement, keynote, hearing). Clean, but more formal.
3. **A live moment from the news** (phone video in a post, a press scrum). Noisy. Mark clips from it `"live": true`.
   Great for the first and last scenes.
4. **Someone else's edit** (a clip with music added). Last resort: find the original interview instead. If you
   must use it, mark the clip `"isolate": true` so their music is removed.

## How to search (use the first engine you have)

1. If your agent has its own web-search / page-fetch / video-search / transcript tools, use those first.
2. `python3 scripts/find_audio.py web "<name> interview podcast"` uses, in order: `SEARXNG_URL` (a self-hosted
   SearXNG, the best choice for local agents: `export SEARXNG_URL=http://host:8080`, JSON output must be enabled),
   `BRAVE_API_KEY`, or the `ddgs` package (no key).
3. Queries that work: `"<name>" podcast interview`, `"<name>" "full interview" <year>`, `"<name>" commencement speech`,
   `"<name>" <event> video`, and for a quote you already know: the quote in quotation marks.
4. News articles about a live event usually **embed the posts that contain the video**. Open the article, collect
   the post URLs, and `get` each one. That is how the lobby recordings in the reference film were found.

## Getting the file

| where it is | command |
|---|---|
| a podcast | `find_audio.py podcast "<show>"` → `episodes <feed> --grep "<guest>"` → `get "<mp3 url>" --name x` |
| YouTube | `find_audio.py yt "<query>"` → `subs <url>` (captions only, seconds to fetch) → `clip.py find tx/<id>.json "phrase"` → `get <url> --name x --start S --end E` |
| a post on X | `find_audio.py get "<post url>" --name x` |
| archive.org | `find_audio.py archive "<query>"` → `get "<details url>" --name x` |

If YouTube answers "Sign in to confirm you're not a bot": do not fight it. Look for the same interview as a
podcast (most shows publish both), or set `YTDLP_ARGS="--cookies-from-browser firefox"` if the user has told
you to use their own logged-in browser.

## Places with spoken-word archives

- Podcast feeds (via `find_audio.py podcast`): the show's own RSS has every episode's audio URL.
- Internet Archive (`archive`): talks, radio, old TV, conference recordings.
- Government and public-broadcast sites (speeches, hearings): US federal government recordings are public domain.
- Wikimedia Commons audio: free licenses, check each file's page.
- Paid transcript search engines exist that search inside podcasts and return timestamps (for example
  Audioscrape, PodSips, Spoken, Podchaser's API). Use one only if the user has given you a key.

## Before you move on

- Every source has a row in `story.md`: what it is, year, URL, clean or noisy.
- `film.json` → `sources` has `file`, `credit` and `url` for each.
- You have NOT used any audio you cannot name the origin of.

## Rules about other people's audio

- Keep each quote short (1-9 seconds) and use only what the story needs.
- Credit every source on screen (the kit does this from `credit`).
- Never keep another creator's music. Never present a re-edit as the original.
- The user decides whether to publish. Tell them in your final message exactly which sources are in the film.
