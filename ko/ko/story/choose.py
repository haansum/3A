"""Candidate-then-choose for the lines that matter (the hardest line of trash talk, the last
sentence). The writer proposes several candidates WITH its own estimate of how likely it
would have been to write each one; code then keeps one from the unlikely half. This is the
'verbalized sampling' idea: a model asked for one line gives its most typical line, a model
asked for a spread with probabilities exposes its less typical ones.

    candidates.yaml:
      - {p: 0.45, text: "..."}
      - {p: 0.25, text: "..."}
      - {p: 0.15, text: "..."}
      - {p: 0.10, text: "..."}
      - {p: 0.05, text: "..."}

    python -m ko.story.choose candidates.yaml --seed 13 [--brief brief.yaml]

Rules: at least 4 candidates; the most probable one is never chosen; candidates that contain
a banned phrase or echo past stories are dropped first; the pick is seeded, not the model's.
"""
import argparse
import re

import numpy as np
import yaml

from .draw import bank, ledger
from .lint import STOP, example_trigrams, trigrams


def choose(cands, seed, brief=None, past=None):
    past = ledger() if past is None else past
    B = bank()['bans']
    seen = set(example_trigrams())
    for q in past:
        seen |= set(q.get('trigrams', []))
    bans = list(B['always']) + list(B['boundary']) + list((brief or {}).get('banned_here', []))
    if len(cands) < 4:
        raise SystemExit('need at least 4 candidates')
    ok = []
    for c in cands:
        low = c['text'].lower()
        if any(re.search(r'\b' + re.escape(b), low) for b in bans):
            continue
        tri = {t for t in trigrams(c['text']) if not set(t.split()) <= STOP}
        if tri and len(tri & seen) / len(tri) > 0.15:
            continue
        ok.append(c)
    ok.sort(key=lambda c: -float(c['p']))
    top = max(cands, key=lambda c: float(c['p']))
    tail = [c for c in ok if c is not top][max(0, (len(ok) - 1) // 2 - 1):] or [c for c in ok if c is not top]
    if not tail:
        raise SystemExit('every candidate was banned, an echo, or the most likely one: ask for a new set')
    return tail[int(np.random.default_rng(seed).integers(len(tail)))]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('candidates')
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--brief')
    a = ap.parse_args(argv)
    pick = choose(yaml.safe_load(open(a.candidates)), a.seed, yaml.safe_load(open(a.brief)) if a.brief else None)
    print(pick['text'])


if __name__ == '__main__':
    main()
