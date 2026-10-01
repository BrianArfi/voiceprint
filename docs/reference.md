# voiceprint reference

[Back to the README](../README.md)

## Sources

```bash
# Live Slack. Needs a user token (xoxp-), not a bot token: a bot cannot search your messages.
export SLACK_USER_TOKEN=xoxp-...
python3 scripts/voiceprint.py ingest --source slack --out corpus.json

# An unzipped Slack workspace export. Pass --me <user id>, or --me-name to look it up in users.json.
python3 scripts/voiceprint.py ingest --source slack-export --path ./export --me-name "sam" --out corpus.json

# A WhatsApp chat export (.txt), or a directory of them.
python3 scripts/voiceprint.py ingest --source whatsapp --path ./chats --me-name "Sam" --out corpus.json

# Anything else you can dump: one JSON object per line, or plain text.
python3 scripts/voiceprint.py ingest --source jsonl --path sent.jsonl --out corpus.json
python3 scripts/voiceprint.py ingest --source text  --path sent.txt  --out corpus.json
```

For a WhatsApp chat export, `--me-name` must match your name exactly as WhatsApp writes it. Leave out `--exclude-scan` only if no AI has drafted messages for you.

## Flags

| Flag | Command | Default | Does |
| :--- | :--- | :--- | :--- |
| `--path` | ingest | none | File or directory. Required for every source except live Slack |
| `--token` | ingest | `SLACK_USER_TOKEN` | Slack user token |
| `--max-pages` | ingest | 15 | Slack search pages to pull, 100 messages each |
| `--me`, `--me-name` | ingest | none | Who you are in a Slack export or a WhatsApp chat |
| `--text-field` | ingest | `text` | The JSONL field that holds the message. `ts`, `id`, `venue` or `channel` are read when present |
| `--delimiter` | ingest | `blank` | Plain text: messages split by blank lines, or `line` for one per line |
| `--exclude-scan DIR...` | ingest | none | Folders holding AI-drafted text. Matching messages are dropped |
| `--probe-words` | ingest | 9 | How many opening words are searched for. Shorter messages cannot be attributed |
| `--samples` | analyze | 60 | Real messages kept for the short band. Medium and long keep fewer |
| `--min-freq` | analyze | 1.0 | The share of messages a phrase must appear in to be listed |
| `--repeat-cap` | analyze | 3 | How often one identical message may feed the phrase tables |
| `--name` | render | `the writer` | The name used in `voice.md` and the prompt |
| `--max-chars` | check | the profile's p75 | Override the length ceiling |
| `--rare-threshold` | check | 2.0 | A habit at or under this share of messages counts as not yours |

## What `check` fails on

Exit 1 with one `FAIL` line per problem, exit 0 with `PASS`. The draft comes from `--file`, `--text`, or standard input.

- **Over length.** Longer than the 75th percentile of what you send, or the `--max-chars` you set.
- **A habit you do not have.** A table, a heading, bold, a bulleted or numbered list, an em-dash, an ellipsis, an exclamation mark, emoji or a code block, when the profile shows it in 2% of your messages or fewer.
- **Assistant filler.** A fixed English list, such as "I wanted to reach out", "kindly", "circling back", "I hope this finds you well" and "let me know if you have any questions". A sign-off like "Best regards" on its own line fails too. This is the one fixed list in the tool, because no corpus will ever justify these phrases.

It also prints `note` lines that do not fail the draft: a draft over twice your median length, no question mark when a third or more of your messages carry one, and a capital letter at the start of a short message when a third or more of yours are entirely lowercase.

## Version and changelog from the CLI

```bash
python3 scripts/voiceprint.py --version            # voiceprint 1.0.0
python3 scripts/voiceprint.py --changelog          # list of versions
python3 scripts/voiceprint.py --changelog full     # the whole changelog
```
