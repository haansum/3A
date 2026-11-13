# Story generator handoff: short context stories for KO takes

For the model that writes the stories. Read all of it once; then follow section 2 for every story.

## 1. What this is

Each KO take can carry a short story (120 to 320 words) that explains why the fight is
personal and ends where the animation begins. The stories must not resemble each other.

Language models repeat themselves mostly in their **choices**: the same names, places,
grudges and plot shapes. So here the choices are not yours. Code draws them from a bank
(`ko/story/bank/`) with a seed and a memory of past stories, and hands you a **brief**. You
write prose to the brief. A lint then rejects text that echoes earlier stories.

Your job is the part code cannot do: make two invented people feel like they have known
each other for ten years, in under 300 words.

## 0. The default shape: finish first, talk as the payload

The generator's default output is no longer a lead-up scene. It is a three-part piece, 360
to 540 words, with parts separated by a line holding only `*`:

1. **Lead-up**: at most three sentences. Who they are to each other, the one thing that was
   done, what is at stake. Nothing else about the fight.
2. **The finish**: the knockout as the simulation shows it, described fact by fact.
3. **Aftermath and talk**: at least half the words. What the room does, then the rubbing-in.
   Three lines are chosen by code from the writer's candidates: an opener, the personal one,
   a closer.

    python -m ko.story.generate --seed 60 --count 5                 # aftermath shape (default)
    python -m ko.story.generate --seed 60 --take takes/beats/x.yaml # describe a real take's finish
    python -m ko.story.generate --seed 60 --set tone=measured --set speaker=caller
    python -m ko.story.generate --seed 60 --shape leadup            # the older scene-before-the-fight shape

The writer's instructions for this shape are `ko/story/writer_prompt_aftermath.md`. Sections
3 to 6 below describe the older `leadup` shape and its brief; the craft rules in sections 4
and 5 apply to both.

**Where the finish comes from.** With `--take`, the facts are read off that take's beat sheet
in order, so the prose describes the animation. Without it, `finish.py` draws a finish from
the lever catalog (strike, where it lands, fall, two posture facts, two effects while she is
out, how she rests, her eyes, optional follow-ups, one thing she does coming round) and also
emits `sim_prose`, a line `ko.beats.parse` can turn into a beat sheet for that finish.

**Why finishes stop repeating** (`bank/finish_prose.yaml`):

| Piece | Count | Use |
| --- | --- | --- |
| Lenses | 18 | One governs how the whole finish is told: by sound, by the clock, one body part, from the floor, as a machine losing power, as the referee sees it, and so on |
| Phase seeds | 78 | One small observation for each of six phases: arrival, contact, the instant she goes, the fall, the landing, the first still second |
| Sounds | 14 | One thing heard |
| Renderings | about 330 across 110 facts | Each fact arrives with one way a ringside viewer might see it, rotated by memory, so "arms.fencing" is not described the same way twice running |
| Banned stock phrases | 53 | Rejected in the finish by the lint: trees, sacks, rag dolls, lights, switches, naps, "crumpled", "thud", and the rest |

**Effects that sell it.** A new lever family, `ko_effects` (46 levers, in
`ko/beats/catalog/08_ko_effects.yaml` and `docs/LEVERS.md`), lists observable signs
consistent with the posturing: snoring and its late onset, one huge first breath, lips
fluttering, cheeks puffing, breath hitching, a groan, breath whistling round the mouthguard,
jaw working, lip smacking, mumbling, slow blinks, eyes open throughout, an arm that stays
raised and sinks in stages, hands pawing at air, fingers fanning or rippling, wrists curling
in, a guard that comes back up while she is out, a glove tapping the canvas, a shrug that
holds, a single shudder, knees quivering, feet paddling, toes fanning, heels digging, the
back bowing and letting go, the head lifting and dropping; and coming round: grabbing or
fighting the referee, sitting up too fast, legs not answering, the wrong corner, asking what
round it is, arguing the stoppage, keeping her guard up on the stool, wiping her mouth,
pushing help away, a confused smile, studying her gloves. They are written as observation
only. Most are prose-only for now: the sim needs the face, finger, toe and breath layers
before it can show them.

**Tone.** `tone` is drawn: underground 75%, measured 25%. Underground is the voice of an
unsanctioned, knockout-hungry circuit: young, fast, funny-cruel, sharper than a street-clip
caption and looser than a broadcast. It may clown the way she fell and the pose she is in;
then it gets personal. Three registers exist for it: `roast_the_pose`, `receipts` (phone
culture as evidence) and `house_mic` (the circuit's caller). The speaker is the winner 84%
of the time, the caller 8%, the loser's corner, the loser later, or the winner's corner the
rest.

**The talk bank.** `ko/story/examples/trash_talk.yaml` holds 385 lines across 29 registers,
tagged `when` (before / after) and `tone` (measured / underground); 349 are post-knockout,
125 underground. The generator shows the writer six per piece, matching the tone, from
registers the piece does not use. Every line in the file counts as used text.

**Details that sell the event.** Each brief draws five observed details (clock, referee,
corners, room, body) from `bank/aftermath.yaml`, plus who the talk is aimed at, what the
speaker is doing while she says it, when, and how the piece ends.

**Limits that still hold.** No blood, injury detail or medical vocabulary; no slurs; nothing
about looks, race, religion, sexuality or disability; nothing sexual; fictional adults only.
Jokes about how she fell and what her body is doing are in.

## 2. Running it

**Normal use: the generator does the whole loop.**

    python -m ko.story.generate --seed 40 --count 5                      # Claude API, needs credentials
    python -m ko.story.generate --seed 40 --take takes/beats/<take>.yaml # end where a real take begins
    python -m ko.story.generate --seed 40 --writer cmd --cmd "claude -p --model claude-opus-5-5"
    python -m ko.story.generate --seed 40 --set register=ledger --set talker_falls=true

For each seed, in order, it: draws the brief; asks the model for five candidate hardest
lines with probabilities; keeps one from the unlikely half (`choose.py`); asks for the story
built on that line; lints it; sends the failures back for a rewrite, up to three attempts;
records the accepted story in the ledger. Files land in `ko/story/out/`: `s<seed>.brief.yaml`,
`s<seed>.md` (or `.rejected.md`) and `s<seed>.log.json` with candidates, attempts and failures.

The model sees `ko/story/writer_prompt.md` as its system prompt (the craft rules of sections
3 to 5 below, without the commands). Edit that file to change how stories are written.

`--writer api` uses the Anthropic SDK (`pip install -e ".[story]"`), default model
`claude-opus-5-5`, `--model` to change it. `--writer cmd` pipes the prompt to any command
that prints a reply, so any model can be the writer; the checks are identical.

**By hand** (a model working in the repo without the generator):

    python -m ko.story.draw --seed <N> [--take ...] --out ko/story/out/s<N>.brief.yaml
    python -m ko.story.choose candidates.yaml --seed <N> --brief <brief>
    python -m ko.story.lint ko/story/out/s<N>.brief.yaml ko/story/out/s<N>.md --accept

Draw; invent the three specifics (nickname, the checkable grievance detail, what each does
with her hands); write five candidate lines with honest probabilities and let `choose` pick;
write; lint; fix what it names; accept. Never write two stories in one pass: the memory
only works one story at a time. After three failed attempts, draw a new seed.

## 3. Reading the brief

| Field | What it obliges |
| --- | --- |
| `setting.place`, `setting.detail` | The scene happens here. Use the detail once, in your own words. Do not add a second location unless `form` says two scenes. |
| `situation` | What has just happened as the scene opens. It is why they must deal with each other now. Start from it or arrive at it within two sentences. |
| `people` | Two fighters, `talker` and `target`. Use both names (a first-person narrator must be named by someone). `style` is what she would mock and be mocked for. `temperament` governs her sentences. Invent the nickname from `nickname`. |
| `relationship` | The shared history. One clause is enough to establish it. |
| `grievance` | `done_by` did it to `done_to`. The aggrieved one may be either role. The reader must be able to point at the detail that proves it happened. |
| `stakes` | Belongs to whichever fighter it hurts more. Mention once, never explain. |
| `talk.talker_register`, `talk.target_register` | HOW each of them speaks. A technique, not a vocabulary (section 5). If the place has no audience, "the room" is whoever is in earshot. |
| `arc.beats` | The order of emotional events. Hit each beat once, in order. Do not label them. |
| `moment` | When this is, relative to the fight. |
| `pov`, `form` | Binding. A transcript has no thoughts. "No quoted speech" means none. |
| `first_sentence_is` | The first sentence must be this kind of thing. |
| `ending` | The last sentence must do this. |
| `sensory_anchor` | One non-visual detail, used at most three times. |
| `result.who_falls`, `result.meaning` | Who is knocked out and what it means. The story must make this result feel earned or cruel, as `meaning` says. State or foreshadow it in at most one clause, unless `ending` puts you at the strike. |
| `result.strike`, `strike_from_her`, `fall` | Present only with `--take`. If the story reaches the strike, it must match: the side is HER side. |
| `length_words` | Within 25%. |
| `banned_here`, `do_not_open_with`, `recent_phrases_to_avoid` | Do not use them. These change every story. |

If two fields seem to conflict, the setting wins, then the form. Say what you did in a
comment line at the end of the story file starting with `<!--`.

## 4. Emotional build-up

These are craft conventions, not research findings.

- **Start below the temperature you will end at.** A scene that opens at full heat has
  nowhere to go. Most arcs in the bank begin with effortful politeness for this reason.
- **Escalate by precision, not volume.** Each exchange should be more specific than the
  last, not louder. The worst line is usually the quietest and the most exact.
- **One true thing.** The line that ends the exchange is true, known to both, and has
  never been said aloud. Find it before you write.
- **The body leaks before the mouth does.** Show the hit landing with one small involuntary
  action (a hand that stops, a chin, a swallow) and no named emotion. Never write what she
  felt.
- **Give the target a real answer.** Trash talk against a silent victim is a monologue. The
  target's register is in the brief so the exchange has two sides.
- **Let something be funny.** Real hostility between people with history contains jokes
  only they understand. One is enough.
- **Leave the fight unfought.** The story is pressure; the animation is release. Unless the
  ending says otherwise, stop before the strike.
- **The result should re-read the scene.** Whoever falls, the reader should think back to
  one line and hear it differently. Plant that line on purpose.

## 5. Trash talk

Visceral means **specific and earned**, not loud or obscene. What makes a line hurt:

1. It names a fact only someone close would have (the locker number, the sum, the song).
2. It has been kept a long time. Show the keeping: a receipt in a gear bag, a quote
   printed inside a mouthguard case.
3. It attacks what she is proud of, not what she is ashamed of.
4. It is short. The longer the line, the less the speaker believes it.
5. The speaker gives something away by saying it. The best lines cost the talker too.

The 26 registers are in `bank/voice.yaml`. Two examples each for 18 of them, tied to bank
grievances, are in `ko/story/examples/trash_talk.yaml` (36 lines). The generator shows the
writer four of these per story, always from registers that story does not use. A few:

> **ledger:** "March ninth you cleaned out locker fourteen. March thirtieth we fought for
> the belt with a kid holding the bucket. I'm not angry. I'm reading you the calendar."

> **kindness:** "Nobody will say it to you, so I will, because I like you: they book you
> because you lose well. You make people look good. That's a real skill."

> **borrowed words:** "'A good first test.' That was you, on air, last April, about me. I
> had it printed inside my mouthguard case. I read it every time I put my teeth in."

> **wounded:** "Forty names. I counted them on the replay, twice, in case I'd missed mine.
> You thanked the man who drives the ring truck."

> **whisper:** (a handshake for the cameras; under it, lips barely moving) "I kept your
> gloves because they fit me better."

**The examples teach technique. Do not reuse a line, a sentence shape, or an object from
them.** The lint treats the examples as already-used text.

**The line you may not cross.** Fictional adults only, no real people. No slurs. Nothing
about race, religion, sexuality, disability or body. No sexual content or sexual
humiliation. No threats outside the sport (fighters may promise to win, not to harm).
No blood, injury detail or medical talk (owner's standing rule, enforced by the lint).
Cruelty about choices and history is the whole palette; it is enough.

## 6. Three worked examples

Hand-written (`s00011` to `s00013`) and generated (`s00040`, `s00041`, written by `claude-opus-5-5` through the generator), in `ko/story/out/`, each with its brief. Read the brief beside the story.

| Story | Shows |
| --- | --- |
| `s00011` | 132 words. Comedian against wounded; the mask-slip arc; told by a teammate holding a lucky coin; ends on the object. The cruel one wins and the narrator sides with the loser anyway. |
| `s00012` | 220 words. No quoted speech at all; a cornerman who trained both; the shared-laugh arc; cut on the bell. The talker jokes about her own offence. |
| `s00013` | 270 words, tied to the wheel-kick take. First person from the fighter who will fall; two scenes with a hard cut; the strike arrives from her right as the take specifies; the last line is a sound. |

They differ in person, tense, form, length and who the reader sides with because their
briefs differ. That is the mechanism working, not a style to copy.

## 7. What stops repetition

| Layer | Mechanism | Where |
| --- | --- | --- |
| Choices | 14 independent axes drawn by seed: 89 settings, 55 situations, 44 relationships, 69 grievances, 32 stakes, 26 registers, 22 arcs, 15 points of view, 16 forms, 12 openings, 15 endings, 30 anchors | `draw.py`, `bank/` |
| Memory | Values from the last 3 stories excluded, last 12 down-weighted; names retired 40 stories | `ledger.jsonl` |
| Coherence | Every setting has a phase (weeks before, fight week, fight night); moment, situation and who can be watching follow from it; clashing pairs are excluded | `NIGHT`, `WEEK`, `EARLY`, `OFFICIAL_OK`, `NO_CAMERA`, `CLASH` in `draw.py` |
| Wording | 46 always-banned stock phrases; 6 ordinary words banned per brief at random; recent openings and phrases banned | `bank/bans.yaml` |
| Key lines | Five candidates with probabilities; code picks from the unlikely half | `choose.py` |
| Rejection | At most 8% of a story's three-word phrases may already exist in past stories or the examples | `lint.py` |
| Names | Hand-picked pool; names that models default to are rejected | `bank/people.yaml`, `lint.py` |

Measured on 100 briefs drawn in sequence (`python -m ko.story.measure 100`): with memory on,
nothing recurs within 4 stories on any axis (without memory: back-to-back repeats on most
axes); 59 of 89 settings and 61 of 69 grievances get used; no register + arc + point-of-view
combination repeats; 1 setting + grievance pair repeats. Prose-level repetition has only
been measured on five stories (0% shared three-word phrases), which is too few to conclude from.

## 8. Extending the bank

Add entries to the YAML files; no code changes. Rules: a setting needs one detail only
that place has; a grievance must be something a person could prove; a register is a way
of speaking, never a list of insults; test a new register by writing two lines for
`examples/trash_talk.yaml`. Every new setting must be placed in `draw.py`: `NIGHT` or `WEEK` with its moment, or `EARLY`;
plus `NO_CAMERA` if nobody is filming and `OFFICIAL_OK` if officials are present. A new
situation needs a `phase` list. `tests/test_story.py` fails if a rule names a setting that
does not exist.

## 9. Known limits

- The lint checks surface text. It cannot tell whether a story is good, whether the arc
  beats were hit, or whether the result feels earned. The owner judges that.
- The candidate step relies on the writer's own probability estimates, which are rough.
- With 90 given and 80 family names, names start to recur after about 40 stories.
- The generator has been run for two stories only. Its accept rate, cost per story and the
  quality of its output over a long run are unmeasured.
- Some drawn combinations are strained (a comedian register with nobody watching). The writer
  is told to treat that as the assignment; whether that yields good stories is the owner's call.
- The echo limit (8%) and the windows (3, 12, 18) are first guesses.
- Sources for the approach are listed in the main handoff doc; they were read as search
  summaries only.
