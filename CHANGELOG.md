# Changelog

All notable changes to voiceprint are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project uses [Semantic Versioning](https://semver.org/).

`python3 scripts/voiceprint.py --changelog` lists the versions below;
`--changelog full` prints this file.

## [Unreleased]
<!-- source: branch feat/changelog, this change set. -->

### Added
- `--version` prints the version, and `--changelog` prints this changelog (a list of versions, or `full` for the whole file).
- This `CHANGELOG.md`, backfilled from the git history.

## [1.0.0] - 2026-09-21
<!-- source: git commit f53eb12 "voiceprint: measure how you actually write, then hold drafts to it" (2026-09-21 20:14 +0700), the initial and only commit. No git tag or GitHub release exists; 1.0.0 labels this first public cut. -->

### Added
- `ingest`: pulls your own sent messages from live Slack, a Slack workspace export, a WhatsApp chat export, JSONL or plain text into a corpus.
- `--exclude-scan`: drops messages an AI drafted for you before anything is counted.
- `analyze`: measures length distribution, structural habits, sentence-ending words by lift, openers and repeated phrases, and warns when the recent half of the corpus looks different.
- `render`: writes `voice.md` and `voice_prompt.txt`.
- `check`: holds a draft against the profile and exits 1 on a draft that is too long, a habit you do not have, or assistant filler.
- Standard library only. `SKILL.md` for agent harnesses, regression tests in `tests/test_voiceprint.py`, MIT license.

[Unreleased]: https://github.com/BrianArfi/voiceprint/compare/f53eb12...feat/changelog
[1.0.0]: https://github.com/BrianArfi/voiceprint/commit/f53eb12
