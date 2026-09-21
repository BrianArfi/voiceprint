# voiceprint

Your AI writes like an AI. Not because the model is bad, but because the instruction you
gave it is wrong: "write like me" is a description written from memory, and nobody
remembers how they actually write.

voiceprint measures it instead. Point it at your own sent messages. It tells you your
median message is 61 characters, that 37% have no capital letter anywhere, that a third
end in a question, and that one small word ends your sentences seven times more often than
chance. Then it writes the voice model, and holds every draft to it before it goes out.

```bash
git clone https://github.com/BrianArfi/voiceprint && cd voiceprint

python3 scripts/voiceprint.py ingest  --source slack --exclude-scan ./drafts --out corpus.json
python3 scripts/voiceprint.py analyze corpus.json --out profile.json
python3 scripts/voiceprint.py render  profile.json --out-dir ./voice --name "your name"
python3 scripts/voiceprint.py check   --profile profile.json --file draft.md
```

Sources: live Slack, a Slack workspace export, a WhatsApp chat export, JSONL, or plain
text. Python 3.8+, standard library only. No dependencies, no install step, and nothing
is sent anywhere.

## The part that matters

`--exclude-scan`. If an assistant has been drafting for you for six months, those drafts
are in your sent messages. Measure them and it learns to sound like itself. Point the scan
at wherever the drafts live and they get dropped before anything is counted.

## What you get

`voice.md` for a person or an agent to read, `voice_prompt.txt` to paste into a drafting
prompt, and `check` as a pre-send gate that exits 1 on:

- a draft longer than 75% of what you actually send
- a habit you do not have: a table, a heading, bold, a bulleted list, an em-dash
- assistant filler: "I wanted to reach out", "kindly", "circling back", a sign-off

It measures length distribution, seventeen structural habits, the words that end your
sentences far more often than chance, your openers, and your repeated phrases. It also
splits the corpus in half by time and warns you when the recent half looks different,
which usually means AI-drafted messages the scan missed.

One section of `voice.md` is left blank on purpose. Frequency tables cannot see how you
soften an ask or when you switch language. Read the real messages it sampled and write
that part yourself. It takes an hour and it is the hour that makes the file worth having.

## Using it as an agent skill

`SKILL.md` carries the full instructions in the format Claude Code and similar harnesses
read. Drop the whole directory into your skills folder:

```bash
cp -r voiceprint ~/.claude/skills/
```

Then wire `check` into a pre-send hook so a draft is measured on the way out, not after.

## Privacy

The corpus is your private messages. It stays on your machine and is never sent to a
model. `corpus.json` and `profile.json` are gitignored. `voice.md` quotes real messages as
samples, so read them before you share that file.

## Tests

```bash
python3 tests/test_voiceprint.py
```

## License

MIT. See [LICENSE](LICENSE).
