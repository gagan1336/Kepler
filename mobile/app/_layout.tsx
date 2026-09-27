import { useEffect } from 'react'
import { Stack } from 'expo-router'
import { StatusBar } from 'expo-status-bar'
import * as SplashScreen from 'expo-splash-screen'
import { useFonts } from 'expo-font'
import { GestureHandlerRootView } from 'react-native-gesture-handler'
import { AuthProvider } from '@/lib/auth.tsx'
import { Colors } from '@/constants/theme'

SplashScreen.preventAutoHideAsync()

// Font family constants — mapped to system fonts for now,
// swap out for custom .ttf files in assets/fonts/ if needed
export const FontFamily = {
  regular:   'System',
  semibold:  'System',
  bold:      'System',
  black:     'System',
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({})   // no custom fonts loaded at startup

  useEffect(() => {
    SplashScreen.hideAsync()
  }, [])

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <AuthProvider>
        <StatusBar style="light" backgroundColor={Colors.bg} />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: Colors.bg },
            animation: 'slide_from_right',
          }}
        >
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="onboarding" options={{ animation: 'fade', gestureEnabled: false }} />
          <Stack.Screen name="login" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="register" options={{ animation: 'slide_from_bottom' }} />
          <Stack.Screen name="stock/[symbol]" options={{ animation: 'slide_from_right' }} />
        </Stack>
      </AuthProvider>
    </GestureHandlerRootView>
  )
}
