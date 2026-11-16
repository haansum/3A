# KO pipeline: handoff for Claude Opus (2026-11-16, revision 2)

Written in reply to "KO Sim: Organic Motion Design Study", then revised after the owner
answered the open questions. Paste this whole file into a new Opus session, or commit it as
`docs/OPUS_HANDOFF.md` and tell Opus to read it first.

**The goal.** Final realism: a knockout that sells, at full-body distance and in face
close-up. Process work exists only to serve that. It comes first for three sessions because
no realism change can be measured, or reviewed cheaply, without it; after that, realism and
process alternate.

**What the evaluator checked (updated after receiving `ko3_code_2026-11-16.zip`).** I read
the study and the code archive (157 files, source only). Verified facts:

- `ko3` forked from the remote branch at commit `63c537f` (2026-11-11). Twelve files were
  changed on the Opus side (`bake.py`, `gen_body.py`, `import_rig.py`, `outfit.py`, `cli.py`,
  `manifest.py`, `gates.py`, `render.py`, `control.py`, `reference.py`, `run.py`, `scene.py`)
  plus new ones (`intensity.py`, `consciousness.py`, `fx.py`, `props.py`, 33 scripts in
  `tools/`, `eval/golden_sim.py`). The remote changed 45 other files since the fork (story
  generator, `08_ko_effects.yaml`, docs). **No file was changed on both sides**, so the merge
  is clean.
- `ko/beats/` (predicates, checker, self-test) **is in the tree and is used by one take
  only**, the original Freya test. Every newer archetype has its own hand-written outcome
  block in `gates.py` (eleven outcome names). Package P2 is therefore wiring, not building.
- Nothing in `ko/` or `tools/` compares rendered skin with the rendered canvas.
- `presets/arenas/gym.yaml` sets canvas contact very stiff (`canvas_solref: '0.003 1'`), with
  a note that the owner asked to watch for clipping. That stiffness is a likely source of the
  43 body-weight spikes. Package R1 must solve clipping another way (the flattening deformer
  in R7) rather than by stiffening contact; raise this with the owner when R1 starts.
- `tests/` has no test file for `intensity.py` or `consciousness.py`.
- The archive is not a git repository and holds no assets, builds or renders.

Not seen: character and arena assets, the 13 impact-face references, any `sim.npz`, bake or
render, the scratchpad probe scripts, the render chain script, and how Blender is installed
in the Opus container.

---

## 1. Decisions the owner has made

| Topic | Decision |
| --- | --- |
| What matters | Final realism and selling the knockout. Both distances equally: full body and face close-up. |
| Where it looks least real | The fall and landing; face and head; secondary life (breathing, soft tissue, hair, hands, toes, shoulders). Posture on the canvas was not picked, so posture variety and tremor rework come later. |
| Sequencing | Process packages P0, P1, P2 first. Then alternate one realism package with one process package. |
| The earlier five recommendations | Accepted: gates before video, soft contact before mass work, tool archiving allowed. The choke framework is no longer parked (see track G). Audio stays later. |
| Reference footage | Build a framework that receives video clips. The owner will paste a folder later. Extract timings plus pose tracks. Clips stay local and gitignored; only extracted numbers are committed. |
| Compute | Stay on CPU for now and get the most out of the current container. A GPU (cloud or the owner's machine) comes later; do not plan around it. |
| Time zone | UTC-6. Use `TZ=Etc/GMT+6` (POSIX signs are inverted). If the owner observes daylight saving, switch to the named zone they give. |
| First choke | Rear-naked choke, both seated on the canvas. |
| Attacker | Only his arms are rendered. A torso may be simulated as an unseen anchor. |
| Choke arc | Conscious defence, fading, going out, involuntary movement while out (tremor and spasms), release, slump. The take ends when her posture is steady. No waking or recovery in the first version (my reading of "stops once the posture is steady-state"; confirm). |
| Movement while out | Build all three levels as presets: quiet, mild, pronounced. Default is pronounced: exaggerated, but keeping the pattern of the real thing. |

**Still open for the owner**

1. Confirm the choke arc ends before waking.
2. Arms-only rendering means two arms with nothing behind them. Framing will have to crop at
   his shoulders in every shot. Acceptable, or add a torso later?
3. The asymmetric impact-face samples were waiting on a go-ahead. Face and head was picked as
   a top gap, so package R3 treats that as a go. Say so if not.

---

## 2. What should sell the knockout, in order

My ranking of expected visible gain per session. None of it is measured yet; package P1
gives the numbers that will confirm or reorder it.

| Rank | Change | Why it should matter | Package |
| --- | --- | --- | --- |
| 1 | Soft landing and limbs that settle | A body that booms, bounces once and then keeps sliding and sagging reads as a person. The current 43 body-weight contact spikes read as a mannequin. | R1, R2 |
| 2 | Asymmetric impact face and a jaw that hangs | The face is where a viewer looks first in a close-up, and it is frozen today. | R3, R5 |
| 3 | A neck that whips instead of hinging | One neck link makes every head snap look mechanical. | R5 |
| 4 | Lighting that shows the body's shape | Flat arena light hides contact and form; a stronger key and visible contact shadows make the same motion look more real at no sim cost. | R4 |
| 5 | Visible breathing | The clearest sign that she is out, not dead, and currently invisible at render distance. | R6 |
| 6 | Soft tissue and a cheek that flattens on the canvas | Removes the rigid look at impacts and the clipping when she lands face down. | R7 |
| 7 | Hands, toes and shoulders | Small involuntary details: fingers, toes, a held shrug. | R8 |
| 8 | Calibration against footage | Replaces tuned-by-eye timings with measured ranges. | P5 |
| 9 | Posture variety and effort-driven tremor | Real gains, but the owner did not pick posture as a top gap. | R9, R10 |

---

## 3. Rules for every session (Opus: read each time)

**Start of session**

1. Read `docs/STATE.md`, `docs/DECISIONS.md` and `tools/INDEX.md`. If any is missing, you are
   in package P0.
2. Do exactly one work package. State its name and its acceptance test before you start.
3. Before writing any new script, search `tools/INDEX.md` for a tool that does the job.
   Extend that tool. A new file in `tools/` needs a line in the index saying why none fits.
4. Measure before and after. A package without numbers from `tools/probe.py` is not done.

**End of session**

1. Run the acceptance test and paste its output into `docs/STATE.md`.
2. Update `tools/INDEX.md` and add one dated line to `docs/DECISIONS.md` for any choice made.
3. Commit and push. The container is temporary; unpushed work is lost work.
4. Show the owner only what the package says to show.

**Times.** Never compute a time by hand. Use `date -u +%FT%TZ` and
`TZ=Etc/GMT+6 date '+%a %H:%M'`, and give ETAs as "about N h from now (HH:MM your time)".

**Do not**

- Rewrite `control.py`, `run.py` or the bake wholesale. Add behind a flag.
- Bypass, loosen or delete a QA gate to get a take through. If a gate is wrong, change it in
  its own commit with a test showing the old behaviour was wrong.
- Delete any deliverable, render, take or script. Move to `_archive/`.
- Start a full-quality Cycles video for a take that has not passed its outcome gates and had
  its sheet approved.
- Render to find out something a probe can compute.
- Leave analysis scripts in the scratchpad. They go in `tools/probe.py`.
- Add a parameter without a default that reproduces current behaviour.
- Break the content floor: always clothed and coverage gate passing; no blood, no injury
  detail, no lasting harm shown; the opponent is only a glove, a shin, or (choke) two arms;
  no slow motion, no camera shake.
- Present any posture, timing, airway or choke rule as physiology. They are animation
  choices. Never calibrate anything to real force thresholds for hurting a person.
- Commit reference footage. Clips are gitignored; only numbers go in git.

**Rollback rule.** Every package's behaviour sits behind a take or archetype YAML key whose
default is the old behaviour. For each key there is a golden-master test: with the key off,
the three reference takes produce bit-identical `sim.npz` arrays.

---

## 4. Order of sessions

| # | Package | Track |
| --- | --- | --- |
| 1 | P0 Make the state safe and legible | process |
| 2 | P1 One probe tool and a baseline | process |
| 3 | P2 Outcome gates before any render | process |
| 4 | R1 Soft landing | realism |
| 5 | P3 One review tool, a cheap motion preview, one queue | process |
| 6 | R2 Limbs that settle | realism |
| 7 | P4 Faster frames on two cores | process |
| 8 | R3 Impact face | realism |
| 9 | P5 Video reference intake | process |
| 10 | R4 Lighting that shows form | realism |
| 11 | P6 Cameras from the beat | process |
| 12 | R5 Neck and jaw | realism |
| 13 | G1 One consciousness input | choke |
| 14 | R6 Visible breathing | realism |
| 15 | G2 Two-body scaffold | choke |
| 16 | R7 Soft tissue and canvas flattening | realism |
| 17 | G3 Fade and going out | choke |
| 18 | R8 Hands, toes, shoulders | realism |
| 19 | G4 Movement while out, release, settle | choke |
| 20 | G5 Arms on screen | choke |
| later | R9 posture variety, R10 torque-level tremor, mass from mesh (only if R2's drop test says so), audio | |

The owner may reorder realism and choke packages freely. P0 to P2 stay first.

---

## 5. Process packages

Compute figures use the study's numbers: sim 6 to 20 s; 640 px 20-frame sheet about 7 min;
1280x720 Cycles frame about 2.1 min at 24 samples; one Blender at a time; background jobs
killed at 2 h.

### P0. Make the state safe and legible

**Goal.** Everything is on the remote, and Opus can find any tool in one file.

**Create / change**
- `docs/STATE.md`: current takes, what each waits on, last probe numbers.
- `docs/DECISIONS.md`: section 1 of this file plus the owner rules from the study, one dated
  line each.
- `tools/INDEX.md`: every script in `tools/`, one row: purpose, inputs, outputs, status
  (`keep`, `merge into X`, `archive`). Known overlaps: `angle_panels.py` vs
  `angle_variants.py` / `abc_variants.py`; `comic_sheet.py` vs `manga_contact.py`.
- The `ko-sim` skill: replace with the text in section 9.
- Merge with the remote branch `claude/new-session-3jhr9r`: commit the Opus tree, then merge
  (no file was changed on both sides). This brings in `08_ko_effects.yaml`, the story
  generator and this handoff. Run the full test suite after the merge.
- Copy the scratchpad probe scripts (`slide_metric.py`, `cross.py`, `jit.py`, `hover3.py`)
  and the render chain script into `tools/` before they are lost; P1 folds them into one tool.

**Acceptance.** `git status --short | wc -l` prints 0; local HEAD equals the remote branch
head; every file in `tools/` appears in `INDEX.md`.

**Cost.** No renders. **Show the owner:** `tools/INDEX.md`.

### P1. One probe tool and a baseline

**Goal.** Everything the owner has asked about is a number that takes seconds to get.

**Create.** `tools/probe.py`, absorbing the scratchpad scripts (`slide_metric.py`,
`cross.py`, `jit.py`, `hover3.py`):

| Subcommand | Reads | Reports |
| --- | --- | --- |
| `outcomes` | `sim.npz` | per beat: heel height, ankle crossing in her frame, facing at rest, slide distance, head yaw, anything the take claims |
| `ground` | baked scene | per frame: smallest gap between evaluated skin and the rendered canvas, which part, in mm |
| `load` | `sim.npz` | per segment: peak single-step force and peak 20 ms mean force, in body weights; number of bounces |
| `settle` | `sim.npz` | time from first canvas contact to stillness; how far each limb moves after the trunk stops |
| `organic` | `sim.npz` | symmetry index, still fraction, spectral flatness after the KO, spread across 10 seeds |
| `framing` | baked scene + camera | subject's share of frame height, target in frame, camera inside the arena |
| `look` | a rendered still | share of clipped pixels on skin, key-to-fill ratio, contrast across the body |
| `render` | scene + settings | seconds per frame, and similarity to a high-sample reference frame |

**Then.** Run on `izzy_hook_chair_001`, `izzy_headkick_cross_002`,
`izzy_uppercut_spring_001`; commit `docs/baseline_2026-11.json`.

**Acceptance.** `probe.py all` runs in under 60 s per take without rendering (`look` and
`render` excluded); `probe ground` reports about 20 mm on a scene built with canvas height
1.02 and about 0 with 1.000.

**Cost.** About 3 bakes. **Show the owner:** the baseline table.

### P2. Outcome gates before any render

**Goal.** A take cannot reach a render unless what the owner asked for is true in numbers.

**Change**
- Each take gets an outcome list. Use the `ko/beats` sheet format and checker, which are
  already in the tree; add a predicate only where one is missing. Move the eleven
  hand-written outcome blocks in `gates.py` to beat sheets one archetype at a time, keeping
  each old block until its sheet reproduces the same pass/fail on the reference take.
- QA gains two gates after bake and before render: every outcome passes; `probe ground`
  shows resting contact within 3 mm and no frame beyond the per-segment penetration limit.
- Write the three reference takes' outcomes from the owner's words in the study.

**Acceptance.** Three deliberate breaks each fail the right gate by name: canvas height
1.02; `sim.exclude_pairs` removed so ankles cannot cross; the face-down take's strike
mirrored. Unbroken, the takes pass or their failures are listed in `STATE.md` as defects.

**Cost.** Sims and bakes. **Show the owner:** the pass/fail table.

### P3. One review tool, a cheap motion preview, one queue

**Goal.** A review round costs minutes, and motion is judged before a long render starts.

**Change**
- `tools/review.py` with subcommands `strip`, `preview`, `sheet`, `comic`, `video`. Scripts
  marked `merge` move to `tools/_archive/`.
- Panel times come from the take's beats, at least 70% on knockdown, descent and aftermath.
  `--times` stays as an override.
- **Motion preview = low-sample Cycles.** Measured on 2026-11-16 in a container of this
  kind: Workbench and Eevee cannot run (no `libEGL`, and it could not be installed); Cycles
  at 1 sample, 480 px, rendered a baked take in about 1.5 s per frame. Use 1 to 4 samples,
  480 px, no denoiser, full frame rate, real mesh and real cameras. That figure was on a
  simpler scene than the gym; measure Izzy's.
- **Queue.** `tools/queue.py`: a directory of job files, one worker, one Blender. Review
  jobs go ahead of video jobs. Video jobs render frame by frame in bisection order, so the
  worker can stop at 110 minutes and be restarted by one command. ETA from the last 10
  measured frame times, printed in the owner's time.

**Acceptance.** One preview frame of an Izzy gym take in under 10 s; a 262-frame preview
clip in under 45 min; queueing a sheet while a video runs delays the video by at most one
frame with no manual relaunch; ETA error under 15% on a 20-frame test.

**Cost.** About 45 minutes of renders. **Show the owner:** one motion preview clip.

### P4. Faster frames on two cores

**Goal.** More quality per hour from the same container, proven by measurement.

**Method.** Use `probe render`: for each candidate setting, time one frame at three moments
of a take (strike, landing, rest) and compare it with a 256-sample reference of the same
frame. Keep a setting only if it is faster and the image stays close. Try, in this order:

1. **Static plate.** Most shots use a fixed camera. Render the empty arena once per camera
   at high samples. Render the character each frame with the arena as shadow catcher and
   holdout, cropped to her projected bounding box plus margin (border render). Composite
   outside Blender with numpy or ffmpeg, since Blender's compositor needs `libEGL`.
2. **Fewer samples with a denoiser.** 8 to 12 samples with OpenImageDenoise against 24
   without. Check faces and hair, where denoisers smear.
3. **Shorter light paths.** Total bounces 3 to 4, no caustics, clamp indirect light.
4. **Lighter scene.** Texture size limit, subdivision cap, hair as cards if it is strands.
5. **Persistent data** across frames if it is not already on.

Do not use frame interpolation (it invents motion) and do not lower the frame rate of finals.

**Acceptance.** Per-frame time at 1280x720 falls by at least 2.5 times against the current
24-sample frame, with image similarity to the 256-sample reference no worse than the current
24-sample frame's on all three test frames. Results table committed. If the plate method
alone gives this, spend the saving on samples or on motion blur for strike frames and say
which.

**Cost.** About 1.5 h of test frames. **Show the owner:** three before/after frame pairs.

### P5. Video reference intake

**Goal.** When the owner pastes a folder of clips, the pipeline turns them into numeric
targets without anyone tuning by eye.

**Create**
- `refs/clips/` (gitignored), `refs/annotations/<clip>.yaml`, `refs/tracks/<clip>.npz`,
  `docs/reference_targets.json`.
- `tools/ref.py` with subcommands:
  - `ingest`: probe each clip (frame rate, length, cuts), write a blank annotation file.
  - `track`: 2D body pose per frame on CPU. Try a pretrained pose estimator that installs in
    the container; check it runs before building on it. If none does, the package still
    ships with annotation only.
  - `annotate`: a contact-sheet with frame numbers so the owner or Opus can fill in event
    frames (strike, first canvas contact, head contact, stillness, follow-up) and tag
    effects using lever ids from the catalog, including the `ko_effects` family (arm stays
    up, snoring, toes, wrong corner).
  - `measure`: from tracks and annotations: strike to canvas time, canvas to stillness time,
    bounce count, image-plane joint-angle curves for the limbs facing the camera, how long a
    raised arm stays up, tremor frequency where the clip's frame rate allows.
  - `targets`: pool all clips into medians and ranges per fall type; `probe` then reports
    each take's numbers beside the reference range.
- A clip's annotation records what cannot be trusted: camera moving, limb hidden, cut mid-fall.

**Limits to state in the output.** 2D only; broadcast frame rates cap what tremor can be
measured; moving cameras corrupt angles; a handful of clips is anecdote, not a distribution.

**Acceptance.** Self-test on our own render, where the truth is known: run `track` and
`measure` on a preview clip of a reference take; strike-to-canvas time within 2 frames of
the sim's; knee and elbow angles within 10 degrees for a side-on camera. No file under
`refs/clips/` is tracked by git.

**Cost.** One preview clip. **Show the owner:** the measured table for the self-test clip
and the blank annotation template.

### P6. Cameras from the beat

**Goal.** No more re-renders for framing.

**Change.** In `review.py`, each beat names what must be seen (whole body, face, feet, the
strike). The camera is solved from sim body points and checked by `probe framing` before
rendering: subject 65 to 85% of frame height for full-body shots, target in frame for the
whole beat, camera inside the ropes and above the canvas, face camera follows her travel.

**Acceptance.** The three framing bugs from the study each fail `probe framing` when
reproduced and pass after the solve.

**Cost.** Bakes and a few small stills. **Show the owner:** one A/B/C angle set.

---

## 6. Realism packages

### R1. Soft landing

**Goal.** She lands like a body: one heavy arrival, no rattle, no single-step force spikes.

**Change.** Behind `sim.soft_contact: true`: flesh segments (pelvis, chest, thighs, upper
arms) get softer canvas contact than bony ones (head, knees, elbows, shins). Start near the
study's figure (time constant about 0.015 to 0.02 s for flesh). **Read the current MuJoCo
documentation for `solref`, `solimp` and how two geoms' parameters combine before choosing
values.** Make the penetration gate per segment class.

**Acceptance.** From `probe load` on the three takes: peak single-step canvas force down at
least 5 times; peak 20 ms mean pelvis force in single digits of body weight; at most one
visible rebound of the trunk; resting penetration 5 to 20 mm on flesh, under 5 mm on bone;
outcome gates pass.

**Cost.** Sims, one preview clip. **Show the owner:** before/after preview of one landing.

### R2. Limbs that settle

**Goal.** After the trunk stops, arms and legs keep going: they slide, roll outward and sag,
then come to rest. Nothing freezes mid-air.

**Change.** Behind flags: the residual target yields toward where gravity and contact put
the limb while no tonic phase is holding (the study's C1; `t_relax` partly exists); hip
rotation range and canvas friction checked so a limp leg rolls outward when she is on her
back; passive damping raised only if relaxation brings back bounce.

**Acceptance.** From `probe settle`: limbs continue to move for 0.5 to 2.5 s after the trunk
is still; no joint holds an angle against gravity for more than 1 s at residual tone; still
fraction in the 3 s after landing is under 50%. Run 50 seeded zero-tone drops from standing,
before and after, and commit the distribution of final orientation and settle time. That
distribution also answers whether mass from the mesh is worth building.

**Cost.** Sims, one preview. **Show the owner:** a preview of the 4 seconds after landing.

### R3. Impact face

**Goal.** The face reacts to the hit, asymmetrically, as the owner's reference art shows.

**Change.** Key the asymmetric impact reaction with the existing `ko-impact-face-rig` skill
(near cheek crushed, near eye squeezed, far mouth corner forced open, mouth closed at
contact then forced partly open and shifted), timed from the strike event and scaled by head
angular velocity. Then add slow small noise on lids and brows, irregular partial blinks and
unequal lid heights while she is out (the study's E1).

**Acceptance.** Left/right difference in the driven face controls is non-zero from contact
until 0.3 s after and follows the strike side when the strike is mirrored; mouth-open
control is 0 before contact; no face control is constant for more than 2 s while she is out.

**Cost.** Face close-up samples with `tools/mouth_sample.py`. **Show the owner:** a
six-panel close-up strip across the impact.

### R4. Lighting that shows form

**Goal.** The same motion reads as more real because the body's shape and its contact with
the canvas are visible.

**Change.** A second light preset for the gym beside the current five-light rig: one clear
key, weaker fill, a rim; contact shadows visible under her. Check skin exposure.

**Acceptance.** From `probe look` on three stills: skin pixels clipped under 1%; key-to-fill
ratio between 2:1 and 4:1 on the body; a visible shadow where she touches the canvas. The
old preset remains selectable.

**Cost.** About six stills. **Show the owner:** old and new lighting side by side.

### R5. Neck and jaw

**Goal.** The head whips instead of hinging, and the mouth obeys gravity.

**Change.** Behind flags: a second neck link (upper and lower) with its own passive
stiffness; a passive jaw hinge with a small chin collider, baked to the jaw-open control.

**Acceptance.** Peak angle between upper and lower neck during the head whip is at least 10
degrees; head lag behind the chest at the whip is longer than with one link; jaw opens when
she is on her back and closes when face down, by sign, in two test poses; outcome gates pass.

**Cost.** Sims, face close-up strip. **Show the owner:** close-up preview of a head whip.

### R6. Visible breathing

**Goal.** Breathing can be seen at full-body distance and never pushes through the floor.

**Change.** A breathing curve that is not a sine (inhale about 40% of the cycle, a pause
after the exhale, period and depth varying 10 to 20%, one deep first breath after landing),
driving ribcage, belly and shoulder shape keys or bones at bake time, masked by contact so a
belly on the canvas lifts the back instead. Record breath phase in `frames.npz`.

**Acceptance.** Chest or belly surface moves at least 6 mm peak to peak when free and under
1 mm into the canvas when in contact; breath periods differ by at least 10% within a take.

**Cost.** One bake, one preview. **Show the owner:** a 6-second preview of her at rest.

### R7. Soft tissue and canvas flattening

**Goal.** Impacts read as soft, and nothing passes through the floor when she lands face down.

**Change.** Bake-time damped springs on cheek, lips, bust and belly driven by the sim's head
and trunk acceleration (use the 500 Hz record, not the 30 fps bake); a bake-time deformer
that flattens skin against the canvas with a sideways bulge and a cap on depth. Test a
side-lying sag on the face first: stylised faces can break when pushed physically.

**Acceptance.** `probe ground` shows zero skin below the canvas on a face-down take; spring
displacement stays under a cap the owner sets from a three-level sheet; no injury-like
distortion (owner's judgement on the sheet).

**Cost.** Bakes, close-up stills. **Show the owner:** three amplitude levels side by side.

### R8. Hands, toes, shoulders

**Goal.** The small involuntary details from the `ko_effects` lever family.

**Change.** Clavicle joints for shrug and shoulder roll; finger and toe layers at bake time
(curl, fan, ripple, a raised arm that sinks in stages). Each effect is a lever a take can
ask for, with an outcome check.

**Acceptance.** Each new lever passes its own outcome check on a test take and can be turned
off to reproduce the golden master.

**Cost.** Sims, bakes, one sheet. **Show the owner:** a sheet of the effects.

### Later

R9 coordinated posture variety (three synergy axes, arm side follows head turn). R10
torque-level tremor in a 5 to 9 Hz band scaled by joint saturation. Mass from the mesh only
if R2's drop test shows wrong final orientations. Snoring audio, starting with a 10-second
listening test before any pipeline work.

---

## 7. Choke track (study section G)

Kept from the study: one MuJoCo model, switchable weld and connect constraints, a
compression score from contact on both sides of the neck, one deficit variable driving a
consciousness level. Also kept: the compression score is a tuned animation signal; no real
occlusion force figures are used, ever.

Changed from the study, to fit what Opus does well:

- **Scripted defence first.** The study's task-space defence controller is the riskiest
  piece. Version one uses authored hand-fight poses whose authority is multiplied by the
  consciousness level. Task-space control is a later upgrade.
- **Arms only on screen.** Simulate an unseen torso anchor on an authored path with some
  give, so his arms have something to hang from and can take her weight.
- **Ends at steady state.** No waking, righting or re-orienting in version one.
- **Three presets for movement while out**, default pronounced.

### G1. One consciousness input

**Goal.** The controller takes a consciousness level L between 1 and 0. A strike KO sets it
to 0 at once; a choke will drive it continuously.

**Acceptance.** Golden masters for all strike takes are bit-identical; a test that ramps L
from 1 to 0 over 3 s shows voluntary authority falling smoothly with no step in any torque.

### G2. Two-body scaffold

**Goal.** Her seated, two simulated arms and an unseen torso anchor behind her, the hold
closed and measured.

**Create.** `ko/sim/grapple.py`, `presets/submissions/rnc_back.yaml`,
`presets/attackers/arms_generic.yaml`. Record per-side neck contact force, the compression
score, constraint forces and activity in `sim.npz`.

**Acceptance.** With the hold on: contact on both sides of the neck for at least 80% of the
hold; constraint forces under the attacker preset's strength bound; no solver warnings; the
two bodies never overlap beyond the per-segment limit. Stick-figure strip only.

### G3. Fade and going out

**Goal.** She fights the grip, the fight fails, she goes limp in the hold and his arms take
her weight.

**Create.** Deficit integrator and state sequence in `ko/sim/consciousness.py`; scripted
defence poses in `ko/sim/defence.py`.

**Acceptance.** State order is always conscious, fading, out; time to going out falls in the
sampled 5 to 11 s window within 20%; L never rises while compression is high; at going out
the load on his arms rises and her hands leave his wrist within 0.5 s; a hold released
before the deficit reaches 1 never produces "out".

### G4. Movement while out, release, settle

**Goal.** While out: involuntary movement at three levels. Then his arms open in order, she
slumps, and the take ends when she is still.

**Create.** `ko/sim/jerks.py`: short, irregular, multi-site torque pulses with a random
onset delay, plus tremor and posturing phases from the existing KO layers. Presets:

| Preset | Pattern |
| --- | --- |
| quiet | limp, breathing only |
| mild | onset delay, episode length and frequency sampled from the fainting-study ranges the study cites |
| pronounced (default) | the same pattern with larger amplitude, a longer episode and added tonic posturing; exaggerated on purpose |

**Acceptance.** Pulse intervals are irregular (coefficient of variation above 0.3) and hit
at least three body regions; the pronounced preset's movement energy is at least twice the
mild preset's; after release every constraint is off and no attacker contact force remains
within 0.5 s; the take ends when all joint speeds stay under a threshold for 1 s; all of her
strike-KO gates pass.

### G5. Arms on screen

**Goal.** A reviewable sheet: her mesh, his two arms, framing that never shows where the
arms end.

**Acceptance.** `probe framing` confirms the arm stubs are outside the frame in every panel;
coverage gate passes; outcome gates for the take pass. **Show the owner:** the first sheet
and a motion preview.

---

## 8. Answers to the study's questions

1. **Shared state record.** Yes, as a record: the sim writes extra arrays to `sim.npz`, the
   bake and audio read them. Do not restructure the controller around it.
2. **Torque-level tremor.** The bandwidth argument is right: a critically damped 3 Hz servo
   passes about 12% of an 8 Hz target. Noise in a 5 to 9 Hz band is far below the 2 ms step
   rate, so it should not upset contact; the gate it trips is jitter, which must be split.
3. **Target relaxation with phases as drive.** Holds together if tonic postures stay
   absolute named poses the target blends toward, and relaxation acts only on the residual
   target while no phase is holding.
4. **Mass from mesh or literature.** Decided by R2's drop test. My expectation: contact
   shape and softness change falls more than a 20% shift in segment mass.
5. **Stimulus mapping.** Plain synergy variation gets most of the value. Keep one causal
   rule: the arm side follows the head turn.
6. **Soft contact.** Per-segment contact softness first. Flex bodies are too costly on two
   cores. Check the MuJoCo documentation before tuning.
7. **Snore synthesis.** A 10-second listening test settles it and is the whole first step.
8. **Organic metrics.** None is validated against the owner's taste. Report all, gate on
   none, and log each owner A/B choice beside the numbers. Once P5 has footage, the
   reference ranges become the better yardstick.

Choke questions from the study: start with one deficit variable; a single rigid neck is an
acceptable proxy for version one, improved by R5's second neck link; welds for the frame of
the hold and plain contact for the neck; the unseen torso anchor is the smallest attacker
that shows load transfer; involuntary jerks get their own generator, sharing only the noise
source with tremor; numbers from the cited papers are animation priors and were read from
summaries, so treat them as approximate.

---

## 9. Prompt to start each Opus session, and the `ko-sim` skill

```
Read docs/OPUS_HANDOFF.md section 3, then docs/STATE.md, docs/DECISIONS.md and tools/INDEX.md.
Do package <NAME> only. Before changing anything, tell me in three lines: the package's goal,
its acceptance test, and which existing files you will change. Extend existing tools; do not
add a script if the index has one for the job. When the acceptance test passes, update
STATE.md, commit, push, and show me only what the package says to show. If something in the
package is wrong or blocked, stop and tell me; do not work around a gate.
```

```
name: ko-sim
description: Turn a described knockout into a simulated, checked, reviewed take in the ko
  framework. Use for any KO, fall, collapse or choke animation request in this project.

Framework: the `ko` Python package (stages character -> body -> sim -> qa -> bake -> render,
cached by input hash). Takes are YAML in takes/, built from presets/ (characters, arenas,
archetypes, house.yaml). Not the old Mac scripts (ko_scenario.py, *_hull.xml): ignore those.

Before anything: read docs/STATE.md, docs/DECISIONS.md, tools/INDEX.md.

Order of work for a take, cheapest first. Do not skip a step.
1. Write or update the take YAML and its outcome list (what the owner asked for, as checks).
2. python -m ko.cli build takes/X.yaml --to qa          (seconds)
3. python tools/probe.py all takes/X.yaml               (numbers; fix here, not in a render)
4. python tools/review.py strip takes/X.yaml            (stick figure)
5. python tools/review.py preview takes/X.yaml          (low-sample motion preview, minutes)
6. python tools/review.py sheet takes/X.yaml            (owner reviews this)
7. Only after the owner approves the sheet: queue a video with tools/queue.py.

Rules: QA gates are never bypassed. Nothing is deleted; archive instead. Left and right are
hers. Say what is measured and what is tuned by eye. Always clothed, coverage gate passing;
no blood or injury detail; the opponent is only a glove, a shin, or two arms; no slow motion
or camera shake. Mouth closed at contact, then forced partly open and shifted. About 30% of
the pupil showing. The mouthguard stays in through the KO and is knocked out by the follow-up
over a fraction of a second. Momentum carries through the shutdown. A limp body loads,
rebounds once softly, then lets go. Tremor comes from effort. Give times in UTC-6.

New behaviour goes behind a YAML key that defaults to the old behaviour, with a golden-master
test. One tool per job: extend, do not add.
```

Opus should correct any command in the skill that does not match the tree during P0.
