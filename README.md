# Fight Sim

A mobile fight-simulation app: build fighter profiles, run realistic simulated
fights with round-by-round play-by-play, and crown champions in single-elimination
tournaments. Built with [Expo](https://expo.dev) / React Native — everything runs
on-device with no backend.

## Running the app

```bash
npm install
npm start          # then scan the QR code with Expo Go (iOS/Android)
npm run web        # or run in a browser
```

## What's inside

### Fighters
Create and edit fighters on the fly: 11 attributes (striking, power, speed, chin,
cardio, wrestling, submissions, grappling defense, fight IQ, aggression, heart)
plus a fighting style (pressure striker, counter striker, wrestler, submission
artist, brawler, all-rounder). Styles interact non-transitively — styles make
fights — so a stat-inferior fighter can be a nightmare matchup.

### The simulation engine (`src/engine/`)
Pure TypeScript, no React dependencies. Each 5-minute round is simulated as a
sequence of exchanges across three phases (standing / clinch / ground):

- fighters choose actions from style-driven intent profiles
- rolls resolve against effective attributes, degraded by **stamina** and
  **accumulated damage** (heart resists it, cardio controls the fade)
- knockdowns, flash KOs, ref stoppages, submissions, and judges' scorecards
  (with split/majority decisions) all emerge from the exchange loop
- underdogs keep a genuine puncher's chance — including the intercepting
  counter against a takedown entry

Every fight runs from a **seed**: the same seed replays the identical fight,
commentary and all.

### Scene descriptions for animation
Key moments (knockdowns, big strikes, takedowns, submissions, sweeps, finishes)
carry a structured `scene` payload alongside the commentary text, written for
animators/renderers:

```ts
scene: {
  setting: 'near the fence, the crowd on its feet just beyond the chain-link',
  actor:  { fighterId, name, body, motion, face },
  target: { fighterId, name, body, motion, face },
}
```

`body` is joint-level kinematics ("weight snapping onto the lead leg, elbow
locked at ninety degrees, torso whipping the arm through a horizontal arc"),
`motion` is movement quality/direction, and `face` is expression + gaze —
condition-aware (tired fighters gasp, rocked fighters' eyes go glassy).
Kinematics always match the named technique in the commentary, and all of it is
deterministic per seed.

### Anti-repetition (variety engine)
All narration and scene prose is drawn through a usage tracker
(`src/engine/variety.ts`): within a fight, a template bank never repeats a
variant until every variant has been used, and a new cycle never opens with the
line that just closed the previous one. Each fight result stores a **usage
log** — which variant of which bank was used, in order — which the app rolls
into a "recently used" map fed into the next simulation, so back-to-back fights
(and tournament rounds) avoid reusing prose the user just read. The fight
screen's Variety Log section shows exactly what was drawn and flags any
cycle-forced reuse. Replay stays exact: same seed + same avoid map reproduces
the identical fight.

### Tournaments
4/8/16-fighter single-elimination brackets with optional **damage carryover**:
a fighter who survives a war enters the next round compromised while a quick
finisher stays fresh — the classic one-night-tournament dynamic.

## Tests

Monte Carlo balance checks and determinism/replay guarantees live in
`src/engine/__tests__/`:

```bash
npx tsx --test src/engine/__tests__/engine.test.ts
```

## Project layout

```
src/
  engine/        # pure simulation: fight engine, tournaments, narration, scenes
  store/         # zustand + AsyncStorage persistence
  app/           # expo-router screens (tabs: Fighters / Fight / Tournament)
  components/    # shared UI
```
