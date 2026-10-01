# voiceprint

**Your AI drafts your messages. voiceprint tells you when they do not sound like you.**

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version 1.0.0](https://img.shields.io/badge/version-1.0.0-green.svg)](CHANGELOG.md)
[![GitHub stars](https://img.shields.io/github/stars/BrianArfi/voiceprint?style=social)](https://github.com/BrianArfi/voiceprint/stargazers)

![Headline: "Catch the draft that isn't you." Left, a draft reply to Dina marked "written by your AI", with lime underlines and flags on "I wanted to reach out" (assistant filler), a three-bullet list (bullets: 0% of Sari's messages) and "Best regards," (sign-off), plus a footer reading 7 FAIL, 298 chars against a p75 of 69. Right, "How Sari really writes" from 300 sent messages: median length 19 chars, usual opener "can you", ends a sentence with "ya" 19% of the time, bullets, bold and sign-offs 0%, and a real sample, "can you check this ya". The draft text is left as is: it flags, it does not rewrite.](docs/hero.png)

## Why

You let Claude or ChatGPT draft your Slack replies and work chats, and the drafts sound like AI: three paragraphs where you write one line, bullets and bold in a chat, "Kindly" and "Best regards" to a teammate. "Write like me" in the prompt does not fix it, because nobody remembers how they actually write. Then a teammate asks: "Is this ChatGPT?"

## What it does

- **Learns your voice from messages you already sent** (Slack, WhatsApp, JSONL or plain text), not from a description.
- **Leaves out the messages an AI already drafted for you**, so it does not learn the assistant's voice.
- **Writes a voice file** with your numbers and real sample messages, for your AI to read before it drafts.
- **Flags a draft that is not you** before you send it: too long, a habit you never have, assistant filler, a sign-off. It names each problem. It does not rewrite.
- **Nothing goes to an AI model.** One Python file, standard library only. It reads Slack through the Slack API with your own token, or from an export file.

![A terminal runs the Quick start on the sample writer. ingest reads 300 messages, analyze reports a median of 19 characters and a p75 of 69. cat shows the AI draft with bold, bullets, "Kindly" and "Best regards,". check prints seven red FAIL lines and exits 1. Then check runs on the same news in the writer's style, "pay button goes to the bottom, label is bayar sekarang. ok ya?", and prints PASS, exit 0.](docs/demo.gif)

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

The writer in the sample sends short, lowercase messages (half their messages are 19 characters or shorter). An AI drafts this for them, in [`examples/draft.md`](examples/draft.md):

> Hi Dina, I wanted to reach out regarding the checkout button.
>
> **Summary of the decision:**
> - The pay button will be moved to the bottom of the screen
> - ...
>
> Kindly let me know if you have any questions.
> Best regards,

`check` prints this and exits 1:

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

---

## Documentation

- [How it works](docs/how-it-works.md): the pipeline, the four commands, and what it measures.
- [Reference](docs/reference.md): every source, every flag, and exactly what `check` fails on.
- [SKILL.md](SKILL.md): the instructions for Claude Code and similar agent harnesses.
- [CHANGELOG.md](CHANGELOG.md): the version history.

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

## FAQ

**Does it rewrite my draft?**
No. It flags the parts that are not you and says why. You fix them, or your AI uses those lines to fix them.

**Where do my messages go?**
Nowhere. They stay on your computer and are never sent to a model. Your voice file quotes a few real messages, so read it before you share it.

**How many messages does it need?**
Around 200 at least, and it warns you below that. It will not analyze fewer than 30. Around 1,000 messages the tables get sharp.

**Does it work for messages that are not in English?**
Yes, for the measured parts. Length, habits, sentence endings and openers come from your own messages, in any language. The assistant filler list and the sign-off check are English only.

**Can my AI just imitate the voice file and skip the check?**
It can try, and the voice file helps. But a model drifts back to its own habits. The check does not drift: it measures each draft against the same numbers, before the send.

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md). Latest: **[1.0.0] - 2026-09-21**, the first public cut. `python3 scripts/voiceprint.py --changelog` prints it from the CLI.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

More AI skills: https://brianarfi.com/skills
