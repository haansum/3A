# To-do: not started, waiting for the owner's OK

Ordered by how much each raises quality when a weaker model runs the pipeline.
"Unlocks" = catalog levers that move from planned to driven or checked.

| # | Item | What it adds | Unlocks | Size |
| --- | --- | --- | --- | --- |
| 1 | Annotated stick filmstrip from beats | One frame per beat boundary, each claim's PASS/FAIL and measured value printed under it, contacts and facing arrow drawn | review speed; no new levers | S |
| 2 | Beat-driven contact sheet | One still per beat per shot with the beat label; replaces fixed key moments | review speed | S |
| 3 | Render-side gates | Mesh clipping, face-visible fraction, iris-visible fraction (ID pass), framing, exposure | look.no_clipping, rest.face_visible, eyes.pupil_visible, cam.raise_for_face | M |
| 4 | Seed pass-rate gate with strike perturbation | Take is renderable only if beats pass on most perturbed seeds | robustness; no new levers | S |
| 5 | Face layer by meaning | Per-character map from jaw_open / frown / lids / brow to that rig's shape keys, measured not named | 20 face.* and eyes.* levers | M |
| 6 | Fingers and toes layer | Curl / spread / claw / twitch on finger and toe bones, with a measurement | 12 hand.* and toes.* levers | M |
| 7 | Clavicle joints | Real shrug and shoulder protraction instead of the arm-twist stand-in | shoulder.shrug, shoulder.roll_forward, trunk.upper_back_hunch | M |
| 8 | Per-strike response layer | Jolt size, "straighten further each strike", snap back to neutral, driven per follow-up | dyn.jolt_*, elbow.extend_more_each_strike, legs.jolt, neck.snap_back_neutral | M |
| 9 | Shot compiler | cam.* levers to shot list and shot arguments (length, pan start, orbit start, zoom-out) | 28 cam.* levers | M |
| 10 | Variety engine | Seeded fill of unspecified levers from approved options, "avoid recent" memory across takes, small left/right asymmetry everywhere | vary.* | M |
| 11 | Stagger-step controller | Balance-recovery steps, knee dips, delayed drops | stagger.*, legs.stanky, feet.step_back, fall.delayed | L |
| 12 | Mocap / BVH reference | Real pre-KO motion in place of procedural keys | setup.mid_punch, setup.mid_kick, setup.shooting | L |
| 13 | Slow and joint-specific motion layer | Slow rises/sinks, flutter, pedalling, heel drumming, growing tremor, fade order | shoulder.slow_rise, legs.scissor_flutter, legs.pedal, timing.limb_order, reflex.* | M |
| 14 | Per-joint tone | Limp wrists with stiff elbows, one-side tighter | wrist.limp, tone.asym_side | S |
| 15 | Arena pieces | Corner pad, apron, cage wall | arena.corner, arena.through_ropes, arena.cage_wall | M |
| 16 | Secondary motion | Spring-bone hair, soft tissue, cloth | sec.* | L |
| 17 | Stature-relative limits | Heights and distances in the catalog as fractions of her height, not metres | accuracy on very tall/short rigs | S |
| 18 | Revision notes on an existing sheet | "reduce core crunch by 10%", "replay 2 longer by 35%" applied as edits to the stored sheet | all levers, relative edits | S |
| 19 | Footage calibration | Measure fall time, bounce height, tremor frequency from reference clips to replace by-eye bands | every by-eye limit | L |

## Known weak points of what was just built

- Check limits in the catalog are first guesses tuned against one take. Expect to adjust them.
- The parser is a lexicon. It cannot resolve "it", contrast ("not X but Y" across sentences) or a
  trigger placed mid-sentence; it flags the last case and lists everything it could not place.
- Pose levers are judged as movement since the beat opened. A pose that physics prevents
  (e.g. lifting the upper back with no clavicle joint) shows as FAIL, correctly.
- Several levers on one joint in one beat: the last one wins, and the compiler says so.
- Seeds currently change only tremor phase unless `sim.perturb` is set.
