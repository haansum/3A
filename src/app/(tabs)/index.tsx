import { useRouter } from 'expo-router';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FighterCard } from '@/components/fighter-card';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useStore } from '@/store/useStore';

export default function FightersScreen() {
  const router = useRouter();
  const fighters = useStore((s) => s.fighters);
  const fighterOrder = useStore((s) => s.fighterOrder);
  const roster = fighterOrder.map((id) => fighters[id]).filter(Boolean);

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <ThemedText type="subtitle">Fighters</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {roster.length} on the roster
            </ThemedText>
          </View>
          <Pressable
            onPress={() => router.push('/fighter/new')}
            style={({ pressed }) => pressed && styles.pressed}>
            <ThemedView type="backgroundSelected" style={styles.addButton}>
              <ThemedText type="smallBold">＋ New</ThemedText>
            </ThemedView>
          </Pressable>
        </View>
        <FlatList
          data={roster}
          keyExtractor={(f) => f.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <FighterCard fighter={item} onPress={() => router.push(`/fighter/${item.id}`)} />
          )}
          ListEmptyComponent={
            <ThemedText type="small" themeColor="textSecondary" style={styles.empty}>
              No fighters yet. Create one to get started.
            </ThemedText>
          }
        />
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.three,
    gap: Spacing.three,
  },
  headerText: {
    flex: 1,
    gap: Spacing.half,
  },
  addButton: {
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
  },
  list: {
    gap: Spacing.two,
    paddingBottom: BottomTabInset + Spacing.four,
  },
  empty: {
    textAlign: 'center',
    marginTop: Spacing.five,
  },
  pressed: {
    opacity: 0.7,
  },
});
