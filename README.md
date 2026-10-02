# voiceprint

**Your AI drafts your messages. voiceprint tells you when they do not sound like you.**

For anyone who lets Claude, ChatGPT or an agent draft Slack and WhatsApp replies in their name.

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version 1.0.0](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen.svg)

![Animated illustration, "Catch the draft that isn't you." An AI-written draft reply to Dina slides in. One by one, lime underlines and flags land on it: "I wanted to reach out" (assistant filler), the bold summary line (bold: 0%), a three-bullet list (bullets: 0% of Sari's messages), "Kindly let me know if you have any questions" (filler: kindly) and "Best regards," (sign-off: never). A red "7 FAIL" stamp appears next to "298 chars, your p75 is 69". Then a dark card, "How Sari really writes, 300 sent messages", fills in: median length 19 chars, usual opener "can you", ends a sentence with "ya" 19%, bullets, bold and sign-offs 0%, and a real one, "can you check this ya".](docs/hero.gif)

## The problem

Sari is the sample writer whose 300 sent messages ship in `examples/`. She writes the way most people chat at work: short, lowercase, one question at a time. "can you check this ya". Half her messages are 19 characters or shorter.

On a busy afternoon she asks her AI to answer Dina on Slack about the checkout decision. The draft comes back like this:

> Hi Dina, I wanted to reach out regarding the checkout button.
>
> **Summary of the decision:**
> - The pay button will be moved to the bottom of the screen
> - ...
>
> Kindly let me know if you have any questions.
> Best regards,

It is 298 characters. Three out of four messages Sari has ever sent are 69 characters or shorter, so this one is more than four times that. She skims it, it looks fine, she sends it. Dina reads it and asks: "is this ChatGPT?"

- **The length gives it away first.** You write one line, the draft writes three paragraphs.
- **Habits you never have.** Bullets, bold and headings in a chat. "Best regards" to a teammate you talk to daily.
- **Assistant filler.** "I wanted to reach out", "kindly", "circling back". Nobody on your team says these, and they all notice.
- **"Write like me" does not fix it.** Nobody can describe how they write, so the prompt gets a guess, and the model drifts back to its own voice anyway.
- **You cannot reread every draft with fresh eyes.** By the tenth reply of the day, you approve what looks fine, and it is not you.

## Who it is for

**Good fit if you:**

- let an AI draft Slack, WhatsApp or other chat replies that go out under your name;
- can export a few hundred of your own sent messages (a Slack export, a WhatsApp chat export, JSONL or plain text), or have a Slack user token;
- want a hard check before the send, in a pre-send hook or an agent skill, not a vibe;
- want nothing sent to a model: your messages stay on your machine.

**Not for you if:**

- you want the tool to rewrite the draft for you. It flags and explains. You or your AI fix it;
- you have fewer than about 200 sent messages. The percentages are noise below that, and it will not analyze fewer than 30;
- you need the filler and sign-off checks in a language other than English. The measured parts work in any language, but those two lists are English only;
- you want an app with a UI. It is one Python script you run from a terminal or an agent.

## Before / After

| Before | After |
| :--- | :--- |
| A three-paragraph draft when you usually write one line | A draft longer than three out of four of your messages fails `check` |
| Bullets, bold and headings in a normal chat | A habit that shows up in 2% or fewer of your messages is flagged by name |
| "Kindly", "circling back" and "Best regards" slip through | A fixed list of assistant filler and sign-offs fails before the send |
| "Write like me" in the prompt, and it is still stiff | Your AI reads `voice.md`: your measured numbers plus real messages of yours |
| You find out when a teammate asks "is this ChatGPT?" | You find out from one `FAIL` line per problem, before anyone reads it |

![Animated illustration on the sample writer. Before: the AI draft reply to Dina, with flags for assistant filler, bold 0%, bullets 0%, filler x2 and sign-off, a red length bar at 298 characters far past Sari's p75 marker of 69, and "7 FAIL, exit 1". A lime line wipes across and the draft becomes Sari's version, "pay button to bottom, bayar sekarang?", the bar shrinks to 37 characters under the marker and turns lime, and the verdict reads "PASS, 37 characters against a p75 of 69, exit 0". The FAIL and PASS lines come from a real check run.](docs/before-after.gif)

## How it works

1. **Ingest your sent messages.** From live Slack, a Slack export, WhatsApp chat exports, JSONL or plain text. Point `--exclude-scan` at your old AI drafts and those messages are left out, so it does not learn the assistant's voice.
2. **Analyze.** It measures what is left: length as percentiles (median, 75th, 90th), seventeen habits such as lowercase, questions, bullets and bold, the words that end your sentences, your openers and repeated phrases. `render` turns that into `voice.md` and `voice_prompt.txt` for your AI to read before it drafts.
3. **Check each draft.** `check` holds one draft against your profile: over your 75th percentile length, a habit you almost never have, assistant filler, a sign-off.
4. **Pass or fail.** One `FAIL` line per problem and exit 1, or `PASS` and exit 0, so a pre-send hook can stop the draft. It never rewrites.

![Animated illustration in four boxes joined by arrows that draw in one at a time, with a lime dot travelling along each. 1 ingest, your sent messages: chat bubbles "is this live yet?", "sure, on it", "can you check this ya", "on my way", and an AI-drafted "Kindly advise." struck out. 2 analyze, your numbers: median 19 chars, p75 69 chars, opener "can you", ends with "ya" 19%, bullets and bold 0%. 3 check, your AI's draft: the Dina draft with its filler, bold and sign-off underlined. 4 verdict: FAIL x7, exit 1, then PASS for "pay button to bottom, bayar sekarang?", exit 0.](docs/how-it-works.gif)

The full pipeline, every command and everything it measures: [docs/how-it-works.md](docs/how-it-works.md).

## See it run

The Quick start below, run for real on the sample writer that ships in `examples/`:

![A real terminal recording. ingest reads 300 messages, analyze reports a median of 19 characters and a p75 of 69. head shows the first lines of the AI draft. check prints seven red FAIL lines and exits 1. Then check runs on the same news in the writer's style, "pay button to bottom, bayar sekarang?", and prints PASS, exit 0.](docs/demo.gif)

And what your AI gets to read. `render` writes the voice file and the prompt block from the same profile:

![A real terminal recording. render writes voice/voice.md and voice/voice_prompt.txt and says the Rules section is still yours to write. head shows the top of the prompt block: "HOW SARI WRITES (measured from 300 messages they typed themselves)", median message 19 characters, 4 words, 95% under 200 characters, a draft longer than 69 characters is longer than three out of four things they have ever sent. grep shows the sentence-ending table from voice.md: "ya" ends 19.4% of her sentences, a lift of 6.1x.](docs/voice-file.gif)

## Quick start

Try it on the synthetic writer that ships in the repo. No install, no real messages:

```bash
git clone https://github.com/BrianArfi/voiceprint && cd voiceprint
python3 scripts/voiceprint.py ingest  --source jsonl --path examples/sample_sent.jsonl --out corpus.json
python3 scripts/voiceprint.py analyze corpus.json --out profile.json
python3 scripts/voiceprint.py check   --profile profile.json --file examples/draft.md
```

On your own unzipped Slack export: `python3 scripts/voiceprint.py ingest --source slack-export --path ./export --me <your Slack user id> --out corpus.json`

Then `render` writes `voice/voice.md`. Point Claude Code or ChatGPT at `voice.md` before it drafts (see [how it works](docs/how-it-works.md)).

## Example

The writer in the sample sends short, lowercase messages (half their messages are 19 characters or shorter). An AI drafts the reply in [`examples/draft.md`](examples/draft.md), the one from the problem above. `check` prints this and exits 1:

```text
FAIL  Length 298 characters, over the p75 of 69. Longer than three out of four messages in the corpus.
FAIL  Has a bulleted list, which appears in 0.0% of their messages.
FAIL  Has bold, which appears in 0.0% of their messages.
FAIL  Assistant filler: "i wanted to reach out".
FAIL  Assistant filler: "kindly".
FAIL  Assistant filler: "let me know if you have any questions".
FAIL  Has a sign-off. Messages do not need one.
note  No question mark, but 39.3% of their messages carry one.
```

A line that sounds like the writer passes:

```text
$ python3 scripts/voiceprint.py check --profile profile.json --text "is the new label live yet?"
PASS  26 characters against a p75 of 69.
```

## Use it on your own messages

**1. Ingest your own sent messages.** Pick your source ([all sources](docs/reference.md#sources)). For a WhatsApp chat export, `--me-name` must match your name exactly as WhatsApp writes it. Point `--exclude-scan` at the folders that hold your old AI drafts, so those messages are dropped:

```bash
python3 scripts/voiceprint.py ingest --source whatsapp --path ./chats --me-name "Sam" \
    --exclude-scan ./drafts --out corpus.json
```

**2. Measure and render.**

```bash
python3 scripts/voiceprint.py analyze corpus.json --out profile.json
python3 scripts/voiceprint.py render profile.json --out-dir ./voice --name "Sam"
```

**3. Read `voice/voice.md`, and write its Rules section.** It is left blank on purpose: a frequency table cannot see how you soften an ask or when you switch language.

**4. Check each draft before it goes out.** Wire this into a pre-send hook:

```bash
python3 scripts/voiceprint.py check --profile profile.json --file draft.md
```

The `corpus.json`, `profile.json` and `voice/` outputs are gitignored.

## Using it as an agent skill

[`SKILL.md`](SKILL.md) carries the full instructions in the format Claude Code and similar harnesses read. Copy the whole directory into your skills folder:

```bash
cp -r voiceprint ~/.claude/skills/
```

Then wire `check` into a pre-send hook, so a draft is measured on the way out, not after.

## What it will not do

- **Rewrite your draft.** It flags and explains. You fix it, or your AI does, using those lines.
- **Forge typos.** It reports your rate. Adding typos on purpose is forgery, not voice.
- **Decide what to say.** It governs how a message sounds, never whether it should be sent.
- **Override a send gate.** Approval steps, confidentiality and house style still win.
- **Work on 50 messages.** Under 200 the percentages are noise, and `ingest` warns you. Under 30 usable messages `analyze` stops. Around 1,000 is where the tables get sharp.

## Privacy

The corpus is your private messages. It stays on your machine and is never sent to a model. The only network call is the optional live Slack pull, to Slack. `corpus*.json`, `profile*.json` and `voice/` are gitignored. `voice.md` and `voice_prompt.txt` quote real messages as samples, so read them before you share either file.

## Requirements

- **Python 3.8 or later.** Standard library only. Nothing to install.
- **`grep` on your PATH** for `--exclude-scan`. macOS, Linux, WSL and Git Bash have it. Without it, ingest stops with an error.
- **A Slack user token** (`xoxp-`) only for the live Slack source.
- To run the tests: `python3 tests/test_voiceprint.py`. No network, no fixtures beyond a temp folder.

## Documentation

- [How it works](docs/how-it-works.md): the pipeline, the four commands, and what it measures.
- [Reference](docs/reference.md): every source, every flag, and exactly what `check` fails on.
- [SKILL.md](SKILL.md): the instructions for Claude Code and similar agent harnesses.
- [CHANGELOG.md](CHANGELOG.md): the version history.
- The README images are rendered from [`docs/src/`](docs/src): `python docs/src/render.py` for the illustrations, `python docs/src/demo.py` for the real terminal recordings.

## FAQ

**Does it rewrite my draft?**
No. It flags the parts that are not you and says why. You fix them, or your AI uses those lines to fix them.

**Where do my messages go?**
Nowhere. They stay on your computer and are never sent to a model. Your voice file quotes a few real messages, so read it before you share it.

**Do I need an API key or a model?**
No. It is one Python file using the standard library. The only key it ever uses is your own Slack user token, and only if you pick the live Slack source.

**Which AI does it work with?**
Any. `voice.md` and `voice_prompt.txt` are plain text your AI reads before it drafts, and `check` measures any draft text you give it, from a file, `--text` or standard input.

**How many messages does it need?**
Around 200 at least, and it warns you below that. It will not analyze fewer than 30. Around 1,000 messages the tables get sharp.

**Does it work for messages that are not in English?**
Yes, for the measured parts. Length, habits, sentence endings and openers come from your own messages, in any language. The assistant filler list and the sign-off check are English only.

**What if an AI already drafted some of my old messages?**
Point `--exclude-scan` at the folders where those drafts live, and matching messages are dropped before anything is counted. `analyze` also warns when your recent messages run much longer than your older ones, which is often AI drafts the scan missed.

**Can my AI just imitate the voice file and skip the check?**
It can try, and the voice file helps. But a model drifts back to its own habits. The check does not drift: it measures each draft against the same numbers, before the send.

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md). Latest: **[1.0.0] - 2026-09-21**, the first public cut. `python3 scripts/voiceprint.py --changelog` prints it from the CLI.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

More AI skills: [BrianArfi.com/skills](https://BrianArfi.com/skills)
