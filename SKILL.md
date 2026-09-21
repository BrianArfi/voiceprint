---
name: voiceprint
description: Measure how a person actually writes from their own sent messages, turn it into a voice model an agent can follow, and hold every draft to it before it is sent. Use when an assistant's drafts sound like an assistant, when setting up "write as me" for Slack, WhatsApp, or email, or when an existing voice file describes a voice the person does not have.
---

# voiceprint

Most "write in my voice" instructions are written from memory, and memory is wrong. Ask
anyone how they write and they describe how they think they write: full sentences, polite,
organised. Then you read 1,500 of their actual messages and the median is 61 characters,
37% have no capital letter anywhere, and a third end in a question.

So do not describe the voice. **Measure it.**

This skill pulls a person's own sent messages, removes the ones an AI wrote for them,
measures what is left, and writes two files: `voice.md` for a human or an agent to read,
and `voice_prompt.txt` to paste into a drafting prompt. Then it holds drafts to that
profile before they go out.

Standard library Python, no dependencies, no network except the optional Slack pull.

## When to use it

- Setting up drafting-as-a-person for the first time, on any channel.
- An agent's drafts keep reading as corporate when the person is not.
- A hand-written voice file exists and nobody knows if it is true.
- Re-measuring after a few months, because the voice moves.

## The four steps

### 1. Ingest

Pull the person's own sent messages. Five sources:

```bash
# Live Slack, needs a user token (xoxp-), not a bot token
export SLACK_USER_TOKEN=xoxp-...
python3 scripts/voiceprint.py ingest --source slack --out corpus.json

# An unzipped Slack workspace export
python3 scripts/voiceprint.py ingest --source slack-export --path ./export \
    --me-name "sam" --out corpus.json

# A WhatsApp chat export (.txt), or a directory of them
python3 scripts/voiceprint.py ingest --source whatsapp --path ./chats \
    --me-name "Sam" --out corpus.json

# Anything else you can dump
python3 scripts/voiceprint.py ingest --source jsonl --path sent.jsonl --out corpus.json
python3 scripts/voiceprint.py ingest --source text --path sent.txt --out corpus.json
```

**Filter out the messages an AI wrote for them.** This is the step everyone skips, and
skipping it is fatal: an assistant that has been drafting for six months will measure its
own output and conclude the person writes like an assistant. Drafts almost always still
exist as text in the repo or folder they were drafted in, so point at it:

```bash
python3 scripts/voiceprint.py ingest --source slack --exclude-scan ./journal ./docs \
    --out corpus.json
```

Each message's first nine words are searched for in those paths. A hit means they did not
type it, and it is dropped before anything is measured.

### 2. Analyze

```bash
python3 scripts/voiceprint.py analyze corpus.json --out profile.json
```

Produces length distribution, seventeen structural habits as a percentage of messages,
sentence-ending words ranked by **lift** (how much more often a word ends a sentence than
its general use predicts, which is what separates a tic from a noun), openers, repeated
phrases, and an evenly spread sample of real messages in three length bands.

It also splits the corpus in half by time and compares. If the recent half is much longer
than the older half, that is usually AI-drafted messages the scan missed, and it says so.

### 3. Render

```bash
python3 scripts/voiceprint.py render profile.json --out-dir ./voice --name "Sam"
```

Writes `voice/voice.md` and `voice/voice_prompt.txt`.

**One section is deliberately left blank.** The numbers are measured; the rules are not.
A frequency table cannot see how someone softens an ask, how they apologise, when they
switch language, or what warmth looks like with which person. Read the samples in
`voice.md` and write the Rules section by hand, or have an agent write it from the
samples. That is the part worth an hour of a person's attention, and the tables above it
are what make the hour productive.

Never hand-edit the numbers. The next render overwrites them.

### 4. Check

```bash
python3 scripts/voiceprint.py check --profile profile.json --file draft.md
```

Exit 1 with a numbered failure list, exit 0 on pass. Three kinds of failure:

- **Over length.** Past the 75th percentile of what they actually send.
- **A habit they do not have.** A table, a heading, bold, a bulleted list, an em-dash:
  anything the profile shows at or under 2% of messages.
- **Assistant filler.** "I wanted to reach out", "kindly", "circling back", a sign-off.
  This is the one fixed list in the skill, and it is fixed because no corpus will ever
  justify these.

It also emits `note` lines for habits the person has and the draft dropped, such as no
question mark from someone whose messages are a third questions.

Wire it into a pre-send hook so it runs on the way out, not after.

## What it will not do

- **Forge typos.** It reports the rate. Introducing them on purpose is forgery, not voice.
- **Decide what to say.** It governs how a message sounds, never whether it should be sent.
- **Override a send gate.** Approval steps, confidentiality, house style: all still win.
- **Work on 50 messages.** Under 200 the percentages are noise and it says so. Around
  1,000 is where the tables get sharp.

## Privacy

The corpus is someone's private messages. It stays local, it is never sent to a model, and
only the rendered `voice.md` and `voice_prompt.txt` are meant to travel. Add `corpus.json`
and `profile.json` to `.gitignore` unless the repo is private. `voice.md` quotes real
messages in its samples, so read the samples before sharing that file too.

## Test

```bash
python3 tests/test_voiceprint.py
```
