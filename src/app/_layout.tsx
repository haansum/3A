import { DarkTheme, DefaultTheme, Stack, ThemeProvider } from 'expo-router';
import { useColorScheme } from 'react-native';

export default function RootLayout() {
  const colorScheme = useColorScheme();
  return (
    <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
      <Stack>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="fighter/[id]" options={{ title: 'Fighter' }} />
        <Stack.Screen name="fight/[id]" options={{ title: 'Fight Result' }} />
        <Stack.Screen name="tournament/new" options={{ title: 'New Tournament' }} />
        <Stack.Screen name="tournament/[id]" options={{ title: 'Tournament' }} />
      </Stack>
    </ThemeProvider>
  );
}
