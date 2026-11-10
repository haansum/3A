# ko — KO animation framework

Described knockout → physics simulation → baked Blender animation → rendered cut.
Every take is rebuilt from one manifest. Self-contained: this directory is meant to be
lifted into its own repository as-is.

    pip install -e ".[blender,dev]"        # mujoco 4, bpy 5.2 LTS (Blender as a module)
    python -m ko.cli build takes/stiff_back_001.yaml            # draft cut
    python -m ko.cli build takes/stiff_back_001.yaml --quality full
    python -m ko.sweep takes/stiff_back_001.yaml --set arena.rope_distance=0.8,0.9 --seeds 1,2,3
    python -m pytest

## Stages

| Stage | Code | Reads | Writes (`build/<stage>/<key>/`) |
| --- | --- | --- | --- |
| character | `ko/character` | any rig: `.blend .vrm .glb .gltf .fbx` | `character.blend`, `skeleton.json`, `skin.npz` |
| body | `ko/body` | skeleton + skin | `body.json` (hulls, joints, masses) |
| sim | `ko/sim` | body + manifest | `sim.npz` (500 Hz state, contacts, rope nodes, tone, assist) |
| qa | `ko/qa` | `sim.npz` | `qa.json`; a failure stops the chain |
| bake | `ko/bake` | sim + character | `take.blend` (named action), `bake.json` (round-trip error) |
| render | `ko/render` | bake | `scene.blend`, per-shot video, cut, contact sheet |

A stage's key hashes the config it reads, its upstream keys and its own source code, so an
existing directory is a cache hit and any stage reruns alone.

## From a description to a checked take (beats)

    python -m ko.beats.parse takes/beats/x.txt --seed 2 --name x --out takes/beats/x.yaml
    # owner reads the sheet, edits it, sets approved: true
    python -m ko.cli build takes/x.yaml --to qa      # take file has `beats: takes/beats/x.yaml`
    python -m ko.beats.selftest takes/beats/x.yaml build/sim/<key>/sim.npz
    python -m ko.beats.catalog                       # validate catalog, regenerate docs/LEVERS.md

Prose is matched against the lever catalog (`ko/beats/catalog/*.yaml`, review list in
`docs/LEVERS.md`) with no model call, giving an ordered beat sheet: each beat opens on a
physical event and lists levers with a side and an intensity. `ko.beats.compile` turns the
sheet into controller phases, strikes and bake layers; `ko.beats.check` measures every claim
with generic predicates (`ko/beats/predicates.py`) and reports PASS / FAIL / UNVERIFIED per
beat. QA stops the chain on any FAIL and on a sheet the owner has not approved. No
scenario-specific checking code is needed for a new scenario. Open work: `docs/TODO.md`.

## Manifest layers

`presets/characters/` (locked once) · `presets/arenas/` (once) · `presets/archetypes/`
(validated preset) · `takes/` (a few overrides + seed + quality). `ko.manifest.resolve`
merges them into one lock file whose hash stamps every output.

## Bringing in a rig found online

    python -m ko.cli import path/to/rig.blend --name mychar

prints the automatic bone map (VRoid/VRM, Mixamo, Rigify and similar naming are recognised;
spine/chest/neck are found from the hierarchy). If an entry is wrong, put the right bone
name under `bone_map:` in `presets/characters/mychar.yaml`. Requirements: a humanoid armature
saved in a T- or A-pose, meshes skinned to it. The source file is never modified.
Tested so far on one VRoid VRM only; other rig families are covered by naming unit tests,
not yet by a real file.

## What is real, what is assumed

| Item | Status |
| --- | --- |
| Rope sag, ringing decay | Tested against analytic cable results (`tests/test_rope.py`) |
| Joint sign conventions | Tested numerically on the built rig (`tests/test_pipeline.py`) |
| Sim-to-rig retarget | Measured every bake, written to `bake.json` |
| Rope preload, mass, stiffness, damping | Assumed |
| Segment mass fractions | Literature (de Leva 1996), quoted from memory, unverified |
| Joint ranges, torque caps, passive damping | Approximate / tuned by eye |
| Lever angles, check limits, intensity words (0.25 / 0.6 / 0.8 / 1.0) | First guesses, tuned against one take |
| Wrist flexion axis | Derived from each rig's palm normal, verified numerically |
| Strike impulse, tone envelopes, posturing timing | Tuned by eye; no footage validation yet |
| Pre-KO motion | Procedural keyframes with a capped, logged root assist; not real fight motion |

## Not built yet

BVH/mocap reference tracking, stagger-step controller, spring-bone hair and soft tissue,
fingers, cloth, cage arena, render-mesh penetration and framing gates, review page,
remote GPU render driver, opponent body.
