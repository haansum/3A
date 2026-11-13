"""Generate stories end to end: brief -> candidate lines -> pick -> write -> lint -> retry -> record.

    python -m ko.story.generate --seed 40 --count 5                    # Claude API (needs credentials)
    python -m ko.story.generate --seed 40 --take takes/beats/x.yaml    # tie to a take
    python -m ko.story.generate --seed 40 --writer cmd --cmd "claude -p --model claude-opus-5-5"

One story at a time, in seed order: each accepted story changes what the next brief may use.
Code makes every creative choice (draw.py) and every accept/reject decision (lint.py, choose.py);
the model only writes. Output: ko/story/out/s<seed>.brief.yaml, .md and .log.json.

Writers:
  api  the Anthropic SDK. Model defaults to claude-opus-5-5; --model overrides.
  cmd  any shell command that reads a prompt on stdin and prints the reply (a local CLI,
       another vendor's tool). Same loop, same checks.
"""
import argparse
import json
import os
import re
import subprocess
import sys

import numpy as np
import yaml

from . import choose as chooser
from . import draw, lint

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, 'out')
MODEL = 'claude-opus-5-5'


def system_prompt(shape='leadup'):
    return open(os.path.join(HERE, 'writer_prompt_aftermath.md' if shape == 'aftermath' else 'writer_prompt.md')).read()


def technique_examples(brief, seed, n=4):
    """A few trash-talk examples from registers this story does NOT use, so they teach the
    idea of a register without offering lines that fit. Rotated by seed."""
    d = yaml.safe_load(open(os.path.join(HERE, 'examples', 'trash_talk.yaml')))
    used = {brief['axes']['register'], brief['axes']['counter_register']}
    after = brief.get('shape') == 'aftermath'
    regs = [r for r in d if r not in used and (not after or any(e.get('tone') == brief.get('tone') and e.get('when') == 'after' for e in d[r]))]
    n = 6 if after else n
    rng = np.random.default_rng(seed)
    out = []
    for r in rng.choice(regs, n, replace=False):
        pool = [e for e in d[str(r)] if (e.get('when') == 'after') == after and e.get('tone', 'measured') == brief.get('tone', 'measured')] \
            or [e for e in d[str(r)] if (e.get('when') == 'after') == after] or d[str(r)]
        e = pool[int(rng.integers(len(pool)))]
        out.append(f'- {r} (context: {e["ctx"]}): {e["line"]}')
    return '\n'.join(out)


def brief_text(brief):
    keep = {k: v for k, v in brief.items() if k not in ('axes', 'names', 'seed', 'id', 'sim_prose', 'shape')}
    if 'finish' in keep:                    # the writer needs the fact and the image, not the lever ids
        keep = dict(keep, finish=dict(keep['finish'], facts_in_order=[{k: v for k, v in f.items() if k != 'lever'} for f in keep['finish']['facts_in_order']]))
    return yaml.safe_dump(keep, sort_keys=False, width=110, allow_unicode=True)


CAND_ASK = '''BRIEF
{brief}
Examples of other registers, for technique only. Do not reuse a line, a sentence shape or an object from them:
{examples}

Step 1 of 2. Do not write the story yet.
First decide three specifics: the ring name or nickname in play; the one checkable detail of the grievance; one thing each fighter does with her hands.
Then write {n} candidates for the hardest line of the scene: the worst thing the talker says (or, if the talker's register is silence or whisper, the one line she does say). Make them genuinely different from each other in what they attack and how they are built. For each, give p: your honest estimate of the probability that you would have written that line if asked for only one. The p values sum to 1.

Return only JSON: {{"nickname": str, "detail": str, "hands": str, "candidates": [{{"p": number, "text": str}}, ...]}}'''

WRITE_ASK = '''BRIEF
{brief}
Specifics already decided:
- nickname: {nickname}
- grievance detail: {detail}
- hands: {hands}

The hardest line has been chosen for you. Use it exactly as written, once, spoken or reported as the form requires:
{line}

Step 2 of 2. Write the story now. Return only the story text.'''

FIX_ASK = '''The story was checked mechanically and rejected:
{fails}

Rewrite the whole story so every check passes. Keep the brief, the specifics and the chosen line. Return only the story text.'''


CAND_ASK_AFTER = '''BRIEF
{brief}
Examples of other registers, for technique only. Do not reuse a line, a sentence shape or an object from them:
{examples}

Step 1 of 2. Do not write the piece yet.
First decide three specifics: the nickname or ring name in play; the one checkable detail of the grievance (a number, object, date or place); the exact round and time of the finish.
Then write candidates for the three lines the speaker says afterward, {n} for each slot:
- opener: the first thing said. Small, almost offhand.
- personal: the grievance named exactly and tied to what just happened on the canvas.
- closer: what she leaves the room with.
Within a slot make the candidates genuinely different in what they attack and how they are built. For each give p: your honest estimate of the probability that you would have written that line if asked for only one. Within each slot the p values sum to 1.

Return only JSON: {{"nickname": str, "detail": str, "round_time": str, "opener": [{{"p": number, "text": str}}, ...], "personal": [...], "closer": [...]}}'''

WRITE_ASK_AFTER = '''BRIEF
{brief}
Specifics already decided:
- nickname: {nickname}
- grievance detail: {detail}
- round and time: {round_time}

The three lines have been chosen for you. Use each exactly as written, once, in the third part, in this order:
- opener: {opener}
- personal: {personal}
- closer: {closer}

Step 2 of 2. Write the piece now: lead-up, a line with only *, the finish, a line with only *, the aftermath and talk. Return only the text.'''

# ---- writers -----------------------------------------------------------------------------
class ApiWriter:
    """Anthropic SDK. The system prompt is stable, so it is cached across stories."""

    def __init__(self, model=MODEL, effort='medium'):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.model, self.effort, self.shape = model, effort, 'leadup'
        self.usage = {'input': 0, 'output': 0, 'cache_read': 0}

    def _call(self, messages, max_tokens, schema=None):
        a = self.anthropic
        kw = dict(model=self.model, max_tokens=max_tokens, messages=messages,
                  system=[{'type': 'text', 'text': system_prompt(self.shape), 'cache_control': {'type': 'ephemeral'}}],
                  output_config={'effort': self.effort},
                  betas=['server-side-fallback-2026-07-01'], fallbacks='default')
        try:
            if schema is not None:
                r = self.client.beta.messages.parse(output_format=schema, **kw)
            else:
                with self.client.beta.messages.stream(**kw) as s:
                    r = s.get_final_message()
        except a.RateLimitError as e:
            raise SystemExit(f'rate limited after retries: {e.message}')
        except a.APIStatusError as e:
            raise SystemExit(f'API error {e.status_code}: {e.message}')
        except a.APIConnectionError as e:
            raise SystemExit(f'network error: {e}')
        u = r.usage
        self.usage['input'] += u.input_tokens
        self.usage['output'] += u.output_tokens
        self.usage['cache_read'] += getattr(u, 'cache_read_input_tokens', 0) or 0
        if r.stop_reason == 'refusal':
            return None
        if schema is not None:
            return r.parsed_output.model_dump()
        return ''.join(b.text for b in r.content if b.type == 'text').strip()

    def candidates(self, user):
        from pydantic import BaseModel

        class Cand(BaseModel):
            p: float
            text: str

        class Plan(BaseModel):
            nickname: str
            detail: str
            hands: str
            candidates: list[Cand]

        class PlanAfter(BaseModel):
            nickname: str
            detail: str
            round_time: str
            opener: list[Cand]
            personal: list[Cand]
            closer: list[Cand]
        return self._call([{'role': 'user', 'content': user}], 6000, PlanAfter if self.shape == 'aftermath' else Plan)

    def write(self, turns):
        return self._call(turns, 4000)


class CmdWriter:
    """Any command that reads a prompt on stdin and prints a reply."""

    def __init__(self, cmd, timeout=300):
        self.cmd, self.timeout, self.shape = cmd, timeout, 'leadup'
        self.usage = {}

    def _run(self, turns):
        prompt = system_prompt(self.shape) + '\n\n' + '\n\n'.join(
            ('' if t['role'] == 'user' else 'YOUR PREVIOUS ANSWER:\n') + t['content'] for t in turns)
        r = subprocess.run(self.cmd, shell=True, input=prompt, capture_output=True, text=True, timeout=self.timeout)
        if r.returncode != 0:
            raise SystemExit(f'writer command failed: {r.stderr.strip()[:400]}')
        return r.stdout.strip()

    def candidates(self, user):
        out = self._run([{'role': 'user', 'content': user}])
        m = re.search(r'\{.*\}', out, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except json.JSONDecodeError:
            return None

    def write(self, turns):
        out = self._run(turns)
        return re.sub(r'^```\w*\n|\n```$', '', out).strip()


# ---- the loop ------------------------------------------------------------------------------
def _norm(t):
    return re.sub(r'\s+', ' ', t.lower().replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'").replace('\u2018', "'")).strip()


def one(seed, writer, take=None, sets=None, max_attempts=3, n_cand=5, accept=True, log=print, shape='aftermath'):
    os.makedirs(OUT, exist_ok=True)
    after = shape == 'aftermath'
    writer.shape = shape
    brief = (draw.draw_aftermath if after else draw.draw)(seed, sets, take)
    sid = brief['id']
    yaml.safe_dump(brief, open(os.path.join(OUT, sid + '.brief.yaml'), 'w'), sort_keys=False, width=110, allow_unicode=True)
    rec = {'id': sid, 'seed': seed, 'shape': shape, 'attempts': []}
    bt = brief_text(brief)
    slots = ('opener', 'personal', 'closer') if after else ('candidates',)
    plan, lines = None, {}
    for _ in range(2):                      # candidates: one retry if malformed or all rejected
        plan = writer.candidates((CAND_ASK_AFTER if after else CAND_ASK).format(
            brief=bt, examples=technique_examples(brief, seed), n=4 if after else n_cand))
        if plan and all(len(plan.get(k) or []) >= 4 for k in slots):
            try:
                lines = {k: chooser.choose(plan[k], seed + i, brief) for i, k in enumerate(slots)}
                break
            except SystemExit as e:
                rec.setdefault('candidate_rejects', []).append(str(e))
        plan = None
    if plan is None:
        rec['status'] = 'no usable candidates (refused, malformed or all rejected)'
        json.dump(rec, open(os.path.join(OUT, sid + '.log.json'), 'w'), indent=1)
        log(f'{sid}: FAILED at candidates')
        return rec
    rec.update({'plan': plan, 'chosen': {k: {'text': v['text'], 'p': v['p']} for k, v in lines.items()}})
    if after:
        ask = WRITE_ASK_AFTER.format(brief=bt, **{k: plan[k] for k in ('nickname', 'detail', 'round_time')}, **{k: v['text'] for k, v in lines.items()})
    else:
        ask = WRITE_ASK.format(brief=bt, line=lines['candidates']['text'], **{k: plan[k] for k in ('nickname', 'detail', 'hands')})
    turns = [{'role': 'user', 'content': ask}]
    story, ok = None, False
    for k in range(max_attempts):
        story = writer.write(turns)
        if not story:
            rec['attempts'].append({'n': k + 1, 'fails': ['refused or empty']})
            break
        res = lint.check(brief, story)
        fails = [f"{r['check']}: {r['detail']}" for r in res if not r['pass']]
        body = _norm(story)
        for name, ln in lines.items():
            if _norm(ln['text']).strip('"')[:40] not in body:
                fails.append(f'chosen_line ({name}): missing or altered; use it exactly: {ln["text"]}')
        rec['attempts'].append({'n': k + 1, 'words': len(story.split()), 'fails': fails})
        if not fails:
            ok = True
            break
        turns += [{'role': 'assistant', 'content': story}, {'role': 'user', 'content': FIX_ASK.format(fails='\n'.join('- ' + f for f in fails))}]
    rec['status'] = 'accepted' if ok else 'rejected after %d attempts' % len(rec['attempts'])
    rec['usage'] = dict(writer.usage)
    path = os.path.join(OUT, sid + ('.md' if ok else '.rejected.md'))
    if story:
        open(path, 'w').write(story + '\n')
    if ok and accept:
        with open(draw.LEDGER, 'a') as f:
            f.write(json.dumps({'id': sid, 'axes': brief['axes'], 'names': brief['names'], **lint.stats(story)}) + '\n')
    json.dump(rec, open(os.path.join(OUT, sid + '.log.json'), 'w'), indent=1)
    log(f"{sid}: {rec['status']} ({len(rec['attempts'])} attempt(s)); line p={[v['p'] for v in lines.values()]}; {path}")
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--count', type=int, default=1, help='stories to make, seeds seed..seed+count-1, in order')
    ap.add_argument('--take', help='beat sheet to tie the ending to')
    ap.add_argument('--set', action='append', default=[], help='fix an axis, e.g. register=ledger')
    ap.add_argument('--writer', choices=['api', 'cmd'], default='api')
    ap.add_argument('--cmd', default='claude -p --model ' + MODEL)
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--max-attempts', type=int, default=3)
    ap.add_argument('--shape', choices=['aftermath', 'leadup'], default='aftermath',
                    help='aftermath: brief lead-up, the finish, then the talk (default). leadup: the scene before the fight')
    ap.add_argument('--dry', action='store_true', help='do not record accepted stories in the ledger')
    a = ap.parse_args(argv)
    used = {q['id'] for q in draw.ledger()}
    w = ApiWriter(a.model, a.effort) if a.writer == 'api' else CmdWriter(a.cmd)
    done = []
    for s in range(a.seed, a.seed + a.count):
        if f's{s:05d}' in used:
            print(f's{s:05d}: seed already used, skipped')
            continue
        done.append(one(s, w, a.take, dict(x.split('=', 1) for x in a.set), a.max_attempts, accept=not a.dry, shape=a.shape))
    n = sum(r['status'] == 'accepted' for r in done)
    print(f'{n} of {len(done)} accepted' + (f"; tokens {w.usage}" if w.usage else ''))
    return 0 if n == len(done) else 2


if __name__ == '__main__':
    raise SystemExit(main())
