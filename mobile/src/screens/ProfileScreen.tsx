import { View, Text, StyleSheet, TouchableOpacity, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useEffect, useState } from 'react';
import { useAuth } from '@/auth/useAuth';
import { getQueueStatus } from '@/api/stats';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

export function ProfileScreen() {
  const { user, signOut, token } = useAuth();
  const [queue, setQueue] = useState({ pending: 0, processing: 0, sent: 0, failed: 0 });

  useEffect(() => {
    if (!token) return;
    getQueueStatus(token).then(setQueue).catch(() => {/* non-critical */});
  }, [token]);

  function handleSignOut() {
    Alert.alert('Sign out', 'Are you sure you want to sign out?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign out', style: 'destructive', onPress: signOut },
    ]);
  }

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.container}>
        <Text style={styles.heading}>Profile</Text>

        <View style={styles.card}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>
              {user?.username?.charAt(0).toUpperCase() ?? '?'}
            </Text>
          </View>
          <Text style={styles.username}>{user?.username ?? '—'}</Text>
          <Text style={styles.role}>{user?.role ?? '—'}</Text>
        </View>

        <View style={styles.infoCard}>
          <InfoRow label="Email" value={user?.email ?? '—'} />
          <InfoRow label="Role" value={user?.role ?? '—'} />
        </View>

        {/* Queue Status */}
        <Text style={styles.sectionLabel}>📬 Post Queue</Text>
        <View style={styles.queueCard}>
          <View style={styles.queueItem}>
            <Text style={styles.queueCount}>{queue.pending + queue.processing}</Text>
            <Text style={styles.queueLabel}>Pending</Text>
          </View>
          <View style={styles.queueDivider} />
          <View style={styles.queueItem}>
            <Text style={styles.queueCount}>{queue.sent}</Text>
            <Text style={styles.queueLabel}>Sent</Text>
          </View>
          <View style={styles.queueDivider} />
          <View style={styles.queueItem}>
            <Text style={[styles.queueCount, queue.failed > 0 && { color: '#E74C3C' }]}>
              {queue.failed}
            </Text>
            <Text style={styles.queueLabel}>Failed</Text>
          </View>
        </View>

        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutText}>Sign Out</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { flex: 1, padding: 20 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 20 },
  card: {
    backgroundColor: CARD,
    borderRadius: 14,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: BORDER,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: GOLD,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  avatarText: { fontSize: 32, fontWeight: '700', color: '#000' },
  username: { fontSize: 20, fontWeight: '700', color: '#FFF', marginBottom: 4 },
  role: { fontSize: 13, color: '#888', textTransform: 'capitalize' },
  infoCard: {
    backgroundColor: CARD,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: BORDER,
    marginBottom: 24,
    overflow: 'hidden',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  infoLabel: { color: '#888', fontSize: 14 },
  infoValue: { color: '#FFF', fontSize: 14, fontWeight: '500' },
  sectionLabel: { color: '#888', fontSize: 12, fontWeight: '600', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.8 },
  queueCard: {
    backgroundColor: CARD,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: BORDER,
    flexDirection: 'row',
    marginBottom: 24,
    overflow: 'hidden',
  },
  queueItem: { flex: 1, alignItems: 'center', paddingVertical: 14 },
  queueCount: { fontSize: 22, fontWeight: '700', color: GOLD },
  queueLabel: { fontSize: 11, color: '#888', marginTop: 2 },
  queueDivider: { width: 1, backgroundColor: BORDER },
  signOutBtn: {
    borderWidth: 1,
    borderColor: '#C0392B',
    borderRadius: 10,
    padding: 14,
    alignItems: 'center',
  },
  signOutText: { color: '#C0392B', fontWeight: '600', fontSize: 15 },
});
