# MMA Pose Studio — Animation Bible

Master reference for finish physics and post-finish behavior. The
simulation engine (`src/engine/`) implements these rules; scene prose is
generated to comply with them.

---

## Universal Principles

### Law 1: Conservation of Momentum Through Shutdown

The KO removes the pilot. It does NOT remove the physics. Whatever the
body was doing at the moment consciousness left continues on pure
inertia until friction, gravity, or collision stops it.

- A fighter KO'd while attacking falls forward or rotationally.
- A fighter KO'd while retreating falls backward.
- A fighter KO'd mid-takedown-shot collapses along the line of the shot.
- Falls are NEVER arbitrary in direction.
- Clenched fists relax within moments of shutdown; grip is voluntary.
- The audience should be able to read the ghost of the last intent in
  how the body falls.

Engine mapping: the victim's momentum context (`advancing`, `retreating`,
`shooting`, `flat`) is tracked at the moment of every finish and selects
the fall kinematics bank.

---

## Part 1: Knockouts ("System Failure")

A knockout is a neurological system failure, not sleep. KO results from
**rotational acceleration** — strikes that spin the skull (hooks,
overhands, head kicks, uppercuts, elbows, knees) carry more KO power
than straight pushes. Body shots fold a fighter (conscious, breathless
agony) rather than switching the lights off. Leg kicks chop the base
out but do not produce head-trauma KOs.

Engine mapping: each strike kind carries a KO profile (knockdown
multiplier, deep-KO bias, target zone) that scales knockdown and finish
probabilities.

### The Four Phases

1. **Impact** — head rotates on the strike axis; eyes go fixed and
   dilated on this frame. Consciousness leaves before the body reacts.
2. **Short circuit** — postural collapse. Knees buckle inward (valgus)
   or lock straight (timber).
3. **The Jolt** — on head-to-floor contact the fencing response fires:
   limbs snap outward, asymmetric, brief.
4. **Agonal state** — four layers: stiffening (asymmetric, one side
   worse), the hollow settle (awkward, undignified), automatic
   breathing (labored, rattling snore), and the nerve zing (ONE
   extremity twitching — a finger; never multiple limbs).

### KO Tiers

- **Level 1 — Flash KO (the Stumble):** disconnected for a beat, no
  fencing response, jelly legs, eyes open and searching. The fighter
  tries to rise, fails, may grab the fence. The referee rescues them
  mid-stumble.
- **Level 2 — Stiff KO (the Statue):** total neurological lock. Rigid
  timber fall preserving the pre-KO pose, strong fencing response,
  stiffening, delayed rattling snore, single-finger twitch.
- **Level 3 — Deep KO (the Melt):** the body liquefies — knees first,
  cascading collapse into a compact heap. Mild or absent fencing
  response, IMMEDIATE heavy agonal snoring, minimal twitching.

### Anti-patterns (enforced in prose banks)

- Eyes never close peacefully — they stay open, fixed, empty.
- No graceful arm placement; limbs land trapped and wrong.
- Stiffening is asymmetric; one side always worse.
- One twitching extremity, never several.
- Fall direction always follows pre-KO momentum.
- Post-KO eyes track nothing.

---

## Part 2: Blood Chokes ("Melt-to-Seize")

A choke is a drain, not a surge — a battery dying, not a breaker
tripping. Phases:

1. **Panicked struggle** — everything clenched, hands clawing, legs
   bicycling, sharp erratic movement.
2. **The wet melt** — extremities die first: fingers stop hooking,
   become flat brushes, hands SLIDE off and fall. Then the spine
   liquefies in a wave, head lolls, the opponent suddenly carries all
   the weight. Eyes drift and cross.
3. **Release** — the body pours to the mat, sack-of-sand, mild jolt at
   most.
4. **Seizing reboot** — choke-specific signature: toes curl DOWNWARD
   hard (plantar flexion), rhythmic FOOT twitch (not finger), wet
   guttural snore with sharp stomach crunches, compact heap.

Tiers by hold duration: **Snap Sleep** (quick out, wakes in seconds,
tries to stand too early), **Deep Sleep** (full melt, fencing on
release, toes pointed hard), **Broken Sleep** (held far too long —
bilateral leg quiver, the one exception to the single-limb rule;
longest, most confused recovery).

High-heart fighters refuse to tap and go out instead — technical
submission, put to sleep.

---

## Part 3: Slam KOs ("Kinetic Shutdown")

A slam is a gravity weapon: potential energy converted to axial
compression. Pre-impact the victim is either **Spring** (conscious,
tense, fighting it) or **Water** (already out, head swinging free).

- **Spike (high-crotch / inverted):** the accordion — shoulders shrug
  violently toward the ears as the torso mass catches up to the head.
  Starfish jolt, then the permanent hunch.
- **Powerbomb (double-leg lift):** the pancake — flat back impact, the
  head bounces off the mat ONCE (the second impact is the KO), full
  starfish, then straight to the melt. No stiffening phase.
- **Suplex-arc (body lock):** brief involuntary bridge on impact, then
  the Void — eyes fixed on the rafters, gasping (not snoring) because
  the diaphragm took the compression.

Engine mapping: high-amplitude takedown kinds (double, body lock,
high-crotch) carry a small slam-KO probability that scales with the
power/chin mismatch and accumulated damage.

---

## Part 4: Wake-ups

Recovery arrives in involuntary stages: twitching mistaken for waking,
eyes rolling around before they focus, then confusion — fighters ask if
the fight has started yet, try to stand before the referee lets them.
The deeper the finish, the longer and stranger the wake-up.
