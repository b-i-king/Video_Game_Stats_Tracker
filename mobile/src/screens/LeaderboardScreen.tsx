import { View, Text, StyleSheet, FlatList, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useEffect, useState } from 'react';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

// ── Placeholder until Supabase is wired up ────────────────────────────────────

interface LeaderboardEntry {
  rank: number;
  player: string;
  game: string;
  stat_label: string;
  stat_value: number;
}

export function LeaderboardScreen() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO: replace with Supabase realtime subscription
    // import { createClient } from '@supabase/supabase-js';
    // const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    // const { data } = await supabase.from('leaderboard').select('*').order('stat_value', { ascending: false }).limit(25);
    setTimeout(() => {
      setEntries([]);
      setLoading(false);
    }, 500);
  }, []);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.heading}>Leaderboard</Text>
        <Text style={styles.subtitle}>Community rankings — coming soon</Text>

        {loading ? (
          <ActivityIndicator color={GOLD} style={{ marginTop: 40 }} />
        ) : (
          <FlatList
            data={entries}
            keyExtractor={(item) => String(item.rank)}
            renderItem={({ item }) => (
              <View style={styles.row}>
                <Text style={styles.rank}>#{item.rank}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.player}>{item.player}</Text>
                  <Text style={styles.game}>{item.game}</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statValue}>{item.stat_value}</Text>
                  <Text style={styles.statLabel}>{item.stat_label}</Text>
                </View>
              </View>
            )}
            ListEmptyComponent={
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyIcon}>🏆</Text>
                <Text style={styles.emptyText}>
                  Leaderboard will display community stats once Supabase is connected.
                </Text>
              </View>
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { flex: 1, padding: 20 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#666', marginBottom: 20 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: CARD,
    borderRadius: 10,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: BORDER,
  },
  rank: { fontSize: 18, fontWeight: '700', color: GOLD, width: 40 },
  player: { fontSize: 15, fontWeight: '600', color: '#FFF' },
  game: { fontSize: 12, color: '#888', marginTop: 2 },
  statBox: { alignItems: 'flex-end' },
  statValue: { fontSize: 18, fontWeight: '700', color: GOLD },
  statLabel: { fontSize: 11, color: '#888' },
  emptyContainer: { alignItems: 'center', marginTop: 60, paddingHorizontal: 30 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyText: { color: '#555', textAlign: 'center', fontSize: 14, lineHeight: 22 },
});
