import { useState, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  FlatList, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';
import { useAuth } from '@/auth/useAuth';
import { getStats, StatHistoryPoint } from '@/api/stats';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

export function StatsHistoryScreen() {
  const { token } = useAuth();
  const [playerName, setPlayerName] = useState('');
  const [gameName, setGameName] = useState('');
  const [history, setHistory] = useState<StatHistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [interactiveUrl, setInteractiveUrl] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!playerName || !gameName) {
      Alert.alert('Required', 'Enter player name and game name.');
      return;
    }
    setLoading(true);
    setHistory([]);
    setInteractiveUrl(null);
    try {
      const data = await getStats(token!, playerName, gameName);
      setHistory(data);
      // Derive GCS interactive chart URL (matches gcs_utils.py path convention)
      const playerSlug = playerName.toLowerCase().replace(/\s+/g, '_');
      const gameSlug = gameName.toLowerCase().replace(/\s+/g, '_');
      const API_URL = process.env.EXPO_PUBLIC_API_URL ?? '';
      setInteractiveUrl(
        `https://storage.googleapis.com/game-tracker-charts/twitter/interactive/${playerSlug}_${gameSlug}.html`
      );
    } catch (e: unknown) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  }, [token, playerName, gameName]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.heading}>Stat History</Text>

        <TextInput
          style={styles.input}
          placeholder="Player Name"
          placeholderTextColor="#555"
          value={playerName}
          onChangeText={setPlayerName}
          color="#FFF"
        />
        <TextInput
          style={styles.input}
          placeholder="Game Name"
          placeholderTextColor="#555"
          value={gameName}
          onChangeText={setGameName}
          color="#FFF"
        />
        <TouchableOpacity style={styles.searchBtn} onPress={handleSearch}>
          <Text style={styles.searchText}>Search</Text>
        </TouchableOpacity>

        {loading && <ActivityIndicator color={GOLD} style={{ marginTop: 20 }} />}

        {/* Interactive Plotly chart */}
        {interactiveUrl && history.length > 0 && (
          <View style={styles.chartContainer}>
            <WebView
              source={{ uri: interactiveUrl }}
              style={{ flex: 1 }}
              scrollEnabled={false}
            />
          </View>
        )}

        {/* Raw data list */}
        <FlatList
          data={history}
          keyExtractor={(_, i) => String(i)}
          renderItem={({ item }) => (
            <View style={styles.row}>
              <Text style={styles.rowDate}>{item.date}</Text>
              <Text style={styles.rowType}>{item.stat_type}</Text>
              <Text style={styles.rowValue}>{item.stat_value}</Text>
            </View>
          )}
          ListEmptyComponent={
            !loading ? (
              <Text style={styles.empty}>No results yet. Search above.</Text>
            ) : null
          }
          contentContainerStyle={{ paddingBottom: 20 }}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { flex: 1, padding: 20 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 16 },
  input: {
    backgroundColor: CARD,
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    borderWidth: 1,
    borderColor: BORDER,
    color: '#FFF',
    marginBottom: 10,
  },
  searchBtn: {
    backgroundColor: GOLD,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginBottom: 16,
  },
  searchText: { color: '#000', fontWeight: '700', fontSize: 15 },
  chartContainer: {
    height: 260,
    borderRadius: 10,
    overflow: 'hidden',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: BORDER,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: CARD,
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  rowDate: { color: '#888', fontSize: 13, flex: 1 },
  rowType: { color: '#CCC', fontSize: 13, flex: 2 },
  rowValue: { color: GOLD, fontSize: 13, fontWeight: '700', textAlign: 'right' },
  empty: { color: '#555', textAlign: 'center', marginTop: 40, fontSize: 14 },
});
