import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { overallRating } from '@/engine/data';
import { STYLE_LABELS, type Fighter } from '@/engine/types';

export function FighterCard({
  fighter,
  onPress,
  selected,
  badge,
}: {
  fighter: Fighter;
  onPress?: () => void;
  selected?: boolean;
  badge?: string;
}) {
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => pressed && styles.pressed}>
      <ThemedView type={selected ? 'backgroundSelected' : 'backgroundElement'} style={styles.card}>
        <View style={styles.info}>
          <ThemedText type="smallBold" numberOfLines={1}>
            {fighter.name}
            {fighter.nickname ? (
              <ThemedText type="small" themeColor="textSecondary">
                {'  '}“{fighter.nickname}”
              </ThemedText>
            ) : null}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            {STYLE_LABELS[fighter.style]} · {fighter.wins}-{fighter.losses}
            {fighter.draws > 0 ? `-${fighter.draws}` : ''}
          </ThemedText>
        </View>
        <View style={styles.right}>
          {badge ? (
            <ThemedText type="smallBold">{badge}</ThemedText>
          ) : (
            <>
              <ThemedText type="smallBold">{overallRating(fighter)}</ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                OVR
              </ThemedText>
            </>
          )}
        </View>
      </ThemedView>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    borderRadius: Spacing.three,
    gap: Spacing.three,
  },
  info: {
    flex: 1,
    gap: Spacing.half,
  },
  right: {
    alignItems: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});
