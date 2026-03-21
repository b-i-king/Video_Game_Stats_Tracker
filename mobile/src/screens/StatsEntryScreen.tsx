import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, Alert, ActivityIndicator, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/useAuth';
import { addStats, AddStatsPayload } from '@/api/stats';
import { sendLocalNotification } from '@/notifications/pushNotifications';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

type ChartType = 'bar' | 'line';
type Platform = 'twitter' | 'instagram' | 'both' | 'none';

function Field({
  label, value, onChangeText, placeholder = '', numeric = false,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  numeric?: boolean;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#555"
        keyboardType={numeric ? 'numeric' : 'default'}
        color="#FFF"
      />
    </View>
  );
}

export function StatsEntryScreen() {
  const { token } = useAuth();

  // Game info
  const [playerName, setPlayerName] = useState('');
  const [gameName, setGameName] = useState('');
  const [gameInstallment, setGameInstallment] = useState('');
  const [gameMode, setGameMode] = useState('');

  // Stats
  const [stat1Label, setStat1Label] = useState('');
  const [stat1Value, setStat1Value] = useState('');
  const [stat2Label, setStat2Label] = useState('');
  const [stat2Value, setStat2Value] = useState('');
  const [stat3Label, setStat3Label] = useState('');
  const [stat3Value, setStat3Value] = useState('');

  // Options
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [platform, setPlatform] = useState<Platform>('twitter');
  const [isLive, setIsLive] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    if (!confirmed) {
      Alert.alert('Please confirm', 'Check the confirmation toggle before submitting.');
      return;
    }
    if (!playerName || !gameName || !stat1Label || !stat1Value) {
      Alert.alert('Missing fields', 'Player name, game name, and Stat 1 are required.');
      return;
    }

    const payload: AddStatsPayload = {
      player_name: playerName,
      game_name: gameName,
      game_installment: gameInstallment || undefined,
      game_mode: gameMode || undefined,
      stat1_label: stat1Label,
      stat1_value: parseFloat(stat1Value),
      stat2_label: stat2Label || undefined,
      stat2_value: stat2Value ? parseFloat(stat2Value) : undefined,
      stat3_label: stat3Label || undefined,
      stat3_value: stat3Value ? parseFloat(stat3Value) : undefined,
      chart_type: chartType,
      platform,
      is_live: isLive,
    };

    setLoading(true);
    try {
      await addStats(token!, payload);
      await sendLocalNotification('Stats posted!', `${stat1Label}: ${stat1Value}`);
      Alert.alert('Success', 'Stats submitted and chart posted.');
      // Reset confirmation toggle
      setConfirmed(false);
    } catch (e: unknown) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Failed to submit stats');
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.heading}>Log Stats</Text>

        {/* Game Info */}
        <Text style={styles.section}>Game Info</Text>
        <Field label="Player Name" value={playerName} onChangeText={setPlayerName} />
        <Field label="Game Name" value={gameName} onChangeText={setGameName} />
        <Field label="Game Installment (optional)" value={gameInstallment} onChangeText={setGameInstallment} />
        <Field label="Game Mode (optional)" value={gameMode} onChangeText={setGameMode} />

        {/* Stats */}
        <Text style={styles.section}>Stats</Text>
        <View style={styles.statRow}>
          <View style={{ flex: 2, marginRight: 8 }}>
            <Field label="Stat 1 Label" value={stat1Label} onChangeText={setStat1Label} />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Value" value={stat1Value} onChangeText={setStat1Value} numeric />
          </View>
        </View>
        <View style={styles.statRow}>
          <View style={{ flex: 2, marginRight: 8 }}>
            <Field label="Stat 2 Label (opt)" value={stat2Label} onChangeText={setStat2Label} />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Value" value={stat2Value} onChangeText={setStat2Value} numeric />
          </View>
        </View>
        <View style={styles.statRow}>
          <View style={{ flex: 2, marginRight: 8 }}>
            <Field label="Stat 3 Label (opt)" value={stat3Label} onChangeText={setStat3Label} />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Value" value={stat3Value} onChangeText={setStat3Value} numeric />
          </View>
        </View>

        {/* Chart type */}
        <Text style={styles.section}>Chart Type</Text>
        <View style={styles.toggleRow}>
          {(['bar', 'line'] as ChartType[]).map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.chip, chartType === t && styles.chipActive]}
              onPress={() => setChartType(t)}
            >
              <Text style={[styles.chipText, chartType === t && styles.chipTextActive]}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Platform */}
        <Text style={styles.section}>Post To</Text>
        <View style={styles.toggleRow}>
          {(['twitter', 'instagram', 'both', 'none'] as Platform[]).map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.chip, platform === p && styles.chipActive]}
              onPress={() => setPlatform(p)}
            >
              <Text style={[styles.chipText, platform === p && styles.chipTextActive]}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Live toggle */}
        <View style={styles.switchRow}>
          <Text style={styles.label}>Live Stream Active</Text>
          <Switch
            value={isLive}
            onValueChange={setIsLive}
            trackColor={{ false: '#333', true: GOLD }}
            thumbColor={isLive ? '#000' : '#888'}
          />
        </View>

        {/* Confirm */}
        <View style={[styles.switchRow, { marginTop: 16 }]}>
          <Text style={[styles.label, { flex: 1 }]}>
            I have reviewed my stats and they are correct
          </Text>
          <Switch
            value={confirmed}
            onValueChange={setConfirmed}
            trackColor={{ false: '#333', true: GOLD }}
            thumbColor={confirmed ? '#000' : '#888'}
          />
        </View>

        <TouchableOpacity
          style={[styles.submitBtn, (!confirmed || loading) && styles.submitBtnDisabled]}
          onPress={handleSubmit}
          disabled={!confirmed || loading}
        >
          {loading ? (
            <ActivityIndicator color="#000" />
          ) : (
            <Text style={styles.submitText}>Submit Stats</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  scroll: { padding: 20, paddingBottom: 40 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 20 },
  section: { fontSize: 13, fontWeight: '600', color: '#888', marginTop: 20, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.8 },
  fieldGroup: { marginBottom: 12 },
  label: { fontSize: 13, color: '#AAA', marginBottom: 6 },
  input: {
    backgroundColor: CARD,
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    borderWidth: 1,
    borderColor: BORDER,
  },
  statRow: { flexDirection: 'row' },
  toggleRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: CARD,
    borderWidth: 1,
    borderColor: BORDER,
  },
  chipActive: { backgroundColor: GOLD, borderColor: GOLD },
  chipText: { color: '#AAA', fontSize: 13, fontWeight: '500' },
  chipTextActive: { color: '#000', fontWeight: '700' },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginVertical: 8,
  },
  submitBtn: {
    backgroundColor: GOLD,
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    marginTop: 24,
  },
  submitBtnDisabled: { opacity: 0.4 },
  submitText: { color: '#000', fontWeight: '700', fontSize: 16 },
});
