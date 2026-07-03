import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { nextRoundIndex, roundLabel, type BracketMatch } from '@/engine/tournament';
import { useStore } from '@/store/useStore';

const METHOD_SHORT: Record<string, string> = {
  KO: 'KO',
  TKO: 'TKO',
  Submission: 'SUB',
  'Unanimous Decision': 'DEC',
  'Split Decision': 'S-DEC',
  'Majority Decision': 'M-DEC',
  Draw: 'DRAW',
};

export default function TournamentScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const tournaments = useStore((s) => s.tournaments);
  const fighters = useStore((s) => s.fighters);
  const results = useStore((s) => s.results);
  const simulateTournamentRound = useStore((s) => s.simulateTournamentRound);

  const t = tournaments[id];
  if (!t) {
    return (
      <ThemedView style={[styles.container, styles.missing]}>
        <ThemedText type="small" themeColor="textSecondary">
          Tournament not found.
        </ThemedText>
      </ThemedView>
    );
  }

  const fighterName = (fid: string | null) =>
    fid ? (fighters[fid]?.name ?? 'Unknown fighter') : 'TBD';
  const next = nextRoundIndex(t);
  const champion = t.championId ? fighters[t.championId] : null;

  const renderMatch = (match: BracketMatch) => {
    const result = match.resultId ? results[match.resultId] : null;
    const done = !!match.winnerId;
    const line = (fid: string | null) => {
      const isWinner = done && fid === match.winnerId;
      return (
        <ThemedText
          type={isWinner ? 'smallBold' : 'small'}
          themeColor={done && !isWinner ? 'textSecondary' : 'text'}
          numberOfLines={1}>
          {isWinner ? '✓ ' : ''}
          {fighterName(fid)}
        </ThemedText>
      );
    };
    return (
      <Pressable
        key={match.id}
        disabled={!result}
        onPress={() => result && router.push(`/fight/${result.id}`)}
        style={({ pressed }) => pressed && styles.pressed}>
        <ThemedView type="backgroundElement" style={styles.match}>
          <View style={styles.matchNames}>
            {line(match.fighterAId)}
            {line(match.fighterBId)}
          </View>
          {result && (
            <View style={styles.matchMeta}>
              <ThemedText type="smallBold">{METHOD_SHORT[result.method] ?? result.method}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                R{result.endRound}
              </ThemedText>
            </View>
          )}
        </ThemedView>
      </Pressable>
    );
  };

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: t.name }} />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {champion && (
          <ThemedView type="backgroundElement" style={styles.championCard}>
            <ThemedText type="small" themeColor="textSecondary">
              CHAMPION
            </ThemedText>
            <ThemedText type="subtitle" style={styles.championName}>
              🏆 {champion.name}
            </ThemedText>
          </ThemedView>
        )}

        {t.rounds.map((matches, i) => (
          <View key={i} style={styles.section}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
              {roundLabel(t, i).toUpperCase()}
            </ThemedText>
            <View style={styles.matchList}>{matches.map(renderMatch)}</View>
          </View>
        ))}

        {next >= 0 && (
          <Pressable
            onPress={() => simulateTournamentRound(t.id)}
            style={({ pressed }) => pressed && styles.pressed}>
            <ThemedView type="backgroundSelected" style={styles.simButton}>
              <ThemedText type="smallBold">Simulate {roundLabel(t, next)}</ThemedText>
            </ThemedView>
          </Pressable>
        )}

        {t.carryover && (
          <ThemedText type="small" themeColor="textSecondary" style={styles.note}>
            Damage carryover is on: fighters bring wounds from earlier rounds into the next fight.
          </ThemedText>
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
  championCard: {
    alignItems: 'center',
    padding: Spacing.four,
    borderRadius: Spacing.four,
    gap: Spacing.one,
  },
  championName: {
    textAlign: 'center',
  },
  section: {
    gap: Spacing.two,
  },
  sectionLabel: {
    letterSpacing: 1,
  },
  matchList: {
    gap: Spacing.two,
  },
  match: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
    gap: Spacing.three,
  },
  matchNames: {
    flex: 1,
    gap: Spacing.half,
  },
  matchMeta: {
    alignItems: 'center',
  },
  simButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  note: {
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});
