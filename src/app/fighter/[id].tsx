import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, TextInput, View } from 'react-native';

import { AttributeEditor } from '@/components/attribute-editor';
import { Chip } from '@/components/chip';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { createFighter, defaultAttributes } from '@/engine/data';
import {
  ATTRIBUTE_KEYS,
  ATTRIBUTE_LABELS,
  STYLE_LABELS,
  STYLES,
  type Fighter,
  type FightingStyle,
} from '@/engine/types';
import { useTheme } from '@/hooks/use-theme';
import { useStore } from '@/store/useStore';

export default function FighterEditScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const theme = useTheme();
  const fighters = useStore((s) => s.fighters);
  const addFighter = useStore((s) => s.addFighter);
  const updateFighter = useStore((s) => s.updateFighter);
  const deleteFighter = useStore((s) => s.deleteFighter);

  const existing = id !== 'new' ? fighters[id] : undefined;
  const [name, setName] = useState(existing?.name ?? '');
  const [nickname, setNickname] = useState(existing?.nickname ?? '');
  const [style, setStyle] = useState<FightingStyle>(existing?.style ?? 'balanced');
  const [pronouns, setPronouns] = useState<NonNullable<Fighter['pronouns']>>(existing?.pronouns ?? 'they');
  const [attributes, setAttributes] = useState(existing?.attributes ?? defaultAttributes());

  const canSave = name.trim().length > 0;

  const save = () => {
    if (!canSave) return;
    if (existing) {
      updateFighter({ ...existing, name: name.trim(), nickname: nickname.trim() || undefined, style, pronouns, attributes });
    } else {
      addFighter(createFighter(name.trim(), style, attributes, nickname.trim() || undefined, pronouns));
    }
    router.back();
  };

  const confirmDelete = () => {
    if (!existing) return;
    Alert.alert('Delete fighter?', `${existing.name} will be removed from the roster.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          deleteFighter(existing.id);
          router.back();
        },
      },
    ]);
  };

  const inputStyle = [
    styles.input,
    { color: theme.text, backgroundColor: theme.backgroundElement },
  ];

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: existing ? existing.name : 'New Fighter' }} />
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <View style={styles.section}>
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
            IDENTITY
          </ThemedText>
          <TextInput
            style={inputStyle}
            placeholder="Name"
            placeholderTextColor={theme.textSecondary}
            value={name}
            onChangeText={setName}
          />
          <TextInput
            style={inputStyle}
            placeholder="Nickname (optional)"
            placeholderTextColor={theme.textSecondary}
            value={nickname}
            onChangeText={setNickname}
          />
          <View style={styles.styleRow}>
            {(['she', 'he', 'they'] as const).map((p) => (
              <Chip
                key={p}
                label={p === 'she' ? 'She/Her' : p === 'he' ? 'He/Him' : 'They/Them'}
                selected={pronouns === p}
                onPress={() => setPronouns(p)}
              />
            ))}
          </View>
          {existing && (
            <ThemedText type="small" themeColor="textSecondary">
              Record: {existing.wins}-{existing.losses}
              {existing.draws > 0 ? `-${existing.draws}` : ''}
            </ThemedText>
          )}
        </View>

        <View style={styles.section}>
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
            STYLE
          </ThemedText>
          <View style={styles.styleRow}>
            {STYLES.map((s) => (
              <Chip key={s} label={STYLE_LABELS[s]} selected={style === s} onPress={() => setStyle(s)} />
            ))}
          </View>
        </View>

        <View style={styles.section}>
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionLabel}>
            ATTRIBUTES
          </ThemedText>
          <View style={styles.attributes}>
            {ATTRIBUTE_KEYS.map((key) => (
              <AttributeEditor
                key={key}
                label={ATTRIBUTE_LABELS[key]}
                value={attributes[key]}
                onChange={(v) => setAttributes((prev) => ({ ...prev, [key]: v }))}
              />
            ))}
          </View>
        </View>

        <Pressable onPress={save} disabled={!canSave} style={({ pressed }) => pressed && styles.pressed}>
          <ThemedView type={canSave ? 'backgroundSelected' : 'backgroundElement'} style={styles.saveButton}>
            <ThemedText type="smallBold" themeColor={canSave ? 'text' : 'textSecondary'}>
              {existing ? 'Save Changes' : 'Add Fighter'}
            </ThemedText>
          </ThemedView>
        </Pressable>

        {existing && (
          <Pressable onPress={confirmDelete} style={({ pressed }) => pressed && styles.pressed}>
            <ThemedText type="small" style={styles.deleteText}>
              Delete fighter
            </ThemedText>
          </Pressable>
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
  },
  scroll: {
    padding: Spacing.three,
    paddingBottom: Spacing.six,
    gap: Spacing.four,
    width: '100%',
    maxWidth: MaxContentWidth,
    alignSelf: 'center',
  },
  section: {
    gap: Spacing.two,
  },
  sectionLabel: {
    letterSpacing: 1,
  },
  input: {
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two + 2,
    fontSize: 16,
  },
  styleRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
  },
  attributes: {
    gap: Spacing.three,
  },
  saveButton: {
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
    alignItems: 'center',
  },
  deleteText: {
    color: '#e5484d',
    textAlign: 'center',
  },
  pressed: {
    opacity: 0.7,
  },
});
