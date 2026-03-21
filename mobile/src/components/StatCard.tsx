import { View, Text, StyleSheet } from 'react-native';

const GOLD = '#C4A035';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

interface StatCardProps {
  label: string;
  value: number | string;
  /** Optional: previous value to show delta arrow */
  prevValue?: number;
  /** Optional: smaller supplemental line below the value */
  sub?: string;
}

export function StatCard({ label, value, prevValue, sub }: StatCardProps) {
  let delta: string | null = null;
  if (prevValue !== undefined && typeof value === 'number') {
    if (value > prevValue) delta = `↑ ${(value - prevValue).toFixed(1)}`;
    else if (value < prevValue) delta = `↓ ${(prevValue - value).toFixed(1)}`;
    else delta = '→ no change';
  }

  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
      {delta && (
        <Text style={[styles.delta, { color: delta.startsWith('↑') ? '#2ECC71' : delta.startsWith('↓') ? '#E74C3C' : '#888' }]}>
          {delta}
        </Text>
      )}
      {sub && <Text style={styles.sub}>{sub}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: CARD,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: BORDER,
    padding: 16,
    alignItems: 'center',
    flex: 1,
    minWidth: 90,
  },
  label: {
    fontSize: 11,
    color: '#888',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 6,
    textAlign: 'center',
  },
  value: {
    fontSize: 28,
    fontWeight: '700',
    color: GOLD,
  },
  delta: {
    fontSize: 12,
    marginTop: 4,
  },
  sub: {
    fontSize: 11,
    color: '#666',
    marginTop: 4,
    textAlign: 'center',
  },
});
