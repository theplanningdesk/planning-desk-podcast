# The Planning Desk: episode renderer

Turns the weekly script from the script writer agent into a finished MP3: 10 seconds of intro music, Anna and Erik reading the news in turn, 10 seconds of outro music.

```
Sunday 06:35  News scrobbler (Claude)  ->  brief in the claude.ai Project
              Script writer (Claude)   ->  script JSON in the Project
              Voice producer (Claude)  ->  commits episodes/scripts/script-YYYY-MM-DD.json here
              GitHub Actions           ->  ElevenLabs voices every line, ffmpeg stitches it,
                                           the MP3 is published as a GitHub release
```

## One-time setup

1. Add a repository secret named `ELEVENLABS_API_KEY` (Settings > Secrets and variables > Actions > New repository secret). Create the key in ElevenLabs under Developers > API keys, with access to Text to Speech, Sound Effects and Music.
2. In ElevenLabs, add both voices to My Voices if they aren't there already: "Riley - Charismatic News Anchor/Host" (Anna) and "Robert - American standard broadcaster" (Erik).
3. Run the "Make intro and outro music" workflow once (Actions tab > Make intro and outro music > Run workflow). It tries ElevenLabs Music first and falls back to Sound Effects. The render workflow also does this automatically if the files are missing.

## Weekly

Nothing. Pushing a new file to `episodes/scripts/` starts the render. The episode appears under Releases as `episode-YYYY-MM-DD` with the MP3, a timestamped transcript and a timeline JSON.

To re-render or test: Actions > Render episode > Run workflow. Leave the script blank for the newest one, or tick "Dry run" to test the pipeline with placeholder tones and no credits.

## Changing things

Everything adjustable lives in `config.json`:

- Voices: `voices.F.voice_id` and `voices.M.voice_id`
- TTS model: `tts.model_id` (falls back to `tts.fallback_model_id` if rejected)
- Music: edit the prompts under `jingles`, then run the jingle workflow with "Replace" ticked
- Pacing and loudness: `mix` (gaps between lines and segments, fades, -16 LUFS target)
- Episode titles: `titles`. From `style_from` (1 Nov 2026) titles lead with the search topic: daily episodes use the writer's "Topic: hook" title as is, Sundays get the `weekly_prefix` ("Supply Chain News, Week 45: ..."), Saturdays the `saturday_suffix` ("The Goal by Goldratt and Cox: Book Summary"). YouTube titles put the show name last. Earlier episodes keep their old titles.

Voiced lines are cached by voice, model and text, so a re-render only pays for lines that changed.

## Cost

About one ElevenLabs credit per character: a 15-minute episode is around 13,500 characters, one take per line. GitHub Actions use is a few minutes a week, well inside the free allowance.

## Local run

```
pip install -r requirements.txt   # plus ffmpeg on the PATH
export ELEVENLABS_API_KEY=...
python make_jingles.py
python render.py episodes/scripts/script-2026-10-23-test.json
python render.py episodes/scripts/script-2026-10-23-test.json --fake   # no key, no credits
```

## Public podcast feed

Every non-test episode is also published to `docs/`, which GitHub Pages serves at
https://theplanningdesk.github.io/podcast/ :

- `feed.xml`: the RSS feed to submit to Apple Podcasts and Spotify
- `index.html`: a simple episode page with players and show notes
- `cover.png`: 3000x3000 show artwork (redraw with `python tools/make_cover.py`)
- `episodes/`: the MP3s, and `episodes.json`, the list the feed is built from

Scripts whose file name ends in `-test` are rendered and released but never published.
Show title, description, AI disclosure, categories, owner email and the Apple/Spotify links live
under `podcast` in `config.json`; after changing them, run `python publish.py --rebuild` and push.
GitHub Pages sites are limited to about 1 GB, roughly 60 episodes at 15 MB each, so after a year
or so move older MP3s out or switch to a podcast host and redirect the feed.

## Video (YouTube)

Each render also produces a 1080p video with motion graphics, made with Remotion in `video/`:
the episode audio, live captions, and animated cards driven by
`episodes/visuals/visuals-YYYY-MM-DD.json`, which the script writer creates next to the script.
Templates: headline, stat, bars, route map, list, timeline, flow, takeaway, quick hit, expert voice, plus the title and outro cards.
The MP4 is attached to the episode's GitHub release and, once the YouTube secrets exist, uploaded to
YouTube with chapters, captions, a thumbnail and the synthetic-content flag (`youtube_upload.py`).

Preview locally: `cd video && npm ci && node render.mjs --stem 2026-10-23-test --stills 16,70,140`
(needs the episode MP3 and JSON in build/out). Add `--from 0 --to 60` instead of `--stills` for a clip.

YouTube secrets: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
Privacy, category and tags live under `youtube` in `config.json`.

## Engagement stats

Every MP3 link in the feed and on the site goes through [OP3](https://op3.dev) (`https://op3.dev/e,pg=<podcast guid>/...`), a free, open-source download counter, so plays from every podcast app get counted with bots removed. Set `podcast.op3` to `false` in config.json and run `python publish.py --rebuild` to switch it off.

The "Collect stats" workflow runs every morning and saves the numbers on the `stats` branch:

- `README.md` there is the scorecard: channel totals and every episode's podcast downloads, YouTube views, Short views and Instagram numbers.
- `episodes.csv` (latest per episode), `history.csv` (every daily snapshot), `channels.csv` (followers and totals), `manual.csv` (typed-in numbers), `status.json` (which sources worked).

Sources: GitHub release downloads (built in), OP3 (secret `OP3_API_TOKEN`, a free key from op3.dev/api/keys), YouTube and Instagram (the existing upload secrets), Buttondown (the existing key). A missing secret just skips that source.

Spotify, Apple Podcasts and LinkedIn Page numbers have no API open to a show like this one. Type them in weekly: Actions > Log manual stats > Run workflow, fill in the boxes you have, leave the rest blank.
