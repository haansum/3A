# ko.story: short context stories for KO takes (PAUSED 2026-11-11)

Paused by the owner mid-build. State and next steps are in the handoff doc
"KO Framework Handoff: Improvements to Date", section "Story generator".

Built: the bank (`bank/*.yaml`), a seeded brief sampler with memory (`draw.py`), and a
mechanical repetition lint (`lint.py`). Not built: the writer prompt, worked example stories,
the trash-talk example set, tests, and a run over many seeds to measure repetition.

    python -m ko.story.draw --seed 7 [--take takes/beats/x.yaml] [--set register=ledger]
    python -m ko.story.lint brief.yaml story.md [--accept]

`out/` holds three drawn briefs (seeds 11-13) that the example stories were going to be
written from. `ledger.jsonl` does not exist until a story is accepted.

Prior art in this repo: `src/engine/variety.ts` (commit f1b8d72), the Expo app's per-bank
usage tracker. Same idea at the phrase-template level; this package works at the
scenario level and keeps a cross-story ledger instead.
