import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { Fragment, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { formatClock } from '@/engine/narration';
import type { FightEvent, SceneDescription } from '@/engine/types';
import { useStore } from '@/store/useStore';

const HIGHLIGHT_TYPES: FightEvent['type'][] = [
  'knockdown',
  'big_strike',
  'sub_attempt',
  'ko',
  'tko',
  'submission',
  'decision',
];

function SceneBlock({ scene }: { scene: SceneDescription }) {
  return (
    <ThemedView type="backgroundElement" style={styles.sceneBlock}>
      <ThemedText type="small" themeColor="textSecondary" style={styles.sceneSetting}>
        🎬 {scene.setting}
      </ThemedText>
      {[scene.actor, scene.target].map((who) => (
        <View key={who.fighterId} style={styles.sceneFighter}>
          <ThemedText type="smallBold">{who.name}</ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Body: {who.body}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Motion: {who.motion}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Face: {who.face}
          </ThemedText>
        </View>
      ))}
    </ThemedView>
  );
}

function StatRow({ label, a, b }: { label: string; a: string | number; b: string | number }) {
  return (
    <View style={styles.statRow}>
      <ThemedText type="smallBold" style={styles.statCell}>
        {a}
      </ThemedText>
      <ThemedText type="small" themeColor="textSecondary" style={styles.statLabel}>
        {label}
      </ThemedText>
      <ThemedText type="smallBold" style={styles.statCell}>
        {b}
      </ThemedText>
    </View>
  );
}

export default function FightResultScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const results = useStore((s) => s.results);
  const fighters = useStore((s) => s.fighters);
  const runQuickFight = useStore((s) => s.runQuickFight);
  const [showScenes, setShowScenes] = useState(true);

  const result = results[id];
  if (!result) {
    return (
      <ThemedView style={[styles.container, styles.missing]}>
        <ThemedText type="small" themeColor="textSecondary">
          This fight result is no longer stored.
        </ThemedText>
      </ThemedView>
    );
  }

  const winnerName =
    result.winnerId === result.fighterAId
      ? result.fighterAName
      : result.winnerId === result.fighterBId
        ? result.fighterBName
        : null;

  const canRematch = !!fighters[result.fighterAId] && !!fighters[result.fighterBId] && !result.tournamentId;
  const rematch = () => {
    const newId = runQuickFight(result.fighterAId, result.fighterBId, result.scheduledRounds);
    if (newId) router.replace(`/fight/${newId}`);
  };

  const rounds: FightEvent[][] = [];
  for (const e of result.events) {
    (rounds[e.round - 1] ??= []).push(e);
  }

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: `${result.fighterAName} vs ${result.fighterBName}` }} />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <ThemedView type="backgroundElement" style={styles.hero}>
          <ThemedText type="smallBold" style={styles.heroNames}>
            {result.fighterAName}  vs  {result.fighterBName}
          </ThemedText>
          <ThemedText type="subtitle" style={styles.heroResult}>
            {winnerName ?? 'Draw'}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {winnerName ? `wins by ${result.method}` : result.method} · Round {result.endRound},{' '}
            {formatClock(result.endTime)}
          </ThemedText>
        </ThemedView>

        <View style={styles.section}>
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
            STATS
          </ThemedText>
          <ThemedView type="backgroundElement" style={styles.statsCard}>
            <View style={styles.statRow}>
              <ThemedText type="smallBold" style={styles.statCell} numberOfLines={1}>
                {result.fighterAName}
              </ThemedText>
              <View style={styles.statLabel} />
              <ThemedText type="smallBold" style={styles.statCell} numberOfLines={1}>
                {result.fighterBName}
              </ThemedText>
            </View>
            <StatRow
              label="Sig. strikes"
              a={`${result.statsA.sigStrikes}/${result.statsA.sigStrikesThrown}`}
              b={`${result.statsB.sigStrikes}/${result.statsB.sigStrikesThrown}`}
            />
            <StatRow label="Knockdowns" a={result.statsA.knockdowns} b={result.statsB.knockdowns} />
            <StatRow
              label="Takedowns"
              a={`${result.statsA.takedowns}/${result.statsA.takedownsAttempted}`}
              b={`${result.statsB.takedowns}/${result.statsB.takedownsAttempted}`}
            />
            <StatRow label="Sub attempts" a={result.statsA.subAttempts} b={result.statsB.subAttempts} />
            <StatRow
              label="Control"
              a={formatClock(Math.round(result.statsA.controlSeconds))}
              b={formatClock(Math.round(result.statsB.controlSeconds))}
            />
          </ThemedView>
        </View>

        {result.scorecards.length > 0 && (
          <View style={styles.section}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
              SCORECARDS
            </ThemedText>
            <ThemedView type="backgroundElement" style={styles.statsCard}>
              {result.scorecards.map((card) => (
                <View key={card.judge} style={styles.statRow}>
                  <ThemedText type="smallBold" style={styles.statCell}>
                    {card.totalA}
                  </ThemedText>
                  <ThemedText type="small" themeColor="textSecondary" style={styles.statLabel}>
                    {card.judge}
                  </ThemedText>
                  <ThemedText type="smallBold" style={styles.statCell}>
                    {card.totalB}
                  </ThemedText>
                </View>
              ))}
            </ThemedView>
          </View>
        )}

        <View style={styles.section}>
          <View style={styles.pbpHeader}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
              PLAY-BY-PLAY
            </ThemedText>
            <View style={styles.sceneToggle}>
              <ThemedText type="small" themeColor="textSecondary">
                Scene direction
              </ThemedText>
              <Switch value={showScenes} onValueChange={setShowScenes} />
            </View>
          </View>
          {rounds.map((events, i) => (
            <Fragment key={i}>
              {events.map((e, j) => {
                if (e.type === 'round_start') {
                  return (
                    <ThemedText key={j} type="smallBold" style={styles.roundHeader}>
                      Round {e.round}
                    </ThemedText>
                  );
                }
                const highlight = HIGHLIGHT_TYPES.includes(e.type);
                return (
                  <Fragment key={j}>
                    <View style={styles.eventRow}>
                      <ThemedText type="code" themeColor="textSecondary" style={styles.eventTime}>
                        {formatClock(e.time)}
                      </ThemedText>
                      <ThemedText type={highlight ? 'smallBold' : 'small'} style={styles.eventText}>
                        {e.text}
                      </ThemedText>
                    </View>
                    {showScenes && highlight && e.scene && <SceneBlock scene={e.scene} />}
                  </Fragment>
                );
              })}
            </Fragment>
          ))}
        </View>

        {result.usage && (
          <View style={styles.section}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
              VARIETY LOG
            </ThemedText>
            <ThemedView type="backgroundElement" style={styles.statsCard}>
              {(() => {
                const banks = Object.entries(result.usage!);
                const totalPicks = banks.reduce((n, [, u]) => n + u.picks.length, 0);
                const repeated = banks
                  .map(([bank, u]) => {
                    const counts = new Map<number, number>();
                    for (const p of u.picks) counts.set(p, (counts.get(p) ?? 0) + 1);
                    const repeats = [...counts.values()].filter((c) => c > 1).reduce((n, c) => n + c - 1, 0);
                    return { bank, u, repeats };
                  })
                  .filter((r) => r.repeats > 0);
                return (
                  <>
                    <ThemedText type="small" themeColor="textSecondary">
                      {totalPicks} descriptions drawn from {banks.length} template banks.{' '}
                      {repeated.length === 0
                        ? 'No repeated prose in this fight.'
                        : 'Variants only repeat once a bank is exhausted:'}
                    </ThemedText>
                    {repeated.map(({ bank, u, repeats }) => (
                      <ThemedText key={bank} type="code" themeColor="textSecondary">
                        {bank}: {u.picks.length} picks / {u.size} variants ({repeats}{' '}
                        {repeats === 1 ? 'reuse' : 'reuses'})
                      </ThemedText>
                    ))}
                  </>
                );
              })()}
            </ThemedView>
          </View>
        )}

        <ThemedText type="code" themeColor="textSecondary" style={styles.seed}>
          replay seed: {result.seed}
        </ThemedText>

        {canRematch && (
          <Pressable onPress={rematch} style={({ pressed }) => pressed && styles.pressed}>
            <ThemedView type="backgroundSelected" style={styles.rematchButton}>
              <ThemedText type="smallBold">Run It Back</ThemedText>
            </ThemedView>
          </Pressable>
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  missing: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.four,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  hero: {
    alignItems: 'center',
    gap: Spacing.one,
    padding: Spacing.four,
    borderRadius: Spacing.four,
  },
  heroNames: {
    textAlign: 'center',
  },
  heroResult: {
    textAlign: 'center',
  },
  section: {
    gap: Spacing.two,
  },
  sectionLabel: {
    letterSpacing: 1,
  },
  statsCard: {
    borderRadius: Spacing.three,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  statRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  statCell: {
    flex: 1,
    textAlign: 'center',
  },
  statLabel: {
    flex: 1,
    textAlign: 'center',
  },
  roundHeader: {
    marginTop: Spacing.two,
  },
  pbpHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sceneToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  sceneBlock: {
    marginLeft: 36 + Spacing.two,
    borderRadius: Spacing.three,
    padding: Spacing.three,
    gap: Spacing.two,
  },
  sceneSetting: {
    fontStyle: 'italic',
  },
  sceneFighter: {
    gap: Spacing.half,
  },
  eventRow: {
    flexDirection: 'row',
    gap: Spacing.two,
    alignItems: 'flex-start',
  },
  eventTime: {
    marginTop: 3,
    minWidth: 36,
  },
  eventText: {
    flex: 1,
  },
  seed: {
    textAlign: 'center',
  },
  rematchButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});
