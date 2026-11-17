# Solutions to the Brainstorm Brief (2026-11-17)

Reply to "KO Sim: Brainstorm Brief", section "Problems for a powerful model". Each of the 23
problems gets a design, an executable plan and an acceptance test. Six were worked on the
three reference takes in this session and carry measured results; the rest are designs.

Everything here was run on the merged branch (`claude/new-session-3jhr9r`) with the Izzy
assets installed. Sims only: no bake or render was done, so anything about the rendered
picture is still unmeasured.

## What was measured, and what it changes

| Finding | Numbers | Consequence |
| --- | --- | --- |
| The "43 body weights" is a one-step solver spike, not the load | Peak single step 20 to 51 BW; the same landings averaged over 20 ms are 4.7 to 6.2 BW | Landing forces are already plausible. Judge contact by the 20 ms mean. The brief's R5 target ("peak force inside the band") is met today on that measure. |
| The real contact defect is chatter | Non-foot segments make and break canvas contact 356 to 996 times per take; the pelvis rebounds 3 to 14 times | "Hits the canvas like furniture" is rattling, not hardness. R5 is redefined around touchdown count and rebounds. |
| Softening the whole canvas is a trade, not a fix | From the gym's 0.003 s to 0.02 s: step spike down 3 to 4 times, chatter down about half, penetration up from 2 to 4 mm to 9 to 15 mm, and the head-kick take's end state flips from prone to supine | Soften flesh segments only, keep bone stiff, and hide the sink with a flattening deformer. Do not change the canvas globally. |
| One shipped take is a lucky seed | Chair take under 8% strike perturbation: 19 of 20 seeds fail the jitter gate (the shipped seed sits at 0.46 against a 0.5 limit) | "Anything the sim does looks believable" is not yet true for this archetype. |
| End states are not stable | Head kick "ends face down": prone 10, on her side 8, supine 2 of 20. Uppercut: supine 20 of 20 | A named end state needs a seed search or a steering term; an unnamed one needs the distribution shown to the owner. |
| The owner's words already parse into checks | The three takes described in the owner's own phrases: 26 claims pass, 8 fail, 4 cannot be measured yet | E1 is working. Some failures are real (no upper-back lift, heels higher than asked); some are the sheet guessing a side the owner never stated. |
| Nothing is ever fully still | In all three takes no 30 fps frame has every joint under 0.1 degrees of motion | "The aftermath reads paused" is not stillness in the sim. It is motion too small to see at render distance. V3 must be judged in rendered pixels. |
| Fast preview | Workbench and Eevee do not run in this container (no `libEGL`, install blocked). Cycles at 1 sample, 480 px: about 1.5 s per frame on a simpler scene | E6's answer here is low-sample Cycles. The brief says EGL libraries are present in the Opus container, so test Workbench there first. |

New in the tree from this session: `tools/probe.py` (outcomes, load, settle, organic,
endstate, ensemble, baseline), three levers (`legs.heels_lifted`, `arms.locked_unequal`,
`rest.on_canvas`), beat sheets for the three reference takes under `takes/beats/`, ensemble
results in `docs/ensemble_*.json`. A correction to the brief: a lever for "ankles crossed"
already existed (`legs.ankles_cross`).

## Decisions from the brief that change the earlier handoff

The handoff (`OPUS_HANDOFF_2026-11-16.md`) stays the session guide. These owner answers
override it where they differ:

- Tonic posture starts from a muscle model with authored overrides (R1 below). The handoff
  had set muscle models aside.
- Full body first, then face close-up.
- Reduced range of motion is preferred to clipping; a small hidden overlap is acceptable.
- A one or two frame impact hold is allowed. Only handheld wobble is banned; a single-frame
  camera kick is allowed.
- The impact face is approved to build.
- Effects are realistic by default; speed lines and flashes only on comic-style sheets.
- It is a fight with a winner. No referee or medic. The winner is rendered later.
- End states are tested when named; otherwise whatever the sim does must look believable.
- Aftermath runs at least 5 to 9 s.
- Reference standard: real-time play stays fast and hard to read; replays and close-ups
  carry held poses and exaggerated expression.

## Order

Measured-first, then what the owner ranked. Each line is one Opus session.

1. E5 self-check, E1 wiring into QA (the tools exist; this makes them gates)
2. R4 + V4 ensemble as a standing report; fix the chair take's jitter
3. E6 + E2 preview tier and the single review tool
4. R5 segment-wise contact
5. I1 strike-aware camera, I2 impact punctuation (both are edit-side, cheap, high impact)
6. R2 reachable poses
7. V3 signs of life
8. I4 impact face with exaggeration
9. R1 muscle-driven posture
10. E3 render cost, E4 scheduler
11. R3 bands, V1 severity
12. I3 edit grammar, V5 aftermath camera
13. R6 mass and clavicle, I6 props, I5 sound, V2 winner interface

---

## Realism

### R1. Muscle-driven tonic posture

**Design.** A lumped antagonist model, not anatomical muscles. Each of the 37 joints gets a
flexor group and an extensor group. Each group has an activation between 0 and 1 with
first-order dynamics (fast rise, slower fall), a strength curve over joint angle (strongest
mid-range, weaker toward the ends), and a short-range stiffness that grows with activation.
Joint torque is flexor pull minus extensor pull minus passive tissue. A posture is then an
equilibrium between the two groups, gravity and contact, not an angle the joint is driven to:
push a limb against the canvas and it stops there and strains. Three additions give the
behaviour the owner asks for: a stretch reflex with a short delay (produces tremor and
clonus at the end of range without a timer), fatigue (capacity drains while activation is
high, so a long hold sags and shakes more), and co-contraction (both groups on: stiff
without moving).

Postures become activation recipes per body region (for example extensors dominant in the
legs, flexors in one arm and extensors in the other). The authoring layer has three knobs:
an override weight that blends the existing angle-target servo back in per region (0 pure
muscle, 1 legacy), a bias that shifts where each group's strength curve peaks, and one
exaggeration number that scales activations and pushes equilibria toward the end of range.

Keep it implicit-stable the way the controller is now: each step, linearise the torque
about the current angle and write gain and bias into the existing actuators.

**Plan.** `ko/sim/muscle.py` (groups, activation, curves, reflex, fatigue), a
`controller.mode: muscle` key defaulting to the legacy path, recipes in
`presets/postures/*.yaml`. Fit the three reference postures by search: about a dozen
region-level activations per posture, objective = joint error at the peak of the hold, each
evaluation one 6 s sim.

**Acceptance.** The brief's: the three escalated postures within 10 degrees per joint at
peak using the override layer; the exaggeration knob moves them visibly further (monotone in
`probe outcomes` intensity); sim time at most twice today's; legacy golden masters unchanged.
Add: a limb blocked by the canvas shows rising activation and rising tremor in the record.

**Risk.** It is still authored: recipes replace angle tables. The gain is that contact and
load now change the result. Say so; do not call it physiology.

### R2. Range of motion instead of clipping

**Design.** Two parts. First, replace the take-wide `sim.exclude_pairs` with explicit
contact pairs for thigh against thigh and shin against shin that are soft and allow a set
overlap (10 to 15 mm, standing in for flesh compressing), so legs rest against each other
instead of passing through. Second, a pose resolver that runs before the sim: given a
requested pose, minimise weighted joint distance to it subject to joint limits and to no
pair overlapping more than its allowance, on the kinematic model only (collision query, no
dynamics). It returns the nearest reachable pose and the error per joint.

**Plan.** `ko/body/reach.py` with `resolve(pose) -> (pose, error)`; the compiler calls it for
every pose lever and writes the error into `compile_notes`; pair allowances in the character
preset. Start with the leg set (hips and knees, both sides).

**Acceptance.** "Ankles crossed" and "arms locked at different angles" on the uppercut take
with at most 5 mm overlap measured on the render mesh, or the resolver reports the nearest
reachable pose and its error. `sim.exclude_pairs` removed from the take.

### R3. Plausibility bands without footage

**Design.** Three sources, labelled per row, replaceable by footage numbers later:
physics bounds that need no citation, our own ensembles, and literature Opus must open and
cite (not quote from memory).

| Quantity | Bound | Basis |
| --- | --- | --- |
| Strike to first non-foot contact | No less than about 0.43 s (free drop of a hip at 0.9 m); under about 1.5 s for an unsupported topple | Physics |
| Head speed at the canvas, unassisted | No more than about 5.6 m/s (free fall from 1.6 m) | Physics |
| Pelvis load on landing, 20 ms mean | Single digits of body weight | To source; today 2.7 to 4.5 |
| Visible rebounds of the trunk | 0 to 1 | To source or footage; today 3 to 14 |
| Strike to down, per archetype | Today's ensembles: uppercut 0.95 to 1.08 s, chair 0.94 to 1.13 s, head kick 0.59 to 0.61 s | Ours, not a reference |

**Plan.** `presets/bands.yaml` with a `basis` and `source` per row; `probe bands` scores a
take. Opus fills the "to source" rows from papers it has opened.

**Acceptance.** Every row has a basis; each reference take gets a score; the trunk-rebound
row fails today, which is correct.

### R4. "Anything that happens looks believable", made testable

**Done here.** `python tools/probe.py ensemble takes/X.yaml -n 20` perturbs strike impulse,
direction and timing and reports end states, QA pass rate with causes, and outcome pass rate.

| Take | QA clean | Cause of failures | End states |
| --- | --- | --- | --- |
| Uppercut | 95% | canvas penetration, once | supine 20 |
| Head kick 002 | 95% | joint-limit overshoot, once | prone 10, side 8, supine 2 |
| Chair | 5% | jitter gate, 19 times | supine 19, prone 1 |

**Plan.** Add the R3 band score to each row; run it in QA as a report for every new
archetype; fix the chair take's jitter (find which joint and which phase with `probe`,
before touching any number).

**Acceptance.** The brief's: at least 90% of 20 runs inside the bands with no hand tuning,
failures classified by cause. Two of three takes are at 95% on QA today; none is scored on
bands yet.

### R5. Compliant contact

**Measured here** (six canvas settings, three takes; table at the top). Conclusions: the
load is fine, chatter and rebounds are the defect, global softening trades chatter for sink
and changes outcomes.

**Design.** Contact softness per segment: flesh (pelvis, chest, thighs, upper arms) soft,
bone (head, shins, forearms, hands, feet) as stiff as now. Find the chatter's source before
tuning: per-segment touchdown counts are in `probe load`; test whether tremor or hull edges
drive it by rerunning with tremor off. Hide the remaining sink at render time with the
flattening deformer.

**Plan.** Per-geom contact parameters in `gen_body.py` behind `sim.soft_contact`; read the
MuJoCo documentation on how two geoms' parameters combine before choosing values; a
segment-aware penetration gate.

**Acceptance.** Non-foot touchdowns per take under 100 (today 356 to 996); pelvis rebounds
at most 1 (today 3 to 14); 20 ms mean load unchanged within 20%; resting sink 5 to 15 mm on
flesh and under 5 mm on bone; the three takes keep their end states; 20-seed QA clean rate
does not fall.

### R6. Mass and inertia from the mesh, and a clavicle

**Design.** Partition the body mesh by dominant bone weight, cap the cuts, exclude hair,
clothing and eyeballs, integrate volume, centre of mass and inertia with a density per
tissue type, normalise to total mass, and clamp each segment share to within 30% of the
published table, logging any clamp. Add a clavicle joint per side (elevation and
protraction).

**Acceptance.** The brief's: segment masses within 10% of a published female table that
Opus has opened, and landing orientation change measured with `probe ensemble` before and
after. If the end-state distribution does not move, stop there and keep the table.

---

## Selling the impact

### I1. Strike-aware camera

**Design.** From the sim alone: take the head's displacement over the first 0.15 s after
contact. The camera's view direction is horizontal and perpendicular to that displacement,
so the motion crosses the screen. Of the two sides, pick the one facing the struck cheek;
reject it if a ray from camera to head passes through her own guard arm or shoulder, or if
the camera would sit outside the ropes. Frame on the head with room in the direction of
travel.

**Plan.** A `strike` shot type in the review tool; `probe framing` projects sim points
through the solved camera, so the test needs no render.

**Acceptance.** The brief's, computed by projection: on all three takes the head moves at
least 15% of frame height in the first 0.15 s and the struck side faces the camera.

### I2. Impact punctuation

**Spec.** Three tools, all applied in the edit, none needing a new render:

- **Hold.** At the contact frame, show that frame for one or two extra output frames (40 to
  80 ms at 25 fps), then continue at real time. Nothing else is slowed.
- **Kick.** On the frame after contact, shift the picture 1.5 to 3% of its width along the
  strike direction, half that on the next frame, zero on the third. Render with 4% overscan
  so the shift is a crop. A decaying single impulse is not handheld wobble.
- **Cut on contact.** The outgoing shot ends on the frame before contact; the strike-aware
  shot begins on the contact frame.

**Two variants to render as a strip on the uppercut take.** A: cut on contact plus a
one-frame hold. B: no cut, two-frame hold plus kick. The owner picks.

**Acceptance.** The brief's: written spec (this) and both variants as a contact strip.

### I3. Edit grammar for live plus replays

**Design.** A template filled from sim events, written as a cut list:

1. Live: one wide angle, real time, from before the strike to 2 s after she settles. Fast
   and hard to read on purpose.
2. Replay 1: the strike-aware angle, real time, with the chosen punctuation.
3. Replay 2: held poses. Three stills at contact, at the top of the fall and at landing,
   each held 0.6 to 1.0 s, with the impact face at full exaggeration on the first. Stills,
   not slowed motion.
4. Aftermath: the tonic posture from the angle set with the most variety, then the high
   angle.

**Acceptance.** The brief's: one command builds a 20 to 30 s sequence for any take with no
hand edits, timings from the sim events.

### I4. Exaggeration control for the impact face

**Design.** One number from 0 to 1 scales every feature of the asymmetric impact face (near
cheek crush, near eye squeeze, far mouth corner, jaw shift and opening), each with its own
cap so no single feature can run away. Live play uses 0 to 0.3; replays and held poses 0.7
to 1. Mouth stays closed until contact at every setting.

**Acceptance.** The brief's: close-up samples at 0, 0.5 and 1; the owner marks where it
turns uncanny and that value becomes the cap.

### I5. Procedural sound from sim data

**Design.** Every contact and its impulse is already recorded at 500 Hz. Build a cue list
(time, impulse, part, surface) and synthesise: glove on head as a short noise burst over a
low thump; canvas landings as a decaying low tone plus noise, longer for trunk than for
limbs; slides as filtered noise gated by slip speed times load. Level follows impulse.
Write a 48 kHz WAV per shot and mux at encode time.

**Acceptance.** The brief's: each onset within one frame of its sim contact, on one take.
Include a 10-second listening test before anything is wired in.

### I6. Glove and shin prop

**Design.** A glove is read by its silhouette: a padded knuckle mass wider than the wrist,
a separate thumb lobe, a cuff band with lacing or a strap, a tapered wrist. Model it
procedurally from those four parts, two-tone, and give the prop motion blur along its path
on the strike frames only.

**Acceptance.** The brief's blind look at 640 px on the A01 and B01 panels.

---

## Selling the victory and the defeat

### V1. Severity scale

**Design.** One severity number per strike, from 0 to 1, that drives everything the viewer
reads as "how hard": strike impulse, how fast control switches off, how far she travels, how
violent the head whip is, how rigid and how long the posture holds, and how long until the
first sign of life. Each is logged by `probe` (strike to down, travel, peak head angular
speed, hold length, time of first breath).

**Acceptance.** The brief's: five takes of one strike at rising severity; every logged
dimension moves in one direction (rank correlation of 1).

### V2. Interface for the winner

**Design.** Extend the strike record with where the blow comes from: striking limb, its
path as timed points, contact point on her, closing speed and effective mass. Impulse is
derived from the last two. A winner rendered later reads the same record, so her sim never
has to be rerun.

**Acceptance.** The brief's: a strike rebuilt from the new schema reproduces a reference
take's sim bit for bit.

### V3. Signs of life

**Design.** Driven by state, in the bake: a first deep breath 0.8 to 2 s after landing;
breathing with unequal periods and depth, visible on chest and belly and masked where she
touches the canvas; a finger or toe movement when tone fades through a threshold; a slow
eye change as the gaze returns from the upward stare; snoring-related mouth movement when
she is on her back with the chin down. Each has a cause in the record, none a fixed timer.

**Acceptance.** Judged in rendered pixels, since the sim is never still: in a low-sample
preview of the aftermath, no 1-second window without a surface point moving at least 2
pixels at 640 px, and the autocorrelation of chest motion between 1 and 6 s stays under 0.5
(today 0.07 to 0.15 in the sim, where it is invisible).

### V4. Believable end states

**Done here** as part of the ensemble: the end-state distribution per take (table under R4).
Nothing exists to compare it with until footage arrives.

**Plan.** Show the distribution to the owner as a stick sheet per archetype (one figure per
end state with its share). For a named end state, search seeds and small strike changes for
one that reaches it, and report how rare it was.

### V5. Aftermath camera

**Design.** Rules picked from the beat: the first aftermath shot is high and looks down at
35 to 60 degrees so she reads small; a push-in no faster than 3% of frame per second; one
low shot from the side the strike came from, the winner's side; the greatest variety of
angle during the tonic posture; the last shot wide enough to show her whole body and the
empty canvas around her.

**Acceptance.** The brief's: the rule set applied by the angle tool on all three takes.

---

## Efficiency

### E1. The owner's words as tests

**Done here.** The owner's descriptions of the three takes, typed as prose, parse into beat
sheets and are checked against the sims:

| Take | Pass | Fail | Cannot measure |
| --- | --- | --- | --- |
| Uppercut | 15 | 4 | 3 (fists, stiff tier) |
| Head kick 002 | 3 | 2 | 1 (mid-punch setup) |
| Chair | 8 | 2 | 0 |

Real failures: no upper-back lift (no clavicle), heels at 34 cm against a 11 to 30 cm band,
hands take load in the head-kick fall, back curl stronger than "moderate". Sheet-side
failures: where the owner named no side, the parser picked one from the seed and the take
did the other.

**Plan.** Let a claim carry `side: any` when checking an existing take; wire the sheet into
QA after the sim (the hook exists as outcome `beats`); add the render-space check for
`rest.on_canvas`; have the owner approve the three sheets.

**Acceptance.** The brief's: all phrases the owner used this week parse; each check agrees
with what the owner said about the take.

### E2. One review plan

| Tier | Command | Cost | Answers | Must pass first |
| --- | --- | --- | --- | --- |
| Stick strip | `review strip` | seconds | timing, staging | QA and outcome checks |
| Motion preview | `review preview` | minutes | does the motion read | stick strip looked at |
| Contact sheet | `review sheet` | about 7 min | pose, look, framing | framing probe |
| Comic page | `review comic` | about 15 min | A/B/C angles, comic effects | sheet approved |
| Video | `review video` | hours | final | sheet approved by the owner |

**Acceptance.** The brief's: one tool, one command per tier, measured cost per tier, no
duplicate scripts left in `tools/` (moved to `_archive/`).

### E3. Halve CPU render cost

Plan as in the handoff's P4: a static arena plate per camera with the character rendered
cropped and composited outside Blender; fewer samples with the denoiser; shorter light
paths; simplified hair and smaller textures at viewing distance. Measure each with a
high-sample reference frame. **Acceptance.** The brief's.

### E4. Scheduler

Plan as in the handoff's P3, plus disk: delete build cache directories that no current
take's lock file points to, never anything under outputs or drafts, when the disk passes
80%. **Acceptance.** The brief's.

### E5. Self-maintaining knowledge

**Design.** `tools/selfcheck.py`, run before every commit: every script in `tools/` has a
row in `tools/INDEX.md`; every path named in a skill or the README exists; the Blender
version in the README matches the installed module; every lever id used in a beat sheet
exists in the catalog. **Acceptance.** The brief's: it fails on a missing index entry or a
dead path.

### E6. Fast preview

**Measured here** (top table). In this container the answer is Cycles at 1 to 4 samples and
480 px. In the Opus container, test Workbench first since the EGL libraries are there, and
keep whichever renders a 20-frame sheet in under 2 minutes.
