#!/usr/bin/env python3
"""voiceprint - measure how a person actually writes, then hold drafts to it.

Four steps, four subcommands:

    ingest   pull the person's own sent messages into a corpus
    analyze  measure the corpus into a profile (numbers, tics, samples)
    render   write voice.md + voice_prompt.txt an agent can read
    check    hold a draft against the profile before it is sent

Standard library only, on purpose. This file is meant to be copied into any repo
and run with nothing installed.

    python3 voiceprint.py ingest --source slack --out corpus.json
    python3 voiceprint.py analyze corpus.json --out profile.json
    python3 voiceprint.py render profile.json --out-dir ./voice
    python3 voiceprint.py check --profile profile.json --file draft.md
    python3 voiceprint.py --version | --changelog [list|full]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter

__version__ = '1.0.0'
CHANGELOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'CHANGELOG.md')
CHANGELOG_URL = 'https://github.com/BrianArfi/voiceprint/blob/main/CHANGELOG.md'

# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

URL_RE = re.compile(r'<?https?://[^\s>|]+>?')
SLACK_ENTITY_RE = re.compile(r'<[@#!][^>]*>')
WORD_RE = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)


def strip_noise(text):
    """Text with links and mentions removed, for word-level statistics."""
    t = URL_RE.sub(' ', text)
    t = SLACK_ENTITY_RE.sub(' ', t)
    return re.sub(r'\s+', ' ', t).strip()


def tokens(text):
    return WORD_RE.findall(strip_noise(text).lower())


def pct(part, whole):
    return 0.0 if not whole else round(100.0 * part / whole, 1)


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, data):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)


def die(msg):
    sys.exit('voiceprint: ' + msg)


# --------------------------------------------------------------------------
# ingest
# --------------------------------------------------------------------------

def slack_api(token, method, params):
    url = 'https://slack.com/api/%s?%s' % (method, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    last = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as exc:  # network flake, rate limit, 5xx
            last = exc
            time.sleep(2 * (attempt + 1))
    return {'ok': False, 'error': 'request failed: %s' % last}


def ingest_slack(args):
    """Own messages via search.messages, using a user token (xoxp-)."""
    token = args.token or os.environ.get('SLACK_USER_TOKEN')
    if not token:
        die('set SLACK_USER_TOKEN (a user token, xoxp-...) or pass --token')
    if not token.startswith('xoxp-'):
        print('warning: a bot token cannot search your own messages, you need xoxp-',
              file=sys.stderr)

    who = slack_api(token, 'auth.test', {})
    if not who.get('ok'):
        die('auth.test failed: %s' % who.get('error'))
    uid = who['user_id']
    print('authenticated as %s (%s)' % (who.get('user'), uid), file=sys.stderr)

    rows = []
    for page in range(1, args.max_pages + 1):
        res = slack_api(token, 'search.messages', {
            'query': 'from:<@%s>' % uid,
            'count': 100,
            'page': page,
            'sort': 'timestamp',
        })
        if not res.get('ok'):
            print('search failed on page %d: %s' % (page, res.get('error')), file=sys.stderr)
            break
        block = res['messages']
        for m in block['matches']:
            channel = m.get('channel') or {}
            rows.append({
                'id': m.get('ts'),
                'ts': float(m.get('ts') or 0),
                'venue': channel.get('name') or ('dm' if channel.get('is_im') else None),
                'is_dm': bool(channel.get('is_im')),
                'text': m.get('text') or '',
            })
        paging = block.get('paging', {})
        print('page %d: %d messages (total %s)' % (page, len(block['matches']),
                                                   paging.get('total')), file=sys.stderr)
        if page >= paging.get('pages', 1):
            break
        time.sleep(1)
    return rows


def ingest_slack_export(args):
    """Own messages from an official Slack workspace export directory."""
    root = args.path
    if not root or not os.path.isdir(root):
        die('--path must point at an unzipped Slack export directory')

    uid = args.me
    users_file = os.path.join(root, 'users.json')
    if not uid and os.path.exists(users_file):
        needle = (args.me_name or '').lower()
        for u in load_json(users_file):
            names = {u.get('name', ''), u.get('real_name', ''),
                     (u.get('profile') or {}).get('display_name', '')}
            if needle and needle in ' '.join(n.lower() for n in names if n):
                uid = u['id']
                break
    if not uid:
        die('pass --me <SLACK_USER_ID>, or --me-name to look it up in users.json')
    print('filtering export for user %s' % uid, file=sys.stderr)

    rows = []
    for dirpath, _dirnames, filenames in os.walk(root):
        channel = os.path.basename(dirpath)
        for name in filenames:
            if not re.match(r'^\d{4}-\d{2}-\d{2}\.json$', name):
                continue
            try:
                day = load_json(os.path.join(dirpath, name))
            except (ValueError, OSError):
                continue
            for m in day:
                if m.get('user') != uid or m.get('subtype'):
                    continue
                rows.append({
                    'id': m.get('ts'),
                    'ts': float(m.get('ts') or 0),
                    'venue': channel,
                    'is_dm': channel.startswith('D'),
                    'text': m.get('text') or '',
                })
    return rows


# WhatsApp writes two shapes depending on platform and locale.
WA_BRACKET_RE = re.compile(
    r'^\[(?P<stamp>[^\]]+)\]\s*(?P<who>[^:]{1,60}):\s?(?P<text>.*)$')
WA_DASH_RE = re.compile(
    r'^(?P<stamp>\d{1,2}[/.]\d{1,2}[/.]\d{2,4},?\s+\d{1,2}[:.]\d{2}(?::\d{2})?(?:\s?[APap][Mm])?)'
    r'\s+-\s+(?P<who>[^:]{1,60}):\s?(?P<text>.*)$')


def ingest_whatsapp(args):
    """Own messages from an exported WhatsApp chat .txt (or a directory of them)."""
    if not args.me_name:
        die('--me-name is required, it must match your name exactly as WhatsApp writes it')
    paths = []
    if os.path.isdir(args.path):
        for name in sorted(os.listdir(args.path)):
            if name.lower().endswith('.txt'):
                paths.append(os.path.join(args.path, name))
    else:
        paths = [args.path]
    if not paths:
        die('no .txt chat export found at %s' % args.path)

    me = args.me_name.strip().lower()
    rows = []
    for path in paths:
        venue = os.path.splitext(os.path.basename(path))[0]
        current = None
        with open(path, encoding='utf-8', errors='replace') as f:
            for raw in f:
                # WhatsApp uses a narrow no-break space around the time on iOS.
                line = unicodedata.normalize('NFKC', raw).rstrip('\n')
                m = WA_BRACKET_RE.match(line) or WA_DASH_RE.match(line)
                if m:
                    if current:
                        rows.append(current)
                        current = None
                    if m.group('who').strip().lower() != me:
                        continue
                    text = m.group('text')
                    if text.strip() in ('<Media omitted>', 'null', ''):
                        continue
                    current = {
                        'id': '%s|%s' % (venue, m.group('stamp')),
                        'ts': 0.0,
                        'venue': venue,
                        'is_dm': True,
                        'text': text,
                    }
                elif current is not None:
                    current['text'] += '\n' + line
        if current:
            rows.append(current)
    # Export order is chronological, so position stands in for a timestamp.
    for i, r in enumerate(rows):
        r['ts'] = float(i)
    return rows


def ingest_jsonl(args):
    """Own messages from a JSONL file, one object per line."""
    rows = []
    with open(args.path, encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            text = obj.get(args.text_field)
            if not text:
                continue
            rows.append({
                'id': str(obj.get('id') or i),
                'ts': float(obj.get('ts') or i),
                'venue': obj.get('venue') or obj.get('channel'),
                'is_dm': bool(obj.get('is_dm')),
                'text': text,
            })
    return rows


def ingest_text(args):
    """Own messages from a plain text file: blank-line separated, or one per line."""
    with open(args.path, encoding='utf-8') as f:
        blob = f.read()
    chunks = re.split(r'\n\s*\n', blob) if args.delimiter == 'blank' else blob.split('\n')
    rows = []
    for i, chunk in enumerate(chunks):
        text = chunk.strip('\n').strip()
        if text:
            rows.append({'id': str(i), 'ts': float(i), 'venue': None,
                         'is_dm': False, 'text': text})
    return rows


def flag_ai_drafted(rows, scan_dirs, min_words):
    """Mark messages that an AI wrote for you, so they never train the profile.

    A draft an assistant produced for you almost always still exists as text in
    the repo it was drafted in. So take a distinctive slice of each message and
    look for it there. A hit means you did not type it.

    True = found in the scanned tree, False = not found, None = too short to tell.
    """
    hit_cache, warned = {}, set()
    for r in rows:
        clean = strip_noise(r['text'])
        words = clean.split()
        if len(words) < min_words:
            r['ai_drafted'] = None
            continue
        probe = ' '.join(words[:min_words])
        if probe in hit_cache:
            r['ai_drafted'] = hit_cache[probe]
            continue
        found = False
        for d in scan_dirs:
            try:
                res = subprocess.run(['grep', '-rlF', '--', probe, d],
                                     capture_output=True, text=True, timeout=60)
            except OSError:
                die('grep not found on PATH: --exclude-scan cannot search %s, so no '
                    'AI-drafted message would be dropped. Install grep, or drop '
                    '--exclude-scan if no AI has drafted messages for you.' % d)
            except subprocess.SubprocessError as e:
                warned.add(d)
                print('warning: scan of %s failed (%s), treated as no match'
                      % (d, e.__class__.__name__), file=sys.stderr)
                continue
            if res.returncode > 1 and d not in warned:
                warned.add(d)
                print('warning: grep could not read all of %s: %s'
                      % (d, res.stderr.strip()[:200]), file=sys.stderr)
            if res.stdout.strip():
                found = True
                break
        hit_cache[probe] = found
        r['ai_drafted'] = found
    return rows


def cmd_ingest(args):
    handler = {
        'slack': ingest_slack,
        'slack-export': ingest_slack_export,
        'whatsapp': ingest_whatsapp,
        'jsonl': ingest_jsonl,
        'text': ingest_text,
    }[args.source]
    if args.source != 'slack' and not args.path:
        die('--path is required for --source %s' % args.source)

    rows = handler(args)
    rows = [r for r in rows if (r['text'] or '').strip()]

    seen, uniq = set(), []
    for r in rows:
        if r['id'] in seen:
            continue
        seen.add(r['id'])
        r['chars'] = len(r['text'])
        uniq.append(r)
    uniq.sort(key=lambda r: r['ts'])

    if args.exclude_scan:
        missing = [d for d in args.exclude_scan if not os.path.isdir(d)]
        if missing:
            die('--exclude-scan paths do not exist: %s' % ', '.join(missing))
        if not shutil.which('grep'):
            die('grep not found on PATH: --exclude-scan needs it to search your drafts. '
                'Install grep (macOS, Linux, WSL and Git Bash ship it), or drop '
                '--exclude-scan if no AI has drafted messages for you.')
        print('scanning %d path(s) for AI-drafted messages' % len(args.exclude_scan),
              file=sys.stderr)
        flag_ai_drafted(uniq, args.exclude_scan, args.probe_words)
    else:
        for r in uniq:
            r['ai_drafted'] = None

    corpus = {
        'source': args.source,
        'messages': uniq,
        'counts': {
            'total': len(uniq),
            'ai_drafted': sum(1 for r in uniq if r['ai_drafted'] is True),
            'unattributed': sum(1 for r in uniq if r['ai_drafted'] is None),
        },
    }
    corpus['ai_scan'] = bool(args.exclude_scan)
    write_json(args.out, corpus)
    c = corpus['counts']
    if args.exclude_scan:
        print('wrote %s: %d messages (%d AI-drafted, %d too short to attribute)'
              % (args.out, c['total'], c['ai_drafted'], c['unattributed']))
    else:
        print('wrote %s: %d messages, not scanned for AI-drafted sends. Pass '
              '--exclude-scan <dir> to filter those out.' % (args.out, c['total']))
    if c['total'] < 200:
        print('warning: under 200 messages, the percentages will be noisy', file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# analyze
# --------------------------------------------------------------------------

# Structural markers. Deliberately language-neutral: no English wordlist decides
# whether something is in your voice, the corpus does.
MARKERS = [
    ('starts_lowercase', r'^[a-z]', 0),
    ('all_lowercase', r'^[^A-Z]*$', 0),
    ('question_mark', r'\?', 0),
    ('exclamation', r'!', 0),
    ('ellipsis', r'\.\.\.', 0),
    ('em_dash', r'—', 0),
    ('emoji_shortcode', r':[a-z0-9_+-]+:', re.I),
    ('unicode_emoji', r'[\U0001F300-\U0001FAFF☀-➿]', 0),
    ('mention', r'<@[UW][A-Z0-9]+>|(?<!\S)@\w', 0),
    ('link', r'https?://', 0),
    ('bullet_list', r'(?m)^\s*[-*•]\s+\S', 0),
    ('numbered_list', r'(?m)^\s*\d+[.)]\s+\S', 0),
    ('bold', r'\*[^*\n]+\*|\*\*[^*\n]+\*\*', 0),
    ('heading', r'(?m)^#{1,6}\s+\S', 0),
    ('table', r'(?m)^\s*\|.*\|\s*$', 0),
    ('code_block', r'```', 0),
    ('multi_paragraph', r'\n\s*\n', 0),
]


def percentile(sorted_values, p):
    if not sorted_values:
        return 0
    k = min(len(sorted_values) - 1, int(round((p / 100.0) * (len(sorted_values) - 1))))
    return sorted_values[k]


def vocab_pool(msgs, cap):
    """The corpus with boilerplate capped, for word and phrase counting.

    One message sent verbatim fifty times is one phrase habit, not fifty. Left
    uncapped it floods every n-gram table with the text of whatever gets pasted
    most. Length and shape statistics still use the full corpus, because sending
    the same two words fifty times genuinely is how the person writes.
    """
    seen, pool = Counter(), []
    for r in msgs:
        key = re.sub(r'\s+', ' ', strip_noise(r['text']).lower()).strip()
        if seen[key] >= cap:
            continue
        seen[key] += 1
        pool.append(r)
    return pool


def ngram_profile(msgs, n, min_msgs):
    """n-grams ranked by how many messages carry them, not by raw count.

    Message-frequency is the right unit: one long message repeating a phrase
    eight times is one habit, not eight.
    """
    counts = Counter()
    for r in msgs:
        toks = tokens(r['text'])
        grams = {' '.join(toks[i:i + n]) for i in range(len(toks) - n + 1)}
        counts.update(grams)
    total = len(msgs)
    return [{'gram': g, 'messages': c, 'pct': pct(c, total)}
            for g, c in counts.most_common() if c >= min_msgs]


def sentence_tails(msgs, limit, min_count):
    """Words that land at the end of a sentence far more often than chance.

    Raw end-of-sentence frequency mostly returns nouns, because every sentence
    ends on something. What identifies a writer is the word that ends sentences
    at a much higher rate than it appears generally: a softener, a hedge, a tic.
    So rank by lift, not by count.
    """
    tail_counts, all_counts = Counter(), Counter()
    for r in msgs:
        clean = strip_noise(r['text'])
        all_counts.update(WORD_RE.findall(clean.lower()))
        for part in re.split(r'[.!?\n]+', clean):
            toks = WORD_RE.findall(part.lower())
            if toks:
                tail_counts[toks[-1]] += 1
    tail_total, all_total = sum(tail_counts.values()), sum(all_counts.values())
    if not tail_total or not all_total:
        return []

    out = []
    for word, count in tail_counts.items():
        if count < min_count:
            continue
        share_tail = count / tail_total
        # Smoothed, so a word used twice in the whole corpus cannot top the table
        # on a denominator of two.
        share_all = (all_counts[word] + 0.5) / (all_total + 0.5 * len(all_counts))
        out.append({
            'word': word,
            'count': count,
            'pct': round(100.0 * share_tail, 1),
            'lift': round(share_tail / share_all, 1) if share_all else 0.0,
        })
    out.sort(key=lambda d: (-d['lift'], -d['count']))
    return out[:limit]


def openers(msgs, limit):
    counts = Counter()
    for r in msgs:
        toks = tokens(r['text'])
        if toks:
            counts[' '.join(toks[:2]) if len(toks) > 1 else toks[0]] += 1
    return [{'opener': o, 'count': c, 'pct': pct(c, len(msgs))}
            for o, c in counts.most_common(limit)]


def measure(msgs):
    """Every number the rendered profile quotes."""
    total = len(msgs)
    lens = sorted(len(r['text']) for r in msgs)
    word_counts = sorted(len(tokens(r['text'])) for r in msgs)
    out = {
        'messages': total,
        'length': {
            'p10': percentile(lens, 10), 'p25': percentile(lens, 25),
            'median': percentile(lens, 50), 'p75': percentile(lens, 75),
            'p90': percentile(lens, 90), 'max': lens[-1] if lens else 0,
            'under_80_pct': pct(sum(1 for x in lens if x < 80), total),
            'under_200_pct': pct(sum(1 for x in lens if x < 200), total),
            'over_500_pct': pct(sum(1 for x in lens if x > 500), total),
        },
        'words': {
            'median': percentile(word_counts, 50),
            'p75': percentile(word_counts, 75),
            'p90': percentile(word_counts, 90),
        },
        'markers': {},
    }
    for name, pattern, flags in MARKERS:
        hits = sum(1 for r in msgs if re.search(pattern, r['text'], flags))
        out['markers'][name] = {'messages': hits, 'pct': pct(hits, total)}
    return out


def sample(msgs, lo, hi, want):
    """An evenly spread sample across the whole time range, not the first N."""
    band = [r for r in msgs if lo <= len(r['text']) < hi]
    if not band:
        return []
    step = max(1, len(band) // want)
    return [{'venue': r.get('venue'), 'text': r['text']} for r in band[::step][:want]]


def cmd_analyze(args):
    corpus = load_json(args.corpus)
    rows = corpus['messages']
    own = [r for r in rows if r.get('ai_drafted') is not True]
    if len(own) < 30:
        die('only %d usable messages, that is too few to measure anything' % len(own))
    own.sort(key=lambda r: r.get('ts') or 0)

    pool = vocab_pool(own, args.repeat_cap)
    min_msgs = max(2, int(len(pool) * args.min_freq / 100.0))
    min_tail = max(2, int(len(pool) * 0.005))
    profile = {
        'generated_from': os.path.abspath(args.corpus),
        'source': corpus.get('source'),
        'excluded_ai_drafted': sum(1 for r in rows if r.get('ai_drafted') is True),
        'ai_scan': corpus.get('ai_scan', False),
        'stats': measure(own),
        'vocabulary': {
            'counted_messages': len(pool),
            'top_words': [{'word': w, 'count': c}
                          for w, c in Counter(
                              t for r in pool for t in tokens(r['text'])).most_common(80)],
            'sentence_final_words': sentence_tails(pool, 40, min_tail),
            'openers': openers(pool, 25),
            'bigrams': ngram_profile(pool, 2, min_msgs)[:60],
            'trigrams': ngram_profile(pool, 3, min_msgs)[:40],
            'fourgrams': ngram_profile(pool, 4, min_msgs)[:25],
        },
        'samples': {
            'short': sample(own, 0, 90, args.samples),
            'medium': sample(own, 90, 400, max(10, args.samples // 2)),
            'long': sample(own, 400, 10 ** 9, max(5, args.samples // 6)),
        },
    }

    # Drift check. If the recent half looks different from the older half, the
    # recent half is usually contaminated by AI drafts that the scan missed.
    cut = len(own) // 2
    profile['drift'] = {
        'older_half': measure(own[:cut])['length'],
        'recent_half': measure(own[cut:])['length'],
    }
    write_json(args.out, profile)

    s = profile['stats']
    print('wrote %s' % args.out)
    print('  %d messages measured, %d AI-drafted excluded'
          % (s['messages'], profile['excluded_ai_drafted']))
    print('  median %d chars, p75 %d, under 200 chars %.0f%%'
          % (s['length']['median'], s['length']['p75'], s['length']['under_200_pct']))
    older, recent = profile['drift']['older_half'], profile['drift']['recent_half']
    if recent['median'] > older['median'] * 1.6 and older['median'] > 0:
        print('  warning: recent messages are much longer than older ones. Either your '
              'writing changed, or AI-drafted sends are still in the corpus.',
              file=sys.stderr)
    return 0


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def _rows(items, key, label, limit):
    lines = ['| %s | Messages | Share |' % label, '| :--- | ---: | ---: |']
    for it in items[:limit]:
        lines.append('| `%s` | %s | %s%% |'
                     % (it[key], it.get('messages', it.get('count')), it['pct']))
    return '\n'.join(lines)


def _tail_rows(items, limit):
    lines = ['| Last word of a sentence | Ends sentences | Share of endings | Lift |',
             '| :--- | ---: | ---: | ---: |']
    for it in items[:limit]:
        lines.append('| `%s` | %s | %s%% | %sx |'
                     % (it['word'], it['count'], it['pct'], it['lift']))
    return '\n'.join(lines)


VOICE_MD = """# {name}'s voice

Measured from **{messages} messages {name} typed** ({source}){excluded_note}. This file
says how {name} sounds. It does not override any send gate, approval step, or house style
rule. Those still win.

> Regenerate with `voiceprint analyze` then `voiceprint render`. Do not hand-edit the
> numbers: they come from the corpus, and the next render overwrites them.

## The one-line model

{oneliner}

## Length, which is the biggest tell

| Measure | Value |
| :--- | :--- |
| Median message | **{median} characters** |
| Median word count | **{median_words} words** |
| Under 80 characters | {under80}% |
| Under 200 characters | **{under200}%** |
| 75th percentile | {p75} characters |
| 90th percentile | {p90} characters |
| Over 500 characters | {over500}% |

**A draft over {p75} characters is longer than three out of four things {name} has ever
sent.** When a draft goes past it, the extra length has to be carrying facts that cannot
be dropped. Explanation nobody asked for is not one.

## How the messages are shaped

| Habit | Share of messages |
| :--- | ---: |
{marker_rows}

Read that table as permissions. A habit near 0% is effectively banned: if {name} has never
put a table in a message, a table is not in {name}'s voice no matter how tidy it looks. A
habit above 30% is expected, and a draft without it will read as somebody else.

## Sentence endings

Softeners, hedges and tics live on the last word of a sentence, so this is the most
diagnostic list in the file. **Lift** is how much more often the word ends a sentence than
its overall use would predict. A lift of 1x is an ordinary word that happened to land at
the end. Anything above 3x is a tic, and the tics are the voice.

{tail_rows}

## How messages open

{opener_rows}

## Repeated phrases

These are the phrases {name} reaches for, ranked by how many messages carry them.

{phrase_rows}

## Real messages

Write like these. Not like a tidied version of these.

### Short
{short_samples}

### Medium
{medium_samples}

### Long
{long_samples}

## Rules

<!-- Written by a human or an agent reading the samples above. The numbers are
     measured; these are not. Delete this comment once they are filled in. -->

{rules}

## The test before a draft goes out

1. **Is it under {p75} characters?** If not, is the extra length carrying facts that could
   not be dropped?
2. **Could this have been two messages instead of one paragraph?**
3. **Does it use the habits above at roughly the right rate**, and avoid the ones near 0%?
4. **Read it out loud in their voice.** If it sounds like a status report, rewrite it.
"""

RULES_PLACEHOLDER = """1. _(unwritten)_ Read the samples above and name the habit a
   frequency table cannot see: how they soften an ask, how they apologise, how they
   share a link, when they switch language or register, what warmth looks like with
   whom.
2. _(unwritten)_ Add a "never do this" list, drawn from what the tables show at
   roughly 0%.
3. _(unwritten)_ Add calibration pairs: the real message on the left, the flat
   assistant version on the right."""

PROMPT_TXT = """HOW {upper} WRITES (measured from {messages} messages they typed themselves)

Length is the biggest tell. Median message is {median} characters, {median_words} words.
{under200}% are under 200 characters. A draft longer than {p75} characters is longer than
three out of four things they have ever sent. Cut it.

Shape, as measured:
{prompt_markers}

A habit at or near 0% is banned. A habit above 30% is expected.

Their sentence endings, most common first:
{prompt_tails}

Their openers: {prompt_openers}

Their repeated phrases: {prompt_phrases}

Real messages of theirs, to match:
{prompt_samples}

Before handing over a draft:
1. Under {p75} characters, or is the extra carrying facts that cannot be dropped?
2. Could it have been two short messages instead of one paragraph?
3. Does it use their habits at roughly the right rate, and avoid the ones near 0%?
4. Read it in their voice. If it sounds like a status report, it is not them.
"""

MARKER_LABELS = {
    'starts_lowercase': 'Starts with a lowercase letter',
    'all_lowercase': 'Entirely lowercase, no capitals at all',
    'question_mark': 'Contains a question mark',
    'exclamation': 'Contains an exclamation mark',
    'ellipsis': 'Uses an ellipsis',
    'em_dash': 'Uses an em-dash',
    'emoji_shortcode': 'Uses an emoji shortcode',
    'unicode_emoji': 'Uses an emoji character',
    'mention': 'Mentions someone',
    'link': 'Contains a link',
    'bullet_list': 'Uses a bulleted list',
    'numbered_list': 'Uses a numbered list',
    'bold': 'Uses bold',
    'heading': 'Uses a heading',
    'table': 'Uses a table',
    'code_block': 'Uses a code block',
    'multi_paragraph': 'Runs to more than one paragraph',
}


def build_oneliner(stats):
    """One sentence describing the writer, assembled from what actually measured high."""
    length = stats['length']
    traits = []
    if length['median'] < 120:
        traits.append('short')
    elif length['median'] < 300:
        traits.append('compact')
    else:
        traits.append('expansive')
    m = stats['markers']
    if m['all_lowercase']['pct'] > 20:
        traits.append('often entirely lowercase')
    if m['question_mark']['pct'] > 25:
        traits.append('asks rather than announces')
    if m['multi_paragraph']['pct'] < 20:
        traits.append('one thing per message')
    if m['bullet_list']['pct'] + m['numbered_list']['pct'] < 10:
        traits.append('prose, not lists')
    if m['emoji_shortcode']['pct'] + m['unicode_emoji']['pct'] > 15:
        traits.append('uses emoji freely')
    return 'They write **' + ', '.join(traits) + '.**'


def fmt_samples(items, limit):
    if not items:
        return '_(none in this band)_'
    out = []
    for s in items[:limit]:
        body = '\n'.join('> ' + line for line in s['text'].split('\n'))
        out.append(body)
    return '\n>\n'.join(out) if len(out) == 1 else '\n\n'.join(out)


def cmd_render(args):
    profile = load_json(args.profile)
    stats, vocab = profile['stats'], profile['vocabulary']
    length, markers = stats['length'], stats['markers']
    name = args.name

    marker_rows = '\n'.join(
        '| %s | %s%% |' % (MARKER_LABELS.get(k, k), v['pct'])
        for k, v in sorted(markers.items(), key=lambda kv: -kv[1]['pct']))

    excluded = profile.get('excluded_ai_drafted') or 0
    voice_md = VOICE_MD.format(
        name=name,
        source=profile.get('source') or 'mixed sources',
        messages=stats['messages'],
        excluded_note=(', with %d AI-drafted messages removed first' % excluded
                       if excluded else ''),
        oneliner=build_oneliner(stats),
        median=length['median'], p75=length['p75'], p90=length['p90'],
        median_words=stats['words']['median'],
        under80=length['under_80_pct'], under200=length['under_200_pct'],
        over500=length['over_500_pct'],
        marker_rows=marker_rows,
        tail_rows=_tail_rows(vocab['sentence_final_words'], 25),
        opener_rows=_rows(vocab['openers'], 'opener', 'Opening words', 15),
        phrase_rows=_rows(vocab['trigrams'] or vocab['bigrams'], 'gram', 'Phrase', 25),
        short_samples=fmt_samples(profile['samples']['short'], 18),
        medium_samples=fmt_samples(profile['samples']['medium'], 6),
        long_samples=fmt_samples(profile['samples']['long'], 2),
        rules=RULES_PLACEHOLDER,
    )

    prompt_markers = '\n'.join(
        '- %s: %s%% of messages' % (MARKER_LABELS.get(k, k), v['pct'])
        for k, v in sorted(markers.items(), key=lambda kv: -kv[1]['pct'])[:12])
    prompt_txt = PROMPT_TXT.format(
        upper=name.upper(),
        messages=stats['messages'],
        median=length['median'], p75=length['p75'],
        median_words=stats['words']['median'],
        under200=length['under_200_pct'],
        prompt_markers=prompt_markers,
        prompt_tails=', '.join('"%s" (%sx more often than chance)' % (t['word'], t['lift'])
                               for t in vocab['sentence_final_words'][:12]),
        prompt_openers=', '.join('"%s"' % o['opener'] for o in vocab['openers'][:10]),
        prompt_phrases=', '.join('"%s"' % g['gram']
                                 for g in (vocab['trigrams'] or vocab['bigrams'])[:12]),
        prompt_samples='\n'.join('  ' + s['text'].replace('\n', ' / ')
                                 for s in profile['samples']['short'][:12]),
    )

    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.join(args.out_dir, 'voice.md')
    txt_path = os.path.join(args.out_dir, 'voice_prompt.txt')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(voice_md)
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(prompt_txt)
    print('wrote %s' % md_path)
    print('wrote %s' % txt_path)
    print('\nThe numbers are done. The "Rules" section is not: read the samples in '
          'voice.md and write it.')
    return 0


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

# Phrases no measured corpus will ever justify, because they are what an
# assistant reaches for when it has nothing to say.
FILLER = [
    'i wanted to reach out', 'just following up', 'circling back', 'per my last',
    'as discussed', 'please find attached', 'please find below', 'kindly',
    'i hope this finds you well', 'at your earliest convenience', 'moving forward',
    'that said', 'furthermore', 'additionally,', 'in order to ensure',
    'it is worth noting', 'i would be happy to', 'let me know if you have any questions',
    'thank you for your understanding', 'we appreciate your patience',
]
SIGNOFF = re.compile(
    r'(?mi)^\s*(best regards|kind regards|warm regards|regards|sincerely|best,|cheers,)\s*,?\s*$')


def cmd_check(args):
    profile = load_json(args.profile)
    stats = profile['stats']
    length, markers = stats['length'], stats['markers']

    if args.file:
        with open(args.file, encoding='utf-8') as f:
            draft = f.read().strip()
    elif args.text:
        draft = args.text
    else:
        draft = sys.stdin.read().strip()
    if not draft:
        die('nothing to check')

    problems, notes = [], []
    n = len(draft)
    ceiling = args.max_chars or length['p75']
    if n > ceiling:
        problems.append(
            'Length %d characters, over the p75 of %d. Longer than three out of four '
            'messages in the corpus.' % (n, ceiling))
    elif n > length['median'] * 2:
        notes.append('Length %d characters, over twice the median of %d.'
                     % (n, length['median']))

    # A structural habit the corpus almost never shows is a habit that is not theirs.
    for key, pattern, flags in MARKERS:
        if key in ('starts_lowercase', 'all_lowercase', 'multi_paragraph', 'mention',
                   'link', 'question_mark'):
            continue
        rate = markers.get(key, {}).get('pct', 0)
        if rate <= args.rare_threshold and re.search(pattern, draft, flags):
            habit = MARKER_LABELS.get(key, key).lower()
            habit = re.sub(r'^(uses|contains|starts with|runs to) ', '', habit)
            problems.append('Has %s, which appears in %s%% of their messages.'
                            % (habit, rate))

    low = draft.lower()
    for phrase in FILLER:
        if phrase in low:
            problems.append('Assistant filler: "%s".' % phrase)
    if SIGNOFF.search(draft):
        problems.append('Has a sign-off. Messages do not need one.')

    # Habits the corpus shows constantly and the draft dropped entirely.
    if markers['question_mark']['pct'] >= 30 and '?' not in draft and n > 40:
        notes.append('No question mark, but %s%% of their messages carry one.'
                     % markers['question_mark']['pct'])
    if markers['all_lowercase']['pct'] >= 30 and draft[:1].isupper() and n < 90:
        notes.append('Sentence-cased a short message, but %s%% of theirs are entirely '
                     'lowercase.' % markers['all_lowercase']['pct'])

    for line in problems:
        print('FAIL  ' + line)
    for line in notes:
        print('note  ' + line)
    if not problems:
        print('PASS  %d characters against a p75 of %d.' % (n, ceiling))
    return 1 if problems else 0


# --------------------------------------------------------------------------

def changelog_text(mode='list'):
    """The bundled CHANGELOG.md: a list of version headings, or the full text."""
    try:
        with open(CHANGELOG_PATH, encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return ('voiceprint %s. CHANGELOG.md is not bundled with this copy; '
                'read it at %s' % (__version__, CHANGELOG_URL))
    if mode == 'full':
        return text.rstrip('\n')
    heads = [line[3:].strip() for line in text.splitlines() if line.startswith('## [')]
    return '\n'.join(['voiceprint %s' % __version__] + heads +
                     ['', 'Full text: --changelog full'])


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--changelog' in argv:
        i = argv.index('--changelog')
        mode = argv[i + 1] if i + 1 < len(argv) and argv[i + 1] in ('list', 'full') else 'list'
        print(changelog_text(mode))
        return 0

    p = argparse.ArgumentParser(
        prog='voiceprint', description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--version', action='version', version='voiceprint ' + __version__)
    p.add_argument('--changelog', nargs='?', const='list', choices=['list', 'full'],
                   help='print the bundled changelog: version list, or full text')
    sub = p.add_subparsers(dest='cmd', required=True)

    g = sub.add_parser('ingest', help='pull your own sent messages into a corpus')
    g.add_argument('--source', required=True,
                   choices=['slack', 'slack-export', 'whatsapp', 'jsonl', 'text'])
    g.add_argument('--path', help='file or directory, for every source but live slack')
    g.add_argument('--out', default='corpus.json')
    g.add_argument('--token', help='Slack user token, or set SLACK_USER_TOKEN')
    g.add_argument('--me', help='your Slack user id, for --source slack-export')
    g.add_argument('--me-name', help='your name as it appears in the export')
    g.add_argument('--text-field', default='text', help='JSONL field holding the message')
    g.add_argument('--delimiter', default='blank', choices=['blank', 'line'])
    g.add_argument('--max-pages', type=int, default=15, help='Slack search pages, 100 each')
    g.add_argument('--exclude-scan', nargs='+', metavar='DIR',
                   help='directories holding AI-drafted text, to filter those messages out')
    g.add_argument('--probe-words', type=int, default=9,
                   help='words matched when attributing a message')
    g.set_defaults(func=cmd_ingest)

    a = sub.add_parser('analyze', help='measure a corpus into a profile')
    a.add_argument('corpus')
    a.add_argument('--out', default='profile.json')
    a.add_argument('--samples', type=int, default=60, help='messages kept per length band')
    a.add_argument('--min-freq', type=float, default=1.0,
                   help='minimum %% of messages a phrase must appear in')
    a.add_argument('--repeat-cap', type=int, default=3,
                   help='times one identical message may feed the phrase tables')
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser('render', help='write voice.md and voice_prompt.txt')
    r.add_argument('profile')
    r.add_argument('--out-dir', default='.')
    r.add_argument('--name', default='the writer')
    r.set_defaults(func=cmd_render)

    c = sub.add_parser('check', help='hold a draft against the profile')
    c.add_argument('--profile', required=True)
    c.add_argument('--file')
    c.add_argument('--text')
    c.add_argument('--max-chars', type=int, help='override the p75 ceiling')
    c.add_argument('--rare-threshold', type=float, default=2.0,
                   help='a habit at or under this %% counts as banned')
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
