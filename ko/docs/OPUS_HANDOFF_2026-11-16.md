# KO pipeline: handoff for Claude Opus (2026-11-16)

Written in reply to "KO Sim: Organic Motion Design Study". Paste this whole file into a new
Opus session, or commit it as `docs/OPUS_HANDOFF.md` and tell Opus to read it first.

**What the evaluator could and could not check.** I read the study in full. I could not read
the `ko3` code it describes: `tools/`, `ko/sim/intensity.py`, `ko/sim/consciousness.py`, the
Izzy character and the gym arena are not on the remote (`haansum/3a`, branch
`claude/new-session-3jhr9r`). File paths below are taken from the study. Package 0 has Opus
confirm them before anything else.

**Main judgement.** The study's priority order puts organic motion first. I would put it
third. This week's losses were process losses: a 20 mm hover found after about 30 hours of
renders, five sweeps to find uncrossed ankles, re-renders for framing. Until outcomes are
measured before a render, every motion package is judged by eye at a cost of hours per look,
and none of sections A to F can be shown to have helped. So: make the state safe, measure,
gate, make review cheap, and only then change motion.

---

## 1. Decisions for the owner (answer before Opus starts)

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | Freeze new motion features until packages 0 to 4 are done (about 4 sessions)? | **Yes.** They make every later package measurable and cut review cost. |
| 2 | Video policy: allow a real-time Cycles video (9 to 10 h) only for a take that has passed its outcome gates and whose contact sheet you approved? | **Yes.** Add a cheap motion preview tier (package 3) so you can still judge motion before that. |
| 3 | Park the choke framework (study section G) and snoring audio until packages 0 to 7 are done? | **Yes.** G is the largest open-ended redesign in the study, the kind of work Opus loses the thread on. It stays a design, not a plan. |
| 4 | Body model order: soft contact first (F4, without convex decomposition), and let a drop test decide whether volume-derived mass (F2/F3) is worth building? | **Yes.** The 43 BW contact spikes and the failing penetration gate are measured problems. The mass error is a suspicion. |
| 5 | May Opus move overlapping scripts into `tools/_archive/` (moved, never deleted) and keep one script per job? | **Yes.** It respects the archive rule and stops tools growing sideways. |

One more thing to supply once: **your time zone** (IANA name, for example `America/Toronto`),
so Opus stops doing clock arithmetic by hand.

---

## 2. Rules for every session (Opus: read each time)

**Start of session**

1. Read `docs/STATE.md`, `docs/DECISIONS.md` and `tools/INDEX.md`. If any is missing, you are
   in package 0.
2. Do exactly one work package. State its number and its acceptance test before you start.
3. Before writing any new script, search `tools/INDEX.md` for a tool that does the job.
   Extend that tool. A new file in `tools/` needs a line in the index saying why no existing
   tool fits.
4. Measure before and after. A package without numbers from `tools/probe.py` is not done.

**End of session**

1. Run the package's acceptance test and paste its output into `docs/STATE.md`.
2. Update `tools/INDEX.md` and, if a choice was made, add one dated line to
   `docs/DECISIONS.md` (what, why, who decided).
3. Commit and push. The container is temporary; unpushed work is lost work.
4. Show the owner only what the package says to show.

**Times.** Never compute a time by hand. Use
`date -u +%FT%TZ` and `TZ=<owner zone> date '+%a %H:%M %Z'`, and give ETAs as
"about N h from now (HH:MM owner time)".

**Do not**

- Rewrite `control.py`, `run.py` or the bake wholesale. Add behind a flag.
- Bypass, loosen or delete a QA gate to get a take through. If a gate is wrong, change the
  gate in its own commit with a test that shows the old behaviour was wrong.
- Delete any deliverable, render, take or script. Move to `_archive/`.
- Start a Cycles video for a take that has not passed outcome gates and had its sheet approved.
- Render to find out something a probe can compute.
- Leave analysis scripts in the scratchpad. They go in `tools/probe.py` or they do not exist.
- Add a parameter without a default that reproduces current behaviour.
- Break the content floor: always clothed and coverage gate passing; no blood, no injury
  detail; the opponent is only ever a glove or shin prop; no slow motion, no camera shake.
- Present any posture, timing or airway rule as physiology. They are animation choices.

**Rollback rule.** Every package's behaviour sits behind a take or archetype YAML key whose
default is "off / legacy". For each key there is a golden-master test: with the key off, the
three reference takes produce bit-identical `sim.npz` arrays. A package that changes a
golden master without a flag is rejected.

---

## 3. Work packages, in order

Compute figures use the study's numbers: sim 6 to 20 s; 640 px 20-frame sheet about 7 min;
1280x720 Cycles frame about 2.1 min; one Blender process at a time; background jobs killed
at 2 h.

### Package 0. Make the state safe and legible

**Goal.** Everything is in git on the remote, and Opus can find any tool in one file.

**Create / change**
- `docs/STATE.md`: current takes, what each is waiting on, last probe numbers.
- `docs/DECISIONS.md`: owner rules from the study, one line each, dated; the five answers above.
- `tools/INDEX.md`: every script in `tools/`, one row: purpose, inputs, outputs, status
  (`keep`, `merge into X`, `archive`). The study names these overlaps:
  `angle_panels.py` vs `angle_variants.py` / `abc_variants.py`; `comic_sheet.py` vs
  `manga_contact.py`.
- The `ko-sim` skill: replace with the text in section 6.
- Check whether `ko/beats/` exists in the tree (it was built on the remote branch on
  2026-11-10: prose to beat sheet, generic outcome predicates, a checker and a mutation
  self-test). Record yes or no in `STATE.md`. Package 2 depends on the answer.

**Steps.** `git status`; commit in logical pieces; push; write the three docs; do not move
any script yet.

**Acceptance.** `git status --short | wc -l` prints 0; `git log origin/<branch> -1` equals
local HEAD; every file in `tools/` appears in `INDEX.md` (a one-line script comparing `ls`
with the index prints nothing).

**Cost.** No renders. **Show the owner:** `tools/INDEX.md`.

### Package 1. One probe tool and a baseline

**Goal.** Every quantity the owner has asked about is a number that takes seconds to compute.

**Create.** `tools/probe.py` with subcommands, absorbing the scratchpad scripts the study
names (`slide_metric.py`, `cross.py`, `jit.py`, `hover3.py`):

| Subcommand | Reads | Reports |
| --- | --- | --- |
| `outcomes` | `sim.npz` | per beat: heel height, ankle crossing (in her frame), facing at rest, slide distance, head yaw, anything the take's sheet claims |
| `ground` | baked scene | per frame: smallest gap between evaluated skin and the rendered canvas surface, which body part, in mm |
| `load` | `sim.npz` | per segment: peak single-step force and peak 20 ms mean force, in body weights |
| `organic` | `sim.npz` | symmetry index, still fraction, spectral flatness of joint motion after the KO, spread across 10 seeds |
| `framing` | baked scene + camera | subject's share of frame height, whether the beat's target (face, feet) is inside the frame, whether the camera is inside the arena |

**Then.** Run all five on `izzy_hook_chair_001`, `izzy_headkick_cross_002` and
`izzy_uppercut_spring_001`; commit the output as `docs/baseline_2026-11.json`.

**Acceptance.** `python tools/probe.py all takes/<take>.yaml` runs in under 60 s per take
without rendering; `probe ground` on a scene built with the old canvas height of 1.02
reports a gap near 20 mm, and near 0 with 1.000 (this proves the probe would have caught
the hover).

**Cost.** About 3 bakes, no renders. **Show the owner:** the baseline table.

### Package 2. Outcome gates before any render

**Goal.** A take cannot reach a render unless what the owner asked for is true in numbers.

**Change**
- Each take gets an outcome list beside its YAML. If `ko/beats/` exists, use its beat sheet
  format and checker and add predicates only where one is missing. If it does not, add an
  `outcomes:` list to the take with entries such as
  `{at: rest, check: heel_height, min: 0.10, max: 0.20}`,
  `{at: rest, check: ankles_crossed}`, `{at: rest, check: facing, want: down}`.
- QA gains two gates, run after bake and before render: every outcome passes; and
  `probe ground` shows resting contact within 3 mm with no frame deeper than the
  per-segment penetration limit.
- Write the three reference takes' outcomes from the owner's own words in the study.

**Acceptance.** Three deliberate breaks each fail the right gate by name: canvas height set
to 1.02; `sim.exclude_pairs` removed so ankles cannot cross; the face-down take's strike
mirrored. With no breaks, the three takes pass or their failures are listed in `STATE.md`
as real defects.

**Cost.** Sims and bakes only. **Show the owner:** the pass/fail table for the three takes.

### Package 3. One review tool, three cheap tiers, one queue

**Goal.** A review round costs minutes, and renders never wait on a person.

**Change**
- `tools/review.py` with subcommands `strip` (stick figure), `preview` (motion preview
  video), `sheet`, `comic`, `video`. It replaces the scripts marked `merge` in the index;
  those move to `tools/_archive/`.
- Panel times come from the take's beats, with at least 70% on knockdown, descent and
  aftermath (owner rule), not from a hand-typed `--times` list. `--times` stays as an override.
- **Motion preview tier.** First try Blender's Workbench engine on the real mesh at 480 px.
  If the container cannot run it headless, use Cycles at 1 to 2 samples, 320 px, with a
  single clay material override and no denoiser. Measure seconds per frame for both and keep
  the faster. The aim is the full 262-frame motion in under 40 minutes, so motion is judged
  before a 10-hour video is ever started.
- **Queue.** `tools/queue.py`: a directory of job files, one worker, one Blender at a time.
  Review jobs go ahead of video jobs. Video jobs render one frame per invocation in
  bisection order (already resumable), so the worker can stop at 110 minutes and be
  restarted by one command. ETA is computed from the last 10 measured frame times.

**Acceptance.** `review.py sheet` on a reference take matches the panel times the owner
approved last time; the preview tier renders one frame in under 10 s; queueing a sheet while
a video job runs delays the video by one frame at most and needs no manual relaunch; ETA
error under 15% on a 20-frame test.

**Cost.** About 30 minutes of test renders. **Show the owner:** one motion preview clip and
one sheet from the new tool.

### Package 4. Cameras derived from the beat

**Goal.** No more re-renders for framing.

**Change.** In `review.py`, each beat names what must be seen (whole body, face, feet, the
strike). The camera is solved from sim body points for that target, then checked by
`probe framing` before rendering: subject height 65 to 85% of frame for full-body shots
(owner rule is about 75%), target inside the frame for every frame of the beat, camera
position inside the ropes and above the canvas, face camera follows her travel.

**Acceptance.** The three framing bugs from the study each fail `probe framing` when
reproduced (camera 6 m away outside the ropes; chin snap out of frame; face camera assuming
she falls in place) and pass after the solve.

**Cost.** Bakes plus a few 320 px stills. **Show the owner:** A/B/C angle set for one take.

### Package 5. Soft contact (F4 without decomposition)

**Goal.** Landings stop spiking and bouncing; the penetration gate stops failing for the
wrong reason.

**Change.** Behind `sim.soft_contact: true`: flesh segments (pelvis, chest, thighs, upper
arms) get softer canvas contact than bony ones (head, knees, elbows, shins). Start from the
study's figures (time constant about 0.015 to 0.02 s for flesh). **Look up the current
MuJoCo documentation for `solref`, `solimp` and how two geoms' parameters are mixed before
choosing values; do not rely on memory.** Make the penetration gate per segment class.

**Acceptance.** On the three reference takes, from `probe load`: peak single-step canvas
force falls by at least 5 times from the baseline; peak 20 ms mean pelvis force is in single
digits of body weight; resting penetration is 5 to 20 mm on flesh and under 5 mm on bony
segments; outcome gates still pass. Also run 50 seeded zero-tone drops from standing and
record the distribution of final orientation and settle time, before and after.

**Cost.** Sims only, then one sheet. **Show the owner:** before/after sheet of one landing.

**Note.** Soft contact lets rigid geometry sink visibly into the canvas. If the sheet shows
it, the fix is the plane-flattening deformer (E4a), which becomes the next package.

### Package 6. Posture variation that stays coordinated (A2, one rule of A3)

**Goal.** Postures stop looking identical across takes without looking broken.

**Change.** Behind `variety.synergy: true`: three whole-body axes per posture (overall
depth, left/right imbalance, proximal versus distal), sampled per take from the seed. One
causal rule only: the extending arm is on the side the head turned toward. Skip run-time
head coupling (A4) for now; it closes a feedback loop and is hard to keep stable.

**Acceptance.** From `probe organic` over 10 seeds: posture spread at rest is 5 to 15
degrees RMS on the varied joints; symmetry index during holds is above zero and below a
limit the owner sets from a sweep sheet; no joint within 3 degrees of a limit for more than
0.5 s; outcome gates pass on at least 8 of 10 seeds.

**Cost.** 10 sims, one stick sweep sheet. **Show the owner:** a 10-seed stick sheet of the
held posture.

### Package 7. Tremor at torque level (B3 with B2)

**Goal.** Tremor shows where the body is straining and nowhere else.

**Change.** Behind `tremor.mode: torque_noise`: band-limited noise added to joint torque,
scaled by how close the joint is to its torque cap (filtered over about 50 ms, with
hysteresis), normalised by each joint's peak torque. Band 5 to 9 Hz, because the bake is 30
fps and video is 25 fps. Split the jitter gate: it measures everything outside the tremor
band; tremor amplitude is reported separately.

**Acceptance.** Delivered tremor at the joint (degrees RMS in band, from `probe organic`) is
at least 3 times larger on saturated joints than on unsaturated ones in the same take; no
solver warnings; out-of-band jitter is unchanged from baseline within 10%; outcome gates
still pass.

**Cost.** Sims, one motion preview. **Show the owner:** a preview clip of the tonic hold.

### Package 8. Visible breathing, bake only (D1)

**Goal.** Breathing can be seen at full-body distance, and never pushes through the floor.

**Change.** A breathing curve that is not a sine (inhale about 40% of the cycle, a pause
after the exhale, period and depth varying 10 to 20%), driving ribcage, belly and shoulder
shape keys or bones at bake time, masked by contact so a belly on the canvas lifts the back
instead. Record breath phase in `frames.npz`.

**Acceptance.** Chest or belly surface moves at least 6 mm peak to peak at rest when free
and under 1 mm into the canvas when in contact (`probe ground`); breath periods differ by
at least 10% across a take.

**Cost.** One bake, one preview. **Show the owner:** a 6-second preview of her at rest.

### Later, each as its own package when the owner asks

Face expression from state (E1) and the asymmetric impact samples (waiting on the owner's
go-ahead); plane flattening (E4a); jaw (E2); soft-tissue springs (E3); clavicle and second
neck link (F5); volume-derived mass (F2/F3) only if the drop test in package 5 shows final
orientations are wrong; target relaxation refinements; snoring audio, starting with a
10-second listening test before any pipeline work. Section G stays parked.

---

## 4. Answers to the study's questions

1. **Shared state record.** Yes, as a record: the sim writes extra arrays to `sim.npz`, and
   the bake and audio read them. Do not restructure the controller around it. Face and audio
   stay downstream with no path back into the sim.
2. **Torque-level tremor.** The bandwidth argument is right: a critically damped 3 Hz servo
   passes about 12% of an 8 Hz target. Torque noise in a 5 to 9 Hz band is far below the
   2 ms step rate, so it should not destabilise contact; the gate it trips is jitter, which
   package 7 splits. Keep amplitude to a small fraction of peak torque and verify by test.
3. **Target relaxation with phases as drive.** It holds together if tonic postures stay
   absolute named poses that the target blends toward, and relaxation acts only on the
   residual target while no phase is holding. Expressing postures as offsets from a moving
   baseline is what would make them impossible to author.
4. **Mass from mesh or literature.** Unknown until measured. The drop test in package 5
   decides. My expectation is that contact shape and compliance change falls more than a
   20% shift in segment mass does.
5. **Stimulus mapping.** Plain synergy variation gets most of the value. Keep one causal
   rule (arm side follows head turn), because it is the one viewers can read.
6. **Soft contact.** Per-segment contact softness is the cheapest route and the one to try
   first. Flex bodies are too costly and unstable on two CPU cores. Check current MuJoCo
   documentation for parameter meanings before tuning.
7. **Snore synthesis.** Not answerable on paper. A 10-second listening test settles it and
   should be the entire first step.
8. **Organic metrics.** None has been tested against the owner's preference. Report all
   four, gate on none, and log each owner A/B choice next to the numbers so the predictive
   one can be found later.

**Where I disagree with the study**

- It treats ten diagnosis items as one roadmap. Items 8 to 10 (rigid body, mass, no floor
  interaction) are measured through contact spikes and a failing gate and should come before
  more controller work.
- It proposes about 25 mechanisms. Each adds parameters tuned by eye. Build one at a time,
  each behind a flag with a number attached, or tuning time will outrun quality.
- 60 fps rendering is not needed; capping tremor at 9 Hz is cheaper.
- The 2 h job limit and single Blender process are treated as annoyances. They are the
  design constraint: the queue in package 3 is built around them.

---

## 5. Prompt to start each Opus session

```
Read docs/OPUS_HANDOFF.md section 2, then docs/STATE.md, docs/DECISIONS.md and tools/INDEX.md.
Do work package <N> only. Before changing anything, tell me in three lines: the package's
goal, its acceptance test, and which existing files you will change. Extend existing tools;
do not add a script if the index has one for the job. When the acceptance test passes, update
STATE.md, commit, push, and show me only what the package says to show. If something in the
package is wrong or blocked, stop and tell me; do not work around a gate.
```

---

## 6. Replacement text for the `ko-sim` skill

```
name: ko-sim
description: Turn a described knockout into a simulated, checked, reviewed take in the ko
  framework. Use for any KO, fall or collapse animation request in this project.

Framework: the `ko` Python package (stages character -> body -> sim -> qa -> bake -> render,
cached by input hash). Takes are YAML in takes/, built from presets/ (characters, arenas,
archetypes, house.yaml). Not the old Mac scripts (ko_scenario.py, *_hull.xml): ignore those.

Before anything: read docs/STATE.md, docs/DECISIONS.md, tools/INDEX.md.

Order of work for a take, cheapest first. Do not skip a step.
1. Write or update the take YAML and its outcome list (what the owner asked for, as checks).
2. python -m ko.cli build takes/X.yaml --to qa          (seconds)
3. python tools/probe.py all takes/X.yaml               (numbers; fix here, not in a render)
4. python tools/review.py strip takes/X.yaml            (stick figure)
5. python tools/review.py preview takes/X.yaml          (motion preview, minutes)
6. python tools/review.py sheet takes/X.yaml            (owner reviews this)
7. Only after the owner approves the sheet: queue a video with tools/queue.py.

Rules: QA gates are never bypassed. Nothing is deleted; archive instead. Left and right are
hers. Say what is measured and what is tuned by eye. Always clothed, coverage gate passing;
no blood or injury detail; the opponent is only a glove or shin prop; no slow motion or
camera shake. Mouth closed at contact, then forced partly open and shifted. About 30% of the
pupil showing. The mouthguard stays in through the KO and is knocked out by the follow-up
over a fraction of a second. Momentum carries through the shutdown. A limp body loads,
rebounds once softly, then lets go. Tremor comes from effort.

New behaviour goes behind a YAML key that defaults to the old behaviour, with a golden-master
test. One tool per job: extend, do not add.
```

Opus should correct any command in this text that does not match the tree during package 0.
