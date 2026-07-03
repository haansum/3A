import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, TextInput, View } from 'react-native';

import { Chip } from '@/components/chip';
import { FighterCard } from '@/components/fighter-card';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useStore } from '@/store/useStore';

const VALID_SIZES = [4, 8, 16];

export default function NewTournamentScreen() {
  const router = useRouter();
  const theme = useTheme();
  const fighters = useStore((s) => s.fighters);
  const fighterOrder = useStore((s) => s.fighterOrder);
  const createNewTournament = useStore((s) => s.createNewTournament);

  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [carryover, setCarryover] = useState(true);
  const [roundsPerFight, setRoundsPerFight] = useState(3);

  const toggle = (id: string) =>
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : prev.length < 16 ? [...prev, id] : prev,
    );

  const validSize = VALID_SIZES.includes(selected.length);

  const create = () => {
    if (!validSize) return;
    const id = createNewTournament(name.trim() || 'Grand Prix', selected, {
      carryover,
      roundsPerFight,
    });
    router.replace(`/tournament/${id}`);
  };

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <TextInput
          style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
          placeholder="Tournament name"
          placeholderTextColor={theme.textSecondary}
          value={name}
          onChangeText={setName}
        />

        <View style={styles.optionRow}>
          <View style={styles.optionText}>
            <ThemedText type="small">Damage carryover</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Wars leave winners compromised for the next round
            </ThemedText>
          </View>
          <Switch value={carryover} onValueChange={setCarryover} />
        </View>

        <View style={styles.chipRow}>
          <Chip label="3-round fights" selected={roundsPerFight === 3} onPress={() => setRoundsPerFight(3)} />
          <Chip label="5-round fights" selected={roundsPerFight === 5} onPress={() => setRoundsPerFight(5)} />
        </View>

        <View style={styles.section}>
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
            BRACKET ({selected.length} SELECTED — NEED 4, 8, OR 16)
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Selection order sets the bracket: 1st picks fights 2nd, 3rd fights 4th, and so on.
          </ThemedText>
          <View style={styles.list}>
            {fighterOrder.map((id) => {
              const f = fighters[id];
              if (!f) return null;
              const idx = selected.indexOf(id);
              return (
                <FighterCard
                  key={id}
                  fighter={f}
                  selected={idx >= 0}
                  badge={idx >= 0 ? `#${idx + 1}` : undefined}
                  onPress={() => toggle(id)}
                />
              );
            })}
          </View>
        </View>

        <Pressable onPress={create} disabled={!validSize} style={({ pressed }) => pressed && styles.pressed}>
          <ThemedView type={validSize ? 'backgroundSelected' : 'backgroundElement'} style={styles.createButton}>
            <ThemedText type="smallBold" themeColor={validSize ? 'text' : 'textSecondary'}>
              Create Tournament
            </ThemedText>
          </ThemedView>
        </Pressable>
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scroll: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.four,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  input: {
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two + 2,
    fontSize: 16,
  },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
  },
  optionText: {
    flex: 1,
    gap: Spacing.half,
  },
  chipRow: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  section: {
    gap: Spacing.two,
  },
  sectionLabel: {
    letterSpacing: 1,
  },
  list: {
    gap: Spacing.two,
  },
  createButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});
