import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, View } from 'react-native';

import { useAuth } from '@/auth/useAuth';
import { LoginScreen } from '@/screens/LoginScreen';
import { StatsEntryScreen } from '@/screens/StatsEntryScreen';
import { StatsHistoryScreen } from '@/screens/StatsHistoryScreen';
import { DashboardScreen } from '@/screens/DashboardScreen';
import { LeaderboardScreen } from '@/screens/LeaderboardScreen';
import { ProfileScreen } from '@/screens/ProfileScreen';

// ── Color constants ───────────────────────────────────────────────────────────
const GOLD = '#C4A035';
const BG = '#111111';
const INACTIVE = '#555555';

// ── Stack types ───────────────────────────────────────────────────────────────
export type RootStackParamList = {
  Auth: undefined;
  Main: undefined;
};

export type TabParamList = {
  Stats: undefined;
  History: undefined;
  Dashboard: undefined;
  Leaderboard: undefined;
  Profile: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

function TabIcon(name: keyof typeof Ionicons.glyphMap, color: string, size: number) {
  return <Ionicons name={name} size={size} color={color} />;
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: BG, borderTopColor: '#222' },
        tabBarActiveTintColor: GOLD,
        tabBarInactiveTintColor: INACTIVE,
      }}
    >
      <Tab.Screen
        name="Stats"
        component={StatsEntryScreen}
        options={{ tabBarIcon: ({ color, size }) => TabIcon('game-controller', color, size) }}
      />
      <Tab.Screen
        name="History"
        component={StatsHistoryScreen}
        options={{ tabBarIcon: ({ color, size }) => TabIcon('bar-chart', color, size) }}
      />
      <Tab.Screen
        name="Dashboard"
        component={DashboardScreen}
        options={{ tabBarIcon: ({ color, size }) => TabIcon('tv', color, size) }}
      />
      <Tab.Screen
        name="Leaderboard"
        component={LeaderboardScreen}
        options={{ tabBarIcon: ({ color, size }) => TabIcon('trophy', color, size) }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ tabBarIcon: ({ color, size }) => TabIcon('person', color, size) }}
      />
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: BG }}>
        <ActivityIndicator color={GOLD} size="large" />
      </View>
    );
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {user ? (
        <Stack.Screen name="Main" component={MainTabs} />
      ) : (
        <Stack.Screen name="Auth" component={LoginScreen} />
      )}
    </Stack.Navigator>
  );
}
