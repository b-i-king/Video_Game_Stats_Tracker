import { useEffect } from 'react';
import { Text, TextInput, View, ActivityIndicator } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as SplashScreen from 'expo-splash-screen';
import {
  useFonts,
  FiraCode_400Regular,
  FiraCode_700Bold,
} from '@expo-google-fonts/fira-code';
import { AuthProvider } from '@/auth/useAuth';
import { AppNavigator } from '@/navigation/AppNavigator';
import { registerForPushNotifications } from '@/notifications/pushNotifications';

SplashScreen.preventAutoHideAsync();

// Apply Fira Code globally to all Text and TextInput components
((Text as any).defaultProps ??= {}).style = { fontFamily: 'FiraCode_400Regular' };
((TextInput as any).defaultProps ??= {}).style = { fontFamily: 'FiraCode_400Regular' };

export default function App() {
  const [fontsLoaded] = useFonts({ FiraCode_400Regular, FiraCode_700Bold });

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync();
  }, [fontsLoaded]);

  useEffect(() => {
    registerForPushNotifications();
  }, []);

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, backgroundColor: '#111111', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator color="#C4A035" />
      </View>
    );
  }

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <NavigationContainer>
          <StatusBar style="light" />
          <AppNavigator />
        </NavigationContainer>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
