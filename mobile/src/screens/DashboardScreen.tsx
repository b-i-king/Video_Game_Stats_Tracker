import { View, StyleSheet, Text, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { useState } from 'react';

const GOLD = '#C4A035';
const BG = '#111111';
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';

export function DashboardScreen() {
  const [loading, setLoading] = useState(true);

  return (
    <SafeAreaView style={styles.safe}>
      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator color={GOLD} size="large" />
          <Text style={styles.loadingText}>Loading dashboard…</Text>
        </View>
      )}
      <WebView
        source={{ uri: `${API_URL}/dashboard` }}
        style={styles.webview}
        onLoadEnd={() => setLoading(false)}
        onError={() => setLoading(false)}
        allowsInlineMediaPlayback
        mediaPlaybackRequiresUserAction={false}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  webview: { flex: 1, backgroundColor: BG },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: BG,
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 10,
  },
  loadingText: { color: '#888', marginTop: 12, fontSize: 14 },
});
