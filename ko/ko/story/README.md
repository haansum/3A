# ko.story: short context stories for KO takes

Code makes every creative choice and every accept/reject decision; a model only writes.
Full instructions: `docs/STORY_HANDOFF.md`.

    python -m ko.story.generate --seed 40 --count 5 [--take takes/beats/x.yaml]   # the whole loop
    python -m ko.story.generate --seed 40 --writer cmd --cmd "claude -p --model claude-opus-5-5"
    python -m ko.story.draw --seed 7            # just a brief
    python -m ko.story.lint brief.yaml story.md [--accept]
    python -m ko.story.choose candidates.yaml --seed 7
    python -m ko.story.measure 100              # sampler repetition, memory off vs on

| File | Role |
| --- | --- |
| `bank/*.yaml` | Settings, situations, people, conflicts, voices, bans |
| `draw.py` | Seeded brief with memory (`ledger.jsonl`) and coherence rules |
| `writer_prompt.md` | System prompt the writing model sees |
| `examples/trash_talk.yaml` | 36 technique examples; counted as used text |
| `choose.py` | Picks a candidate line from the unlikely half |
| `lint.py` | Mechanical rejection and ledger recording |
| `generate.py` | Draw, candidates, pick, write, lint, retry, record |
| `out/` | Briefs, stories and logs |

Prior art in this repo: `src/engine/variety.ts` (commit f1b8d72), a per-bank usage tracker
for narration templates in the Expo app.
