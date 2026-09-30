#!/usr/bin/env python3
"""Regression tests for voiceprint. No network, no fixtures on disk beyond a tmpdir."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, '..', 'scripts', 'voiceprint.py')
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import voiceprint as vp  # noqa: E402

FAILURES = []


def check(label, condition, detail=''):
    if condition:
        print('  ok   %s' % label)
    else:
        print('  FAIL %s %s' % (label, detail))
        FAILURES.append(label)


def run(*args):
    return subprocess.run([sys.executable, SCRIPT] + list(args),
                          capture_output=True, text=True)


def build_corpus_file(path):
    """A writer with strong tells: short, lowercase, sentence-final 'ya', questions."""
    short = ['got it', 'sure thanks', 'can you check this ya', 'noted bro',
             'let me check', 'is this done ya', 'ok will do', 'any update on this?',
             'nvm, sending an invite', 'sorry missed this', 'please share the doc ya']
    mid = ['can you please check this document and mark where we fulfilled on time?',
           'so the plan is to finish testing by friday, then production next week ya',
           'i am worried buyers will be confused. can we simplify the list?']
    long = ['so here is where i landed after the call. the api needs the charge field '
            'without tax, and the currency separately. but this relies on a system i '
            'do not think exists. now if we want april, we need the estimate first ya']
    with open(path, 'w', encoding='utf-8') as f:
        for i in range(600):
            text = short[i % len(short)] if i % 10 < 7 else (
                mid[i % len(mid)] if i % 10 < 9 else long[0])
            f.write(json.dumps({'id': i, 'ts': i, 'text': text}) + '\n')


def main():
    tmp = tempfile.mkdtemp(prefix='voiceprint_test_')
    jsonl = os.path.join(tmp, 'sent.jsonl')
    corpus = os.path.join(tmp, 'corpus.json')
    profile = os.path.join(tmp, 'profile.json')
    build_corpus_file(jsonl)

    print('ingest')
    r = run('ingest', '--source', 'jsonl', '--path', jsonl, '--out', corpus)
    check('exits clean', r.returncode == 0, r.stderr)
    data = json.load(open(corpus, encoding='utf-8'))
    check('kept every message', data['counts']['total'] == 600,
          'got %d' % data['counts']['total'])
    check('says the AI scan did not run', 'not scanned' in r.stdout, r.stdout)

    print('ingest, whatsapp both export formats')
    wa = os.path.join(tmp, 'chat.txt')
    with open(wa, 'w', encoding='utf-8') as f:
        f.write('[21/09/26, 19.42.11] Sam: can you check the doc ya\n'
                '[21/09/26, 19.42.30] Dana: sure, on it\n'
                '[21/09/26, 19.43.02] Sam: thanks bro\nappreciate it\n'
                '[21/09/26, 19.44.00] Sam: <Media omitted>\n'
                '21/09/2026, 19:45 - Sam: so we go live monday ya?\n'
                '21/09/2026, 19:46 - Dana: yes\n')
    wa_out = os.path.join(tmp, 'wa.json')
    r = run('ingest', '--source', 'whatsapp', '--path', wa, '--me-name', 'Sam',
            '--out', wa_out)
    msgs = json.load(open(wa_out, encoding='utf-8'))['messages']
    texts = [m['text'] for m in msgs]
    check('only my own messages', all('sure, on it' not in t for t in texts), texts)
    check('both timestamp formats parse', len(msgs) == 3, texts)
    check('continuation line joins', 'thanks bro\nappreciate it' in texts, texts)
    check('media placeholder dropped', all('Media omitted' not in t for t in texts), texts)

    print('ingest, AI-drafted filtering')
    drafts = os.path.join(tmp, 'drafts')
    os.makedirs(drafts, exist_ok=True)
    with open(os.path.join(drafts, 'd.md'), 'w', encoding='utf-8') as f:
        f.write('here is the draft\n\nso here is where i landed after the call. '
                'the api needs the charge field without tax, and the currency '
                'separately. but this relies on a system i do not think exists.\n')
    scanned = os.path.join(tmp, 'corpus_scanned.json')
    r = run('ingest', '--source', 'jsonl', '--path', jsonl, '--exclude-scan', drafts,
            '--out', scanned)
    flagged = json.load(open(scanned, encoding='utf-8'))['counts']['ai_drafted']
    check('the AI-drafted message is caught', flagged > 0, 'flagged %d' % flagged)
    no_grep = dict(os.environ, PATH=tmp)
    r = subprocess.run([sys.executable, SCRIPT, 'ingest', '--source', 'jsonl', '--path',
                        jsonl, '--exclude-scan', drafts, '--out',
                        os.path.join(tmp, 'corpus_nogrep.json')],
                       capture_output=True, text=True, env=no_grep)
    check('a missing grep stops ingest, not a silent empty scan',
          r.returncode != 0 and 'grep not found' in r.stderr, r.stderr)

    print('analyze')
    r = run('analyze', corpus, '--out', profile)
    check('exits clean', r.returncode == 0, r.stderr)
    prof = json.load(open(profile, encoding='utf-8'))
    stats = prof['stats']
    check('median length is short', stats['length']['median'] < 60,
          str(stats['length']['median']))
    check('lowercase habit measured high', stats['markers']['all_lowercase']['pct'] > 50,
          str(stats['markers']['all_lowercase']['pct']))
    check('table habit measured at zero', stats['markers']['table']['pct'] == 0.0)
    tails = prof['vocabulary']['sentence_final_words']
    check('the softener surfaces as a top tic', tails and tails[0]['word'] == 'ya',
          str(tails[:3]))
    check('lift is computed', all('lift' in t for t in tails))
    phrases = [p['gram'] for p in prof['vocabulary']['trigrams']]
    check('boilerplate does not flood the phrase table',
          len(set(phrases)) == len(phrases) and len(phrases) > 3, str(phrases[:5]))
    check('drift halves are reported', 'older_half' in prof['drift'])

    print('analyze, refuses a corpus too small to measure')
    tiny = os.path.join(tmp, 'tiny.json')
    vp.write_json(tiny, {'source': 'text', 'messages': [
        {'id': str(i), 'ts': i, 'text': 'hi', 'chars': 2, 'ai_drafted': None}
        for i in range(5)]})
    r = run('analyze', tiny, '--out', os.path.join(tmp, 'x.json'))
    check('exits non-zero', r.returncode != 0)
    check('says why', 'too few' in (r.stderr + r.stdout))

    print('render')
    out_dir = os.path.join(tmp, 'voice')
    r = run('render', profile, '--out-dir', out_dir, '--name', 'Sam')
    check('exits clean', r.returncode == 0, r.stderr)
    md = open(os.path.join(out_dir, 'voice.md'), encoding='utf-8').read()
    txt = open(os.path.join(out_dir, 'voice_prompt.txt'), encoding='utf-8').read()
    check('numbers are filled in, no leftover placeholders',
          '{' not in md.replace('{node:', '') or '{name}' not in md)
    check('the measured median reaches voice.md',
          '%d characters' % stats['length']['median'] in md)
    check('rules section is left for a human', 'unwritten' in md)
    check('prompt block names the person', 'SAM' in txt)
    check('prompt block carries the ceiling', str(stats['length']['p75']) in txt)

    print('check')
    bad = ('Hi Dana,\n\nI wanted to reach out regarding the pending document. Kindly '
           'review it at your earliest convenience.\n\n**Summary:**\n- Item one\n'
           '- Item two\n\nBest regards,\nSam')
    r = run('check', '--profile', profile, '--text', bad)
    check('rejects an assistant draft', r.returncode == 1)
    for expect in ('filler', 'sign-off', 'bulleted list', 'over the p75'):
        check('names the %s problem' % expect, expect in r.stdout, r.stdout)

    r = run('check', '--profile', profile, '--text', 'can you check the doc ya')
    check('accepts a real one', r.returncode == 0, r.stdout)

    # Short enough to pass every hard rule, but sentence-cased by a writer who
    # is lowercase 50%+ of the time. That is a note, never a failure.
    r = run('check', '--profile', profile, '--text', 'Noted, will do.')
    check('notes a dropped habit without failing', 'note' in r.stdout and r.returncode == 0,
          r.stdout)

    stdin = subprocess.run([sys.executable, SCRIPT, 'check', '--profile', profile],
                           input='got it ya', capture_output=True, text=True)
    check('reads a draft from stdin', stdin.returncode == 0, stdin.stdout + stdin.stderr)

    print('version and changelog')
    heads = [l for l in open(vp.CHANGELOG_PATH, encoding='utf-8').read().splitlines()
             if l.startswith('## [') and not l.startswith('## [Unreleased]')]
    check('newest CHANGELOG release matches __version__',
          heads and heads[0].startswith('## [%s]' % vp.__version__), heads[:1])
    ver = run('--version')
    check('--version prints the version',
          ver.returncode == 0 and ver.stdout.strip() == 'voiceprint ' + vp.__version__,
          ver.stdout + ver.stderr)
    log = run('--changelog')
    check('--changelog lists every version heading',
          log.returncode == 0 and '[1.0.0]' in log.stdout, log.stdout + log.stderr)
    full = run('--changelog', 'full')
    check('--changelog full prints the file',
          full.returncode == 0 and full.stdout.startswith('# Changelog'), full.stdout[:80])

    print()
    if FAILURES:
        print('%d failure(s): %s' % (len(FAILURES), ', '.join(FAILURES)))
        return 1
    print('all voiceprint tests passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
