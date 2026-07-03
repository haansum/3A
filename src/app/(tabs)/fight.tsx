import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useStore } from '@/store/useStore';

function CornerPicker({
  label,
  selectedId,
  excludeId,
  onSelect,
}: {
  label: string;
  selectedId: string | null;
  excludeId: string | null;
  onSelect: (id: string) => void;
}) {
  const fighters = useStore((s) => s.fighters);
  const fighterOrder = useStore((s) => s.fighterOrder);
  return (
    <View style={styles.section}>
      <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
        {label}
      </ThemedText>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
        {fighterOrder.map((id) => {
          const f = fighters[id];
          if (!f) return null;
          return (
            <Chip
              key={id}
              label={f.name}
              selected={selectedId === id}
              disabled={excludeId === id}
              onPress={() => onSelect(id)}
            />
          );
        })}
      </ScrollView>
    </View>
  );
}

export default function FightScreen() {
  const router = useRouter();
  const [aId, setAId] = useState<string | null>(null);
  const [bId, setBId] = useState<string | null>(null);
  const [rounds, setRounds] = useState(3);
  const runQuickFight = useStore((s) => s.runQuickFight);
  const results = useStore((s) => s.results);
  const resultOrder = useStore((s) => s.resultOrder);

  const recent = resultOrder
    .map((id) => results[id])
    .filter((r) => r && !r.tournamentId)
    .slice(0, 10);

  const ready = aId && bId && aId !== bId;

  const simulate = () => {
    if (!ready) return;
    const resultId = runQuickFight(aId!, bId!, rounds);
    if (resultId) router.push(`/fight/${resultId}`);
  };

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          <ThemedText type="subtitle" style={styles.title}>
            Fight Night
          </ThemedText>

          <CornerPicker label="RED CORNER" selectedId={aId} excludeId={bId} onSelect={setAId} />
          <CornerPicker label="BLUE CORNER" selectedId={bId} excludeId={aId} onSelect={setBId} />

          <View style={styles.section}>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
              ROUNDS
            </ThemedText>
            <View style={styles.chipRow}>
              <Chip label="3 rounds" selected={rounds === 3} onPress={() => setRounds(3)} />
              <Chip label="5 rounds (title fight)" selected={rounds === 5} onPress={() => setRounds(5)} />
            </View>
          </View>

          <Pressable onPress={simulate} disabled={!ready} style={({ pressed }) => pressed && styles.pressed}>
            <ThemedView type={ready ? 'backgroundSelected' : 'backgroundElement'} style={styles.simulateButton}>
              <ThemedText type="smallBold" themeColor={ready ? 'text' : 'textSecondary'}>
                Simulate Fight
              </ThemedText>
            </ThemedView>
          </Pressable>

          {recent.length > 0 && (
            <View style={styles.section}>
              <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
                RECENT FIGHTS
              </ThemedText>
              <View style={styles.recentList}>
                {recent.map((r) => {
                  const winner = r.winnerId === r.fighterAId ? r.fighterAName : r.fighterBName;
                  const loser = r.winnerId === r.fighterAId ? r.fighterBName : r.fighterAName;
                  const summary = r.winnerId
                    ? `${winner} def. ${loser}`
                    : `${r.fighterAName} vs ${r.fighterBName}`;
                  return (
                    <Pressable
                      key={r.id}
                      onPress={() => router.push(`/fight/${r.id}`)}
                      style={({ pressed }) => pressed && styles.pressed}>
                      <ThemedView type="backgroundElement" style={styles.recentItem}>
                        <ThemedText type="small" numberOfLines={1}>
                          {summary}
                        </ThemedText>
                        <ThemedText type="small" themeColor="textSecondary">
                          {r.method} · R{r.endRound}
                        </ThemedText>
                      </ThemedView>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  safeArea: {
    flex: 1,
    maxWidth: MaxContentWidth,
    paddingHorizontal: Spacing.three,
  },
  scroll: {
    paddingBottom: BottomTabInset + Spacing.four,
    gap: Spacing.four,
  },
  title: {
    paddingTop: Spacing.three,
  },
  section: {
    gap: Spacing.two,
  },
  sectionLabel: {
    letterSpacing: 1,
  },
  chipRow: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  simulateButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  recentList: {
    gap: Spacing.two,
  },
  recentItem: {
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: Spacing.two,
  },
  pressed: {
    opacity: 0.7,
  },
});
