# Lever catalog: review list

Generated from `ko/beats/catalog/*.yaml` by `python -m ko.beats.catalog`. Do not edit here.

301 levers. 68 checks, 56 drives, 74 drives+checks, 1 partial, 102 planned.

- **drives+checks**: prose sets it, the sim is driven toward it, the checker measures it.
- **drives**: set and driven, not measured yet.
- **checks**: an outcome. Measured; reached by tuning strike/stance and sweeping seeds.
- **partial**: a named posture whose parts are a mix of the above.
- **planned**: recognised in prose and reported as UNVERIFIED. Needs build work (see note).

Source: **log** = from your instruction log, **bible** = Animation Bible vocabulary, **new** = proposed here. To approve, strike out or reword anything, then say which ids (or whole families) are approved; `approved: true` is then set in the YAML.

## Head, neck, face

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `neck.chin_tuck` | Chin tucks toward chest (as if looking at her knees) | chin tuck; chin down; chin to chest; looking at her knees | drives+checks | log |  |
|   | `neck.chin_up` | Chin tilts up / head thrown back | chin tilt up; chin up; chin lift; head tilt back | drives+checks | log |  |
|   | `neck.turn` | Head turned to one side (L/R) | head turn; face turn; head rotated; looking over shoulder | drives+checks | new |  |
|   | `neck.tilt` | Head tilted ear-to-shoulder (L/R) | head tilt to; ear to shoulder; head cocked; head lolls to | drives+checks | new |  |
|   | `neck.rigid` | Neck held rigid in line with the trunk | neck rigid; neck stiff; neck locked; head held rigid | drives+checks | bible |  |
|   | `neck.limp` | Neck limp, head lolls with gravity | neck limp; head lolls; head flops; head rolls loosely | drives+checks | bible |  |
|   | `neck.head_off_mat` | Head held up off the canvas while on her back | head off the mat; head held off; head raised off; head hovers | drives+checks | new |  |
|   | `neck.whip` | Head whips (snaps over then is thrown the other way) in the fall | head whip; whiplash; neck whip; head snaps back and forth | checks | log |  |
|   | `neck.snap_to_side` | Head snaps to the side from the strike | head snap to the side; head snaps sideways; head jerks to the side; head spun | checks | log |  |
|   | `neck.snap_back_neutral` | Head snaps back to where it was after a strike (sells the stiffness) | snap back to neutral; head snaps back; resets to the same position; reset close to the same position | drives+checks | log |  |
|   | `neck.slow_roll` | Head slowly rolls to one side as tone fades (L/R) | head slowly roll; head drifts to; head settles to the side | planned | new |  |
|   | `neck.nod_bob` | Head bobs/nods rhythmically (not tremor; slow 1-3 Hz) | head bob; head nodding; head rocking | checks | new |  |
|   | `eyes.gaze_up_corner` | Gaze up and toward the upper corner, her frame (house default: 30% of pupil showing) (L/R) | gaze up corner; eyes up and to the; looking up and to the; upper corner | drives | log |  |
|   | `eyes.rolled_up` | Eyes rolled straight up (bottom third of iris showing) | eyes rolled up; eyes roll back; eyes rolled back; bottom third | drives | log |  |
|   | `eyes.pupil_visible` | Fraction of pupil/iris left visible (0.3 = house rule) | pupil visible; of the pupil; of pupils visible; can't see pupils | planned | log | measured from an ID pass once the render gate exists |
|   | `eyes.vacant_forward` | Vacant stare straight ahead (flash KO | vacant stare; blank stare; thousand yard; staring through | drives | bible |  |
|   | `eyes.divergent` | Eyes drift apart (each eye slightly off-axis) | eyes diverge; eyes drift apart; wall-eyed; unfocused eyes | planned | new |  |
|   | `eyes.drift` | Slow wandering gaze (nystagmus-like slow drift and reset) | eyes drift; eyes wander; gaze wanders; eyes flick | planned | new |  |
|   | `eyes.lids_half` | Eyelids half closed / heavy | half closed; heavy lids; lids droop; eyes half open | planned | new |  |
|   | `eyes.lids_wide` | Eyes wide open | eyes wide; wide eyed; eyes fixed open; eyes stuck open | planned | new |  |
|   | `eyes.lids_flutter` | Eyelids flutter | eyelids flutter; lids flutter; eyes flutter; blinking rapidly | planned | new |  |
|   | `eyes.closed` | Eyes closed (overrides house rule of eyes open) | eyes closed; eyes shut | planned | new |  |
|   | `eyes.asym_lids` | One lid lower than the other (L/R) | one eye half closed; one lid lower; uneven eyelids; one eye more open | planned | new |  |
|   | `eyes.color` | Eye colour more distinct and saturated (asset note) | eyes more distinct; saturated color; eye color | planned | log |  |
|   | `face.jaw_slack` | Jaw slack | jaw slack; mouth hangs open; mouth agape; slack jaw | planned | bible |  |
|   | `face.teeth_clenched` | Teeth clenched | teeth clenched; jaw clenched; clenching; gritted teeth | planned | log |  |
|   | `face.mouthguard` | Mouthguard visible (asset) | mouthguard; mouth guard; gum shield | planned | log |  |
|   | `face.mouthguard_out` | Mouthguard half out / hanging from the lips | mouthguard hanging; mouthguard half out; mouthguard pops out; mouthguard flies | planned | new |  |
|   | `face.frown` | Mouth corners down (no default smirk) | frown; mouth corners down; sad mouth; no smirk | planned | log |  |
|   | `face.lips_parted` | Lips parted | lips parted; lips apart | planned | new |  |
|   | `face.lips_pursed` | Lips pressed/pursed with the tonic phase | lips pursed; lips pressed; lips tight; grimace | planned | new |  |
|   | `face.cheek_puff` | Cheeks puff with each breath out | cheek puff; cheeks puff; puffing cheeks; blowing | planned | new |  |
|   | `face.jaw_shift` | Jaw pushed sideways at the strike then returns (L/R) | jaw shifts; jaw pushed sideways; jaw slides | planned | new |  |
|   | `face.brow_raised` | Brows raised (surprised blankness) | brows raised; eyebrows up; brow lifts | planned | new |  |
|   | `face.brow_furrow` | Brows knit with the tonic phase | brow furrow; brows knit; brows pinch; scowl | planned | new |  |
|   | `face.blank` | Face fully blank and relaxed (no expression keys) | face blank; expressionless; face relaxed; no expression | planned | bible |  |
|   | `face.stylized_default` | House face: jaw slack, slight frown, gaze up-corner, eyes open | stylize facial expression; stylized face; facial expression as per; house face | partial | log |  |
|   | `face.cheek_on_canvas` | Cheek pressed/slides on the canvas (prone finish) | face slides along the ground; cheek on the canvas; face pressed into the mat; face on the mat | checks | log |  |
|   | `face.breath_mouth` | Mouth opens and closes slightly with each breath | mouth breathing; breathing through mouth; gasping | planned | new |  |

## Shoulders, arms, wrists, hands

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `shoulder.roll_forward` | Shoulders roll / hunch forward (L/R) | shoulders roll forward; shoulders hunched forward; shoulders rolling forward; shoulders round | drives+checks | log | no clavicle joint yet: approximated by internal rotation + upper-back flexion |
|   | `shoulder.shrug` | Shoulders shrug up toward the ears (L/R) | shoulders shrug; shrugging; shoulders up to ears; shoulders lift | planned | log | needs clavicle joint |
|   | `shoulder.raise_arm` | Upper arm lifted away from the body (elevation) (L/R) | arm raised; arm lifts; arm up; arm rises | drives+checks | log |  |
|   | `shoulder.arm_overhead` | Arm up over the head (L/R) | arm overhead; arm above head; arm over her head; hand above head | drives+checks | new |  |
|   | `shoulder.arm_at_side` | Arm lies down along the body (L/R) | arm at her side; arm by her side; arm down along the body; arm flat at side | drives+checks | new |  |
|   | `shoulder.reach_forward` | Arm reaches forward (in front of her chest, her frame) (L/R) | arm reach forward; arms extend forward; arm forward; reaching out | drives+checks | log |  |
|   | `shoulder.reach_across` | Arm reaches up and across the body to the other side (L/R) | reaching up and to the; arm across the body; reach across; arm crosses chest | drives+checks | log |  |
|   | `shoulder.arm_back` | Arm trails behind the body (extension) (L/R) | arm behind her; arm trails behind; arm swept back; arm pinned under | drives+checks | new |  |
|   | `shoulder.rotate_in` | Upper arm rotates inward (forearm across belly) (L/R) | arm rotates inward; internal rotation; forearm across belly; forearm across stomach | drives+checks | new |  |
|   | `shoulder.rotate_out` | Upper arm rotates outward (forearm falls open) (L/R) | arm rotates outward; external rotation; forearm falls open; arm flops open | drives+checks | new |  |
|   | `shoulder.slow_rise` | Arm slowly rises as the posture peaks (L/R) | arm slowly rise; arm slowly lifts; arm floats up; arm drifts up | checks | log |  |
|   | `elbow.extend` | Elbow straightens (L/R) | elbow extend; arm extend; arm straighten; elbow straighten | drives+checks | log |  |
|   | `elbow.lock` | Elbow locked dead straight (full extension) (L/R) | elbow locked; arm lock out; arms lock out; locked straight | drives+checks | log |  |
|   | `elbow.flex` | Elbow bends / arm contracts toward the chest (L/R) | arm contract; elbow flex; elbow bend; arm curls | drives+checks | log |  |
|   | `elbow.extend_more_each_strike` | Arms straighten a little further with every follow-up strike (L/R) | straighten further each; further with each impact; straighten out a little further; straightening further each time | checks | log |  |
|   | `arms.fencing` | Fencing posture: one arm extended, the other contracted (side = the extended arm) (L/R) | fencing; one arm extend the other contract; one arm extended the other; asymmetric tonic | drives+checks | log |  |
|   | `arms.both_extended` | Both arms extended stiff ("superman" / reaching) | both arms extended; both arms straight; both arms lock; arms straight out | drives+checks | log |  |
|   | `arms.both_flexed` | Both arms drawn up to the chest (flexor posture) | both arms flexed; arms curl to chest; arms drawn up to chest; both arms contract | drives+checks | bible |  |
|   | `arms.scissor` | Arms locked out and crossed over each other | scissor arms; arms scissor; scissor them; arms cross over | drives+checks | log |  |
|   | `arms.loose_guard` | Guard sags but hands stay up (loose guard) | loose guard; guard drops slightly; guard drop; guard sags | drives+checks | log |  |
|   | `arms.guard_frozen` | Guard frozen in place (hands stay exactly where they were) | guard frozen; hands stay up; guard stays up; arms frozen in guard | drives | bible |  |
|   | `arms.drop_limp` | Arms drop limp to the sides | arms drop; arms go limp; arms fall to her sides; arms hang | drives+checks | bible |  |
|   | `arms.starfish` | Arms flung wide (spread-eagle) | arms flung wide; arms spread; spread eagle; starfish | drives+checks | new |  |
|   | `arms.goalpost` | Arms up, elbows bent 90 degrees ("goalpost" on the canvas) | goalpost; arms up elbows bent; hands by her head; cactus arms | drives+checks | new |  |
|   | `arms.t_rex` | Elbows pinned to ribs | t-rex; elbows pinned; elbows tucked to ribs; forearms up wrists limp | drives+checks | new |  |
|   | `arms.one_reaching_up` | One arm reaching straight up off the canvas (stuck in the air) (L/R) | arm reaching up; arm stuck in the air; arm pointing at the ceiling; arm straight up | drives+checks | log |  |
|   | `arms.not_propping` | Arm must not hold her body up (flattens as tone fades) (L/R) | not keeping her up; holding up her body with her arm; let it flatten; not propping | checks | log |  |
|   | `arms.pinned_under` | Arm trapped under her body (L/R) | arm trapped under; arm under her body; arm pinned beneath; lying on her arm | checks | new |  |
|   | `arms.draped_on_rope` | Arm(s) draped over a rope (L/R) | arm draped over the rope; arms over the ropes; arm hooked on the rope; arms hang over | checks | log |  |
|   | `wrist.flex` | Wrist bends down toward the palm (L/R) | wrists bend down; wrist flex; wrists curl; wrist drop | drives+checks | log |  |
|   | `wrist.extend` | Wrist cocked back (L/R) | wrist cocked back; wrist extend; wrists bent back; hands bent back | drives+checks | new |  |
|   | `wrist.pronate` | Forearm/hand turns palm-down and inward (L/R) | pronate; palms turn down; hands rotate inward; wrists rotate in | drives+checks | new |  |
|   | `wrist.supinate` | Hand turns palm-up (L/R) | supinate; palms up; palm turns up; hands rotate outward | drives+checks | new |  |
|   | `wrist.limp` | Wrists limp, hands hang (L/R) | wrists limp; limp wrists; hands flop | planned | new | per-joint tone not available yet (tone is per region) |
|   | `hand.fist` | Hands clenched into fists (L/R) | fists; fist clenched; hands clench; clenched hands | planned | log |  |
|   | `hand.half_fist` | Hands halfway between open and fist (L/R) | halfway between fists; half fist; half closed hand; loosely curled fingers | planned | log |  |
|   | `hand.open_relaxed` | Hands open, fingers softly curved (L/R) | hands open; hands relaxed; open hand; fingers relaxed | planned | new |  |
|   | `hand.fingers_splayed` | Fingers splayed stiff and wide (L/R) | fingers splay; fingers spread; fingers fan; fingers stiff | planned | new |  |
|   | `hand.claw` | Fingers clawed (knuckles straight, tips curled) (L/R) | claw; clawed fingers; fingers hooked; fingers clawing | planned | new |  |
|   | `hand.thumb_in` | Thumb tucked across the palm (L/R) | thumb tucked; thumb in; thumb across palm | planned | new |  |
|   | `hand.finger_twitch` | Fingers twitch individually (L/R) | fingers twitch; finger twitching; fingers flutter; fingers quiver | planned | new |  |
|   | `hand.grasping` | Hand slowly opens and closes (grasping at nothing) (L/R) | grasping; hand opens and closes; pawing; clutching at air | planned | new |  |
|   | `hand.no_clip` | Hands must not pass through face | hand clipping; fix hand clipping; hands clip; no clipping | checks | log | body-level proxy; mesh-level test is the render-mesh gate |

## Trunk, core, hips, legs, feet

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `trunk.slump_forward` | Trunk slumps forward (spine and chest flex) | slump forward; slumps forward; body slumps; hunched forward | drives+checks | log |  |
|   | `trunk.hip_hinge` | Folds at the hips (trunk stays straighter than a slump) (L/R) | hinge at the hips; hip hinge; folds at the waist; bends at the hips | drives+checks | log |  |
|   | `trunk.back_arch` | Back arches (extension) | back arch; arches her back; spine arches; back bows | drives+checks | log |  |
|   | `trunk.back_curl` | Back curls forward (flexion) instead of arching | back curl; core crunch; crunching; curls up | drives+checks | log |  |
|   | `trunk.upper_back_hunch` | Upper back hunches up off the canvas | upper back hunch; hunch her upper back; upper back off the mat; hunching off canvas | drives+checks | log |  |
|   | `trunk.rigid_plank` | Trunk rigid as a board | rigid trunk; stiff as a board; plank; body rigid | drives+checks | bible |  |
|   | `trunk.limp` | Trunk goes soft and folds with gravity (melt) | trunk limp; body melts; melts; crumples | drives+checks | bible |  |
|   | `trunk.side_bend` | Trunk bends sideways (L/R) | side bend; bends sideways; leans to her; torso tilts | drives+checks | new |  |
|   | `trunk.twist` | Trunk twists (shoulders turned relative to hips) (L/R) | torso twist; trunk twists; shoulders turned; upper body rotates | drives+checks | new |  |
|   | `trunk.whip_into_canvas` | Sits down first then the upper body whips into the canvas | whips into the canvas; upper half whip; whips her back; like a whip | checks | log |  |
|   | `trunk.breathing` | Unconscious breathing visible (chest heaves) | breathing; heaving chest; heavy breathing; heaving breathing | drives+checks | log |  |
|   | `trunk.breath_crunch` | Core crunches and relaxes with each breath | crunching and relaxing; core crunching and relaxing; crunch with each breath; belly breathing | drives+checks | log |  |
|   | `trunk.breath_shoulders_still` | Shoulders must not pump with the breath | shoulders moving weird with breath; shoulders pump; shoulders move with breath | checks | log |  |
|   | `trunk.snore_hold` | Breath pauses then resumes (long hold, big breath) | breath hold; breath catches; breath pauses; gasps then | drives | new |  |
|   | `hips.thrust_up` | Hips lift off the canvas (bridge) (L/R) | hips lift; hips thrust; hips rise off; bridge up | drives+checks | new |  |
|   | `hips.flat` | Both sides of the back of the hips on the canvas | both sides of the back of her hips; hips touching the mat; hips flat; hips down | checks | log |  |
|   | `hips.rotated` | Hips rolled to one side while shoulders stay flat (L/R) | hips rolled to; hips twisted; pelvis turned; lower body twisted | checks | new |  |
|   | `legs.extend_stiff` | Legs straighten and stiffen (extensor posture) (L/R) | legs stiffen; legs straight; legs lock; stiff legs | drives+checks | log |  |
|   | `legs.knee_bend` | Knee bends (L/R) | knee bend; knee bent; knee flex; leg bends | drives+checks | new |  |
|   | `legs.knee_up` | Knee drawn up toward the chest (L/R) | knee drawn up; knee to chest; leg drawn up; knee pulls up | drives+checks | new |  |
|   | `legs.buckle` | Knees buckle (legs give way under her) (L/R) | knees buckle; legs give out; legs give way; legs fold under | drives+checks | bible |  |
|   | `legs.scissor` | Legs scissor: one hip flexes while the other extends, legs drawn together (L/R) | scissor legs; legs scissor; scissoring; legs start to scissor | drives+checks | log |  |
|   | `legs.scissor_flutter` | Scissoring builds to a brief flutter at impact | flutter; legs flutter; slight flutter; fluttering kick | drives+checks | log |  |
|   | `legs.ankles_cross` | Ankles cross (L/R) | ankles cross; crossing ankles; ankles start to cross; crossed ankles | drives+checks | log |  |
|   | `legs.spread` | Legs fall apart / splayed wide (L/R) | legs splay; legs spread; legs fall open; legs apart | drives+checks | new |  |
|   | `legs.frog` | Knees out, feet together ("frog" / butterfly) (L/R) | frog legs; butterfly legs; knees fall outward; knees flop open | drives+checks | new |  |
|   | `legs.figure_four` | One leg bent with its foot by the other knee (figure four) (L/R) | figure four; figure 4; one leg bent across; foot by the other knee | drives+checks | new |  |
|   | `legs.folded_under` | Leg(s) folded underneath her (knee bent, heel by the hip) (L/R) | leg folded under; legs folded underneath; sitting on her heels; leg trapped under | drives+checks | new |  |
|   | `legs.raise` | Legs lift off the canvas (L/R) | legs lift; legs raise; legs elevate; leg elevation | drives+checks | log |  |
|   | `legs.stay_down` | Feet stay near the canvas (no leg lift) | legs stay down; reduce leg elevation; legs low; feet stay on the mat | checks | log |  |
|   | `legs.jolt` | Legs jolt at a strike | legs jolt; legs kick out; legs jump; legs jerk | checks | log |  |
|   | `legs.rotate_out` | Leg rolls outward (toes point away) (L/R) | leg rolls outward; feet turn out; toes point outward; legs externally rotated | drives+checks | new |  |
|   | `legs.rotate_in` | Leg rolls inward (pigeon-toed) (L/R) | leg rolls inward; feet turn in; pigeon toed; toes point inward | drives+checks | new |  |
|   | `legs.one_straight_one_bent` | One leg stiff straight, the other bent (side = straight leg) (L/R) | one leg straight one bent; one leg stiff the other bent; one knee bent the other straight | drives+checks | new |  |
|   | `legs.stanky` | Standing wobble: knees dip and catch, feet stutter ("chicken dance") | stanky leg; chicken dance; wobbly legs; legs wobble | planned | new | needs the stagger-step controller |
|   | `legs.pedal` | Slow alternating leg movement on the canvas (pedalling) | pedalling; legs pedal; bicycle; legs slowly kick | drives+checks | new |  |
|   | `feet.point` | Feet point (plantarflex) (L/R) | feet point; toes point; pointed feet; pointed toes | drives+checks | bible |  |
|   | `feet.flex_up` | Feet pulled up toward the shins (L/R) | feet flex up; feet pulled up; dorsiflex; toes pulled back toward shin | drives+checks | new |  |
|   | `feet.invert` | Soles turn inward (L/R) | feet turn inward; soles inward; feet invert; sickled feet | drives+checks | new |  |
|   | `feet.evert` | Soles turn outward (L/R) | soles outward; feet evert; feet roll out | drives+checks | new |  |
|   | `toes.curl` | Toes curl under (L/R) | toes curl; curling toes; curled toes; toe curl | drives | log |  |
|   | `toes.splay` | Toes fan out and extend upward (L/R) | toes splay; toes fan; toes spread; toes extend | drives | new |  |
|   | `toes.twitch` | Toes twitch (L/R) | toes twitch; toes wiggle; toes flutter | drives | new |  |
|   | `feet.heels_drum` | Heels drum lightly on the canvas | heels drum; heels tap; feet drum; feet tapping | drives+checks | new |  |
|   | `feet.stay_planted` | Feet stay planted while the body goes over them (timber) | feet stay planted; feet planted; pivots over her heels; falls over her feet | checks | bible |  |
|   | `feet.step_back` | Takes a staggering step back before going down | step back; stumbles back; staggers back; backpedals | checks | new | needs the stagger-step controller to drive |

## Fall mechanics, ground contact, final position, whole-body dynamics

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `tier.flash` | Flash KO: brief shutdown, mild posturing, quick fade | flash ko; flash knockout; lights flicker; brief ko | drives | bible |  |
|   | `tier.stiff` | Stiff KO: whole body rigid, long hold | stiff ko; goes stiff; stiffens; stiffen | drives | bible |  |
|   | `tier.melt` | Melt / deep KO: tone drops out, body pours down | melt ko; deep ko; goes limp; limp ko | drives | bible |  |
|   | `tone.intensify` | Posture intensity steps up (tone rises above the previous beat) | intensifies; intensify; escalat; increases tonic | drives+checks | log |  |
|   | `tone.max` | Posture at maximum intensity | max level; maximum intensity; to max; max tonic | drives+checks | log |  |
|   | `tone.mild` | Mild posture only (low tone | mild tonic; mild posture; subtle posture; slight tonic | drives+checks | log |  |
|   | `tone.no_step` | This event must NOT raise the intensity (jolt only) | doesn't increase the tonic; does not increase; without intensifying; no escalation | checks | log |  |
|   | `tone.ramp_hold_fade` | Posture ramps to a set level, holds, fades: no sporadic jerks | progress to determined intensity; ramp hold fade; no sporadic; not sporadic | checks | log |  |
|   | `tone.fade_fast` | Posture fades faster | fades faster; fade faster; relaxes quickly; quick fade | drives | log |  |
|   | `tone.fade_slow` | Posture holds long, fades slowly | fades slowly; long hold; holds for a long time; slow fade | drives | log |  |
|   | `tone.relaxes_by_end` | Tonic state has relaxed before the take ends | until the tonic state relaxes; tonic fades; relaxes by the end; goes slack at the end | checks | log |  |
|   | `tone.asym_side` | One side of the body tighter than the other (L/R) | one side stiff; one side tighter; half her body; left side stiff | planned | new |  |
|   | `tone.upper_only` | Upper body postures, legs stay slack | upper body only; only her arms; legs stay limp; legs slack | planned | new |  |
|   | `tone.lower_only` | Legs posture, arms stay slack | lower body only; only her legs; arms stay limp; arms slack | planned | new |  |
|   | `tone.wave` | Stiffening travels through the body (e.g. legs first then arms) | travels up her body; wave of stiffness; starts in her legs; spreads to her arms | planned | new |  |
|   | `dyn.tremor` | Fine tremor / quiver through the body | tremor; tremors; quiver; quivering | drives+checks | log |  |
|   | `dyn.tremor_upper` | Tremor in the upper body (arms | upper body tremor; arms tremble; arms quiver; arms shake | drives+checks | log |  |
|   | `dyn.tremor_legs` | Tremor in the legs | legs tremble; legs quiver; legs shake; leg tremor | drives+checks | new |  |
|   | `dyn.tremor_grows` | Quivering grows as the hold tires | more quivering as the hold tires; quivering grows; tremor builds; shaking builds | drives | log |  |
|   | `dyn.no_tremor` | No tremor (smooth hold) | no tremor; without tremor; no shaking; perfectly still | checks | new |  |
|   | `dyn.jolt_all` | Jolt through limbs and head at the strike/impact | jolt; jolts; body jolts; jolt through | checks | log |  |
|   | `dyn.jolt_changes_pose` | Jolt strong enough to change the posture into a similar but different one | changing the tonic posture; similar but different; shifts into a different posture; posture changes on the jolt | planned | log |  |
|   | `dyn.twitch` | Isolated twitches of single limbs (late agonal layer) | twitch; twitches; twitching; spasm | planned | bible | conflicts with tone.ramp_hold_fade by design; ask which the owner wants |
|   | `dyn.settle` | Body visibly settles (small sag as everything lets go) | settles; settling; sags into the canvas; lets go | checks | bible |  |
|   | `fall.backward` | Falls backward | falls back; fall back; teeter back; teeters backward | checks | log |  |
|   | `fall.forward` | Falls forward | fall forward; falls forward; teeter forward; teeters forward | checks | log |  |
|   | `fall.sideways` | Falls to her side (L/R) | falls sideways; falls to her left; falls to her right; topples sideways | checks | new |  |
|   | `fall.straight_down` | Drops straight down in place | drops straight down; collapses in place; falls in place; crumples straight down | checks | bible |  |
|   | `fall.timber` | Timber: rigid topple with straight hips and knees | timber; like a tree; statue topple; falls like a plank | checks | bible |  |
|   | `fall.teeter` | Teeter: hangs at the balance point before going over | teeter; teeters; wavers; sways before | checks | log |  |
|   | `fall.delayed` | Delayed drop: stays up a beat, then goes | delayed; delayed reaction; a beat later; then drops | checks | new |  |
|   | `fall.instant` | Drops immediately | drops instantly; instantly; immediately drops; goes down at once | checks | new |  |
|   | `fall.sit_then_back` | Lands on her seat first then rolls back (glutes before head) | falls back on to her ass; sits down then; lands on her butt; glutes first | checks | log |  |
|   | `fall.knees_first` | Drops to her knees first | drops to her knees; knees first; falls to her knees; kneels then | checks | new |  |
|   | `fall.hands_no_catch` | Hands do NOT break the fall (no protective reaction) | no attempt to break; doesn't catch herself; hands don't break the fall; no brace | checks | bible |  |
|   | `fall.spin` | Body spins about vertical as it falls (L/R) | spins as she falls; corkscrews down; twists as she falls; pirouette | checks | new |  |
|   | `fall.no_spin` | Little or no spin on the canvas | reduce the amount she spins; no spin; less spin; doesn't spin | checks | log |  |
|   | `fall.momentum_carries` | Momentum carries through the shutdown (keeps travelling the way she was moving) | momentum carries; momentum survives; keeps moving; carried by her momentum | checks | bible |  |
|   | `fall.over_own_legs` | Folds down over her own legs (knees bend under her as she goes back) | folds over her legs; legs fold under her as she falls; sits back onto her heels; collapses over her legs | checks | new |  |
|   | `ground.head_bounce` | Head bounces off the canvas | head bounce; head bounces; head rebounds; head hits the ground | checks | log |  |
|   | `ground.single_bounce` | At most one head bounce | one bounce; single bounce; bounces once | checks | log |  |
|   | `ground.no_head_hit` | Head never hits the canvas hard | head doesn't hit; head never hits; head stays off; protects her head | checks | new |  |
|   | `ground.slide` | Slides along the canvas after landing | slides along; skids; slides across the canvas; slides back | checks | log |  |
|   | `ground.roll_to_back` | Is rolled over onto her back | rolls her on to her back; roll her on her back; turn her on her back; rolls onto her back | checks | log |  |
|   | `ground.roll_to_front` | Rolls onto her front | rolls onto her stomach; rolls onto her front; rolls face down; turns over face down | checks | new |  |
|   | `ground.subtle_roll` | The roll is subtle (low speed, organic) | subtly turn; subtle roll; more subtle; way too much momentum | checks | log |  |
|   | `ground.rest_early` | In final position with time to spare (default 3 s) | seconds of runtime left; with at least 3s; time left on the sim; settled early | checks | log |  |
|   | `rest.supine` | Finishes on her back, face up | on her back; on back; face up; supine | checks | log |  |
|   | `rest.prone` | Finishes on her stomach, face down | on her stomach; face down; prone; on her front | checks | log |  |
|   | `rest.side` | Finishes on her side (L/R) | on her side; on her left side; on her right side; side lying | checks | log |  |
|   | `rest.not_side` | Not on her side | on back not side; not on her side; not side | checks | log |  |
|   | `rest.flat` | Lies flat (chest low to the canvas) | almost flat; lies flat; flat out; flattens out | checks | log |  |
|   | `rest.seated` | Ends sitting (against ropes/cage or slumped upright) | ends sitting; sitting against; seated; slumped sitting | checks | new |  |
|   | `rest.kneeling_folded` | Ends folded over her knees (face down, hips high) | folded over her knees; kneeling face down; hips in the air; face down hips up | checks | new |  |
|   | `rest.head_turned` | Head turned to one side at rest (L/R) | head turned at rest; face to the side; cheek down; head resting to the | checks | new |  |
|   | `rest.face_visible` | Face must be visible to camera (not blocked by her own body) | face is visible; face visible; face must be visible; not blocked by body | planned | log | needs the render-side visibility gate |

## Strikes, follow-ups, pre-KO setup, ropes and arena

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `strike.hook` | Hook to the jaw (arrives from the side) (L/R) | hook; left hook; right hook; check hook | drives | log |  |
|   | `strike.cross` | Straight punch / cross (arrives from the front) | cross; straight right; straight left; straight punch | drives | new |  |
|   | `strike.overhand` | Overhand (arrives from above and the side) (L/R) | overhand; looping punch; haymaker | drives | new |  |
|   | `strike.uppercut` | Uppercut (arrives from below) | uppercut; upper cut | drives | log |  |
|   | `strike.elbow` | Elbow (short arc from the side) (L/R) | elbow strike; elbow to the; spinning elbow; an elbow | drives | log |  |
|   | `strike.head_kick` | Round head kick (shin from the side) (L/R) | head kick; high kick; roundhouse; shin to the head | drives | log |  |
|   | `strike.wheel_kick` | Wheel / spinning heel kick (heel across from the side) (L/R) | wheel kick; spinning heel kick; spinning hook kick; spinning back kick to the head | drives | log |  |
|   | `strike.front_kick` | Front kick / teep to the chin (from below-front) | front kick; teep; push kick to the face; snap kick | drives | new |  |
|   | `strike.knee` | Knee (rising, from the front) | knee to the; flying knee; knee strike; a knee | drives | new |  |
|   | `strike.backfist` | Spinning backfist (L/R) | backfist; back fist; spinning backfist | drives | new |  |
|   | `strike.body_shot` | Body shot (trunk; a fold, not a head KO) (L/R) | body shot; liver shot; body kick; shot to the body | drives | new | conscious fold: needs a guarded-collapse behaviour, not the KO tone model |
|   | `strike.slam` | Slam / throw onto the canvas | slam; slammed; suplex; thrown | planned | bible | needs an opponent body or a scripted carry |
|   | `hit.jaw_tip` | Lands on the tip of the jaw (mostly spins the head) | clips the jaw; on the chin; tip of the jaw; on the button | drives | log |  |
|   | `hit.temple` | Lands on the temple | temple; side of the head; behind the ear | drives | new |  |
|   | `hit.forehead` | Lands high on the forehead (drives the head back) | forehead; high on the head | drives | new |  |
|   | `hit.clip` | A clip, not a full connection (less momentum into the body) | clips; clip; grazes; glancing | drives | log |  |
|   | `hit.flush` | Lands flush / clean | flush; clean; lands clean; full connection | drives | new |  |
|   | `hit.walked_into` | She was moving into it (closing speed adds) | walks into; walked into; runs into; steps into the punch | drives | new |  |
|   | `hit.retreating` | She was giving ground when hit | backing up; retreating; moving backward when; gives ground | drives | log |  |
|   | `follow.punch` | Follow-up punch from above on the grounded head | followup shot; follow-up shot; follow up strike; followup strike | drives | log |  |
|   | `follow.count` | Number of follow-up strikes | single followup; one followup; two followup; multiple followup | drives | log |  |
|   | `follow.delay` | Follow-up lands this long after she hits the canvas (house: 1 s) | 1s after she's hit the ground; a second after; right after she lands; seconds after she hits | drives | log |  |
|   | `follow.harder` | Follow-up hits harder and more pronounced | hit harder; harder and more pronounced; heavier shot; bigger shot | drives | log |  |
|   | `follow.drives_head_to_mat` | Shot snaps her head further toward the mat | snaps her head further towards the mat; drives her head into the mat; head pinned to the mat | checks | log |  |
|   | `follow.head_snaps_side` | Head snaps to the side from the punch and returns | head snapping to the side and back; head snaps to the side and back to neutral | checks | log |  |
|   | `follow.rolls_her` | This shot's momentum rolls her over | momentum of the follow-up rolls her; shot that turns her; shot rolls her | drives+checks | log |  |
|   | `follow.glove_visible` | A glove/fist is rendered for the strike (nothing else of the opponent) | render a glove; render the glove; glove to show; fist rendering | drives | log |  |
|   | `setup.stance_orthodox` | Orthodox stance (left foot forward) | orthodox | drives | new |  |
|   | `setup.stance_southpaw` | Southpaw stance (right foot forward) | southpaw | drives | new |  |
|   | `setup.guard_high` | High tight guard before the strike | high guard; tight guard; hands high; shelled up | drives | new |  |
|   | `setup.guard_low` | Hands low before the strike | hands low; hands down; low guard; hands by her waist | drives | new |  |
|   | `setup.mid_punch` | She is mid-punch when hit (arm extended) | mid punch; throwing a punch when; caught while punching; counter | drives | new |  |
|   | `setup.mid_kick` | She is mid-kick when hit (one leg off the canvas) | mid kick; caught while kicking; as she kicks; on one leg | drives | new | needs single-support balance |
|   | `setup.shooting` | She is shooting for a takedown (low | shooting in; shoots for a takedown; level change; diving in | drives | new |  |
|   | `setup.circling` | Circling / lateral movement when hit (L/R) | circling; moving laterally; sidestepping | drives | new |  |
|   | `setup.live_fight_stance` | Stance and distance consistent with a live fight (bladed, guard up) | realistic to the scenario of a fight; consistent with a live fight; fight stance; bladed stance | drives | log |  |
|   | `setup.already_hurt` | Already hurt: guard sagging, slow feet before the final shot | already hurt; already wobbled; on wobbly legs; rocked before | drives | new |  |
|   | `arena.rope_distance` | Distance to the ropes at the KO (m) | close to the ropes; near the ropes; against the ropes; too close to the ropes | drives | log |  |
|   | `arena.propped_on_ropes` | Body ends up propped on the ropes for a while | propped up by the ropes; propped on the ropes; held up by the ropes; hangs on the ropes | checks | log |  |
|   | `arena.splayed_over_ropes` | Splayed out over the ropes | splayed out over the ropes; draped over the ropes; hung over the ropes | checks | log |  |
|   | `arena.slides_down_ropes` | Slides slowly down the ropes to the canvas | slides down the ropes; slow slide down; sinks down the ropes | checks | log |  |
|   | `arena.bounces_off_ropes` | Bounces off the ropes back into the ring | bounces off the ropes; rebounds off the ropes; springs back off | checks | new |  |
|   | `arena.through_ropes` | Falls between/through the ropes | through the ropes; between the ropes; out of the ring | planned | new | needs apron geometry |
|   | `arena.head_on_bottom_rope` | Head/neck comes to rest on the bottom rope | head on the bottom rope; neck on the rope; head resting on the rope | checks | new |  |
|   | `arena.corner` | KO happens in a corner (turnbuckle pad behind her) | in the corner; corner post; turnbuckle | planned | new | needs corner pad geometry |
|   | `arena.cage_wall` | Cage wall behind her (slides down the fence) | cage; fence; against the cage; slides down the fence | planned | new | cage arena not built |
|   | `arena.no_ropes` | Open canvas (no ropes simulated) | open canvas; no ropes; open mat | drives | new |  |

## Camera, replays, editorial (house rules pre-applied; these are per-take adjustments)

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `cam.ref_pan` | Referee pan: sweeps across the body as if checking her over, ends on her face | ref cam; referee camera; pans across as if a referee; checking her over | planned | log |  |
|   | `cam.ref_other_side` | Referee pan from the other side of the body | ref cam from other side; from the other side of body | planned | log |  |
|   | `cam.ref_stop_after_rest` | Referee cam stops about 1 s after she reaches the final position | ref cam stops; stops 1s after reaching final position | planned | log |  |
|   | `cam.full_body` | Full-body shot (not a zoom-in) | full body shot; full body; not a zoom in; whole body in frame | planned | log |  |
|   | `cam.orbit` | Orbit around her | orbit; circles around her; orbiting; circle around | planned | log |  |
|   | `cam.orbit_late` | Replay starts orbiting partway through | start orbiting halfway; orbit around at the end; orbiting halfway through | planned | log |  |
|   | `cam.opponent_pov` | Camera from where the opponent stood | where the opponent stood; opponent pov; opponent's point of view; from the opponent | planned | log |  |
|   | `cam.underground` | Underground angle (below the canvas, looking up; shows curled toes) | underground; below canvas; from under the mat; underground view | planned | log |  |
|   | `cam.underground_full` | Underground angle zoomed out to full body | underground angle zoomed out; underground full body | planned | log |  |
|   | `cam.underground_front` | Underground angle facing her front-on | opposing her front on but from underground; underground front on | planned | log |  |
|   | `cam.face_zoom` | Zoom into her face (never the back of the head) | zooms into face; zoom on her face; close on the face; face close-up | planned | log |  |
|   | `cam.zoom_out_end` | Zoom out at the end of the final replay | zoom out at the end; zooms out more by the end; add a zoom out; zoom out during | planned | log |  |
|   | `cam.pan_toe_to_head` | Pan from toes to head (or head-toe-head) | pan from toe to head; toe to head; head to toe; pan up to face | planned | log |  |
|   | `cam.pan_starts_at` | Pan toward the head begins after a fraction of the replay | start panning after; after 40% of the replay | planned | log |  |
|   | `cam.track_same_view` | Keep tracking her from the same perspective until the end | track from the same perspective; extend this replay until the end; same perspective | planned | log |  |
|   | `cam.replay_longer` | Replay runs longer (percent or "until the tonic state relaxes") | replay longer; lasts longer; longer by; increase the length of | planned | log |  |
|   | `cam.replay_until_relaxed` | Replay lasts until the tonic state has relaxed | last until the tonic state relaxes; until she relaxes | planned | log |  |
|   | `cam.raise_for_face` | Raise/move the camera so her face is visible | raise the camera; adjust camera so the face; move the camera so | planned | log |  |
|   | `cam.low_angle` | Low angle at canvas level | low angle; canvas level; mat level; ground level shot | planned | new |  |
|   | `cam.overhead` | Overhead / top-down shot | overhead; top down; bird's eye; from above | planned | new |  |
|   | `cam.corner_cam` | Fixed corner-post camera | corner camera; corner cam; post cam | planned | new |  |
|   | `cam.broadcast` | Broadcast wide (the live angle) | broadcast angle; live angle; wide shot | planned | new |  |
|   | `cam.side_profile` | Side profile locked perpendicular to the fall line | side profile; profile shot; perpendicular to the fall | planned | new |  |
|   | `cam.feet_closeup` | Close-up of feet/toes | close-up of her feet; toes close up; feet close-up | planned | new |  |
|   | `cam.hands_closeup` | Close-up of hands | close-up of her hands; hands close up | planned | new |  |
|   | `cam.impact_angle` | Replay angle chosen to show the strike landing | show the strike landing; angle on the impact; see the punch land | planned | new |  |
|   | `look.outfit` | Outfit selection (asset) | outfit; royal blue set; change her outfit; wearing | planned | log |  |
|   | `look.eye_refraction` | Eye material check (refraction artefacts) | eyes are refracting weird; eye refraction; eyes look wrong | planned | log |  |
|   | `look.no_clipping` | No clipping anywhere (face, eyes, shoulders, hands) | no clipping; fix clipping; face clipping; shoulder clipping | planned | log | needs the render-mesh penetration gate |

## Proposed new families (brainstormed; none requested yet, all need owner approval)

| OK | id | What it is | Phrases that trigger it | Status | Src | Note |
| --- | --- | --- | --- | --- | --- | --- |
|   | `stagger.out_on_feet` | Out on her feet: frozen upright a moment, eyes gone, before anything falls | out on her feet; frozen standing; stands frozen; standing ko | checks | new |  |
|   | `stagger.drunken_walk` | Several unsteady steps in a curve before the legs go | drunken walk; staggers across the ring; stumbles several steps; wanders | planned | new |  |
|   | `stagger.stumble_forward` | Stumbles forward chasing her own balance then pitches down | stumbles forward; lurches forward; chases her balance | planned | new |  |
|   | `stagger.backpedal` | Backpedals with heels skidding until she sits down | backpedals until; heels skid; runs backward | planned | new |  |
|   | `stagger.one_knee_dip` | One knee dips and recovers before the real collapse (L/R) | knee dips; one knee buckles then; dips and recovers; leg betrays her | planned | new |  |
|   | `stagger.tries_to_stand` | Reflex attempt to rise that fails (limbs push, body does not follow) | tries to get up; attempts to stand; tries to rise; pushes up and falls | planned | new | semi-conscious behaviour: new controller mode |
|   | `stagger.grabs_for_support` | Arm reaches for rope/opponent on the way down (L/R) | grabs for the rope; reaches for support; clutches at | planned | new | needs reach targets (IK goal) |
|   | `stagger.falls_into_ropes_twice` | Bounces off the ropes then falls the other way | off the ropes then forward; rope rebound then falls | checks | new |  |
|   | `timing.posture_latency` | Latency between strike and posture onset (0 = instant) | posture starts late; a beat before she stiffens; delay before the tonic; instant stiffening | drives | new |  |
|   | `timing.rise_snap` | Posture snaps on (fast rise) | snaps into; snaps stiff; instantly rigid; locks up at once | drives | new |  |
|   | `timing.rise_creep` | Posture creeps on slowly | slowly stiffens; creeps into; gradually stiffens; gradually | drives | new |  |
|   | `timing.second_wave` | A second wave of stiffening arrives on its own, with no new impact | second wave; stiffens again; re-stiffens; comes back in waves | planned | new | check that this is wanted: the house rule is ramp-hold-fade with no sporadic jerks |
|   | `timing.limb_order` | Order in which limbs release as tone fades (e.g. legs first, arms last) | legs relax first; arms relax last; releases from the feet up; arm stays up longest | planned | new |  |
|   | `timing.arm_lingers` | One arm stays raised long after everything else has let go (L/R) | arm stays up; arm lingers; arm still raised after; last thing to drop | planned | new |  |
|   | `reflex.arm_drop_slow` | Raised arm slowly sinks to the canvas as tone fades (L/R) | arm slowly sinks; arm slowly lowers; arm drifts down; arm falls in slow stages | checks | new |  |
|   | `reflex.arm_drop_sudden` | Raised arm drops all at once when tone lets go (L/R) | arm suddenly drops; arm flops down; arm falls all at once | drives | new |  |
|   | `reflex.leg_slow_extend` | Bent leg slowly slides out straight (L/R) | leg slowly slides out; leg slowly straightens; heel slides along the mat | checks | new |  |
|   | `reflex.head_search` | Head slowly turns side to side (unfocused searching) | head turns side to side; head rolls side to side; head searching | checks | new |  |
|   | `reflex.startle_on_touch` | Whole-body startle (arms fling out) at an impact | startle; arms fling out; flinch at impact; moro | planned | new |  |
|   | `reflex.guarding_hands` | Hands drift toward the face as if guarding, with no coordination | hands drift to her face; hands come up uncoordinated; guarding reflex; covers up weakly | planned | new |  |
|   | `reflex.sit_up_curl` | Trunk curls up off the canvas briefly as if sitting up, then drops | sits up briefly; curls up then drops; half sits up; crunches up off the mat then falls | checks | new |  |
|   | `alt.choke_out` | Choke: tone drains gradually, limbs go heavy, hands slide off | choke; choked out; goes to sleep; strangle | planned | bible | Animation Bible has a choke section; needs opponent contact or a scripted hold |
|   | `alt.choke_release_drop` | Released from a hold and pours onto the canvas | released and drops; let go and she slumps; released from the choke | planned | bible |  |
|   | `alt.body_fold` | Body-shot fold: clutches, folds, takes a knee (conscious) | folds from the body shot; takes a knee; doubles over; clutches her side | planned | new |  |
|   | `alt.tko_turtle` | Covers up / turtles under strikes (conscious, stoppage) | turtles; covers up; shells up on the ground | planned | new |  |
|   | `alt.slam_ko` | Slam KO: posture begins on canvas impact, not on a strike | slam ko; knocked out by the slam; spiked | planned | bible |  |
|   | `alt.double_ko_trip` | She trips or slips into the KO (no strike momentum) | slips; trips; loses her footing | planned | new |  |
|   | `sec.hair_follow` | Hair follows through on head snaps and impacts (spring bones) | hair whips; hair follows; hair swings; hair fans out on the canvas | planned | new |  |
|   | `sec.hair_over_face` | Hair must not cover the face in replays | hair covering her face; hair out of her face | planned | new |  |
|   | `sec.soft_tissue` | Soft-tissue follow-through on impacts (jiggle layer, subtle) | jiggle; soft tissue; follow-through on impact | planned | new |  |
|   | `sec.garment_shift` | Garment shifts/wrinkles with motion (cloth layer) | cloth moves; fabric wrinkles; garment shifts | planned | new |  |
|   | `sec.canvas_dent` | Canvas visibly gives under head/hip impacts | canvas dents; mat gives; canvas ripples | planned | new |  |
|   | `sec.rope_ring` | Ropes keep ringing after contact (already simulated; expose the damping) | ropes shake; ropes ring; ropes vibrate | drives | new |  |
|   | `sec.sweat_spray` | Sweat spray at the strike (particles; within content rules) | sweat spray; sweat flies | planned | new |  |
|   | `ref.wave_off_timing` | Take ends as if at the referee wave-off (cut timing only, nobody rendered) | wave off; ref stops it; referee stops | planned | new |  |
|   | `opp.walk_off` | Walk-off KO: no follow-up strikes at all | walk off; walk-off ko; no follow up; no followup | drives | new |  |
|   | `opp.late_shot` | A late extra shot after she is clearly out | late shot; unnecessary shot; one more for good measure | drives | new |  |
|   | `vary.mirror` | Mirror the whole take left/right | mirror it; mirrored; other side; flip left and right | planned | new |  |
|   | `vary.seeded_details` | Fill every unspecified lever from a seeded draw of plausible options (listed in the sheet for approval) | surprise me; vary it; something different; different from last time | planned | new |  |
|   | `vary.avoid_recent` | Avoid lever combinations used in the last N takes | don't repeat; avoid repeating; not like the previous | planned | new |  |
|   | `vary.subtle_asym` | Small left/right differences everywhere (nothing perfectly mirrored) | asymmetric; not symmetrical; break the symmetry; uneven | planned | new |  |
