import { useRouter } from 'expo-router';
import { Alert, FlatList, Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { nextRoundIndex, roundLabel } from '@/engine/tournament';
import { useStore } from '@/store/useStore';

export default function TournamentsScreen() {
  const router = useRouter();
  const tournaments = useStore((s) => s.tournaments);
  const tournamentOrder = useStore((s) => s.tournamentOrder);
  const fighters = useStore((s) => s.fighters);
  const deleteTournament = useStore((s) => s.deleteTournament);
  const list = tournamentOrder.map((id) => tournaments[id]).filter(Boolean);

  const confirmDelete = (id: string, name: string) => {
    Alert.alert('Delete tournament?', `“${name}” and its fight results will be removed.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteTournament(id) },
    ]);
  };

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <ThemedText type="subtitle">Tournaments</ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              Single elimination, winner takes all
            </ThemedText>
          </View>
          <Pressable
            onPress={() => router.push('/tournament/new')}
            style={({ pressed }) => pressed && styles.pressed}>
            <ThemedView type="backgroundSelected" style={styles.addButton}>
              <ThemedText type="smallBold">＋ New</ThemedText>
            </ThemedView>
          </Pressable>
        </View>
        <FlatList
          data={list}
          keyExtractor={(t) => t.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const champion = item.championId ? fighters[item.championId] : null;
            const next = nextRoundIndex(item);
            const status = item.championId
              ? `🏆 ${champion?.name ?? 'Champion crowned'}`
              : next >= 0
                ? `In progress — ${roundLabel(item, next)} up next`
                : 'In progress';
            return (
              <Pressable
                onPress={() => router.push(`/tournament/${item.id}`)}
                onLongPress={() => confirmDelete(item.id, item.name)}
                style={({ pressed }) => pressed && styles.pressed}>
                <ThemedView type="backgroundElement" style={styles.card}>
                  <ThemedText type="smallBold">{item.name}</ThemedText>
                  <ThemedText type="small" themeColor="textSecondary">
                    {item.fighterIds.length} fighters · {status}
                  </ThemedText>
                </ThemedView>
              </Pressable>
            );
          }}
          ListEmptyComponent={
            <ThemedText type="small" themeColor="textSecondary" style={styles.empty}>
              No tournaments yet. Create one and crown a champion.
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
  card: {
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
    gap: Spacing.half,
  },
  empty: {
    textAlign: 'center',
    marginTop: Spacing.five,
  },
  pressed: {
    opacity: 0.7,
  },
});
