# Lever catalog

One YAML file per family. A lever is one adjustable, nameable thing a description can ask for.

    - id: elbow.extend            # family-unique; referenced by beat sheets
      label: Elbow straightens / locks out
      say: [elbow extend, arm straighten]    # prose phrases; word stems, up to 2 words between
      side: LR                    # LR = needs a side (left/right/both/one); omit if none
      region: arm                 # controller region the pose belongs to (arm, leg, trunk, neck)
      pose: {forearm_$S_flex: [70, 0]}       # joint: [degrees at intensity 0, at intensity 1]
      mirror: true                # values are for 'toward her left'; negated for right
      check: {pred: ..., min: .., max: ..}   # explicit observation (or a list of them)
      layer: {toes: {...}}        # non-sim layer or controller feature it drives
      expands: [...]              # macro: a named posture built from other levers
      src: log | bible | new      # owner's logged notes / Animation Bible vocabulary / proposed
      approved: false             # owner sign-off; unapproved levers still work, flagged in reports

Status is computed, never written by hand:
  drives+checks  has `pose` (the checker measures how far the pose was reached, 0..1)
  drives         has a `layer` the compiler understands, no measurement yet
  checks         has `check` only: an outcome, reached by tuning strikes/stance + seed sweep
  planned        neither: recognised in prose and reported as UNVERIFIED, never dropped

$S = the lever's side, $O = the other side. min/max may be [value at 0, value at 1].
Angles are anatomical, verified numerically per rig: flex + = flexion, abd + = away from
midline, twist + = internal rotation (arm) / external (thigh) / pronation (hand),
lat/twist of trunk and neck + = toward her left, foot_dorsi - = pointed toes.
Left/right is always HER left/right.
