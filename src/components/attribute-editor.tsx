import { Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

const SEGMENTS = 10;

/**
 * One attribute row: label, value, -/+ steppers, and a tappable
 * 10-segment bar (tap segment n to set the value to n*10).
 */
export function AttributeEditor({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  const theme = useTheme();
  const clamp = (v: number) => Math.max(1, Math.min(100, v));

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <ThemedText type="small">{label}</ThemedText>
        <View style={styles.controls}>
          <Stepper label="−" onPress={() => onChange(clamp(value - 5))} />
          <ThemedText type="smallBold" style={styles.value}>
            {value}
          </ThemedText>
          <Stepper label="+" onPress={() => onChange(clamp(value + 5))} />
        </View>
      </View>
      <View style={styles.bar}>
        {Array.from({ length: SEGMENTS }, (_, i) => {
          const filled = value >= (i + 1) * 10 - 4;
          return (
            <Pressable
              key={i}
              onPress={() => onChange((i + 1) * 10)}
              style={[
                styles.segment,
                { backgroundColor: filled ? theme.text : theme.backgroundElement },
              ]}
              hitSlop={{ top: 8, bottom: 8 }}
            />
          );
        })}
      </View>
    </View>
  );
}

function Stepper({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => pressed && styles.pressed} hitSlop={6}>
      <ThemedView type="backgroundElement" style={styles.stepper}>
        <ThemedText type="smallBold">{label}</ThemedText>
      </ThemedView>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.one,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  value: {
    minWidth: 32,
    textAlign: 'center',
  },
  stepper: {
    width: 28,
    height: 28,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bar: {
    flexDirection: 'row',
    gap: Spacing.half,
  },
  segment: {
    flex: 1,
    height: 8,
    borderRadius: 3,
  },
  pressed: {
    opacity: 0.6,
  },
});
