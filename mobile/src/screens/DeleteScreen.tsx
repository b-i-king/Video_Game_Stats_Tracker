import { useState } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/useAuth';
import {
  getPlayers, getAllGames, getRecentStats,
  deletePlayer, deleteGame, deleteStats,
  type Player, type GameDetails, type StatEntry,
} from '@/api/stats';
import { PickerModal } from '@/components/PickerModal';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';
const RED = '#C0392B';

type SubTab = 'player' | 'game' | 'stat';

function Section({ title }: { title: string }) {
  return <Text style={styles.section}>{title}</Text>;
}

function Feedback({ ok, text }: { ok: boolean; text: string }) {
  return (
    <View style={[styles.feedback, ok ? styles.feedbackOk : styles.feedbackErr]}>
      <Text style={styles.feedbackText}>{ok ? '✅ ' : '❌ '}{text}</Text>
    </View>
  );
}

// ── Delete Player ─────────────────────────────────────────────────────────────
function DeletePlayer({ jwt }: { jwt: string }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<'select' | 'confirm'>('select');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getPlayers(jwt);
      setPlayers(data);
      setLoaded(true);
      setStep('select');
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setLoading(true);
    try {
      await deletePlayer(jwt, selectedId);
      const name = players.find((p) => p.player_id === selectedId)?.player_name;
      setMsg({ ok: true, text: `"${name}" and all stats deleted.` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      setLoading(false);
    }
  }

  const selected = players.find((p) => p.player_id === selectedId);

  return (
    <View style={styles.tabContent}>
      <Text style={styles.warningText}>⚠️ This will delete the player AND all associated stats forever.</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Players' : 'Load Players to Delete'}</Text>}
      </TouchableOpacity>

      {loaded && (
        <>
          <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowPicker(true)}>
            <Text style={[styles.selectorText, !selected && styles.placeholder]} numberOfLines={1}>
              {selected ? selected.player_name : '— Select player —'}
            </Text>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>

          {selectedId && step === 'select' && (
            <>
              <Text style={styles.confirmHint}>
                About to delete <Text style={{ color: GOLD }}>{selected?.player_name}</Text> (ID: {selectedId}) and all their stats.
              </Text>
              <TouchableOpacity style={styles.warnBtn} onPress={() => setStep('confirm')}>
                <Text style={styles.warnBtnText}>Confirm Delete Player</Text>
              </TouchableOpacity>
            </>
          )}

          {step === 'confirm' && (
            <>
              <Text style={styles.dangerText}>This action is permanent and cannot be undone.</Text>
              <TouchableOpacity style={[styles.deleteBtn, loading && styles.btnDisabled]} onPress={handleDelete} disabled={loading}>
                {loading ? <ActivityIndicator color="#FFF" size="small" /> :
                  <Text style={styles.deleteBtnText}>DELETE PLAYER FOREVER</Text>}
              </TouchableOpacity>
            </>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}

          <PickerModal
            visible={showPicker}
            title="Select Player"
            options={players.map((p) => p.player_name)}
            selected={selected?.player_name ?? null}
            onSelect={(name) => {
              const p = players.find((pl) => pl.player_name === name);
              if (p) { setSelectedId(p.player_id); setStep('select'); setMsg(null); }
            }}
            onClose={() => setShowPicker(false)}
          />
        </>
      )}
    </View>
  );
}

// ── Delete Game ───────────────────────────────────────────────────────────────
function DeleteGame({ jwt }: { jwt: string }) {
  const [games, setGames] = useState<GameDetails[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<'select' | 'confirm'>('select');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getAllGames(jwt);
      setGames(data);
      setLoaded(true);
      setStep('select');
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setLoading(true);
    try {
      await deleteGame(jwt, selectedId);
      const name = games.find((g) => g.game_id === selectedId)?.game_name;
      setMsg({ ok: true, text: `Game "${name}" deleted.` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      setLoading(false);
    }
  }

  const selected = games.find((g) => g.game_id === selectedId);

  return (
    <View style={styles.tabContent}>
      <Text style={styles.hint}>You can only delete games that have zero associated stats.</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Games' : 'Load Games to Delete'}</Text>}
      </TouchableOpacity>

      {loaded && (
        <>
          <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowPicker(true)}>
            <Text style={[styles.selectorText, !selected && styles.placeholder]} numberOfLines={1}>
              {selected ? selected.game_name : '— Select game —'}
            </Text>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>

          {selectedId && step === 'select' && (
            <>
              <Text style={styles.confirmHint}>
                Attempting to delete <Text style={{ color: GOLD }}>{selected?.game_name}</Text> — this will only succeed if all stats have been removed first.
              </Text>
              <TouchableOpacity style={styles.warnBtn} onPress={() => setStep('confirm')}>
                <Text style={styles.warnBtnText}>Confirm Delete Game</Text>
              </TouchableOpacity>
            </>
          )}

          {step === 'confirm' && (
            <>
              <Text style={styles.dangerText}>This action is permanent.</Text>
              <TouchableOpacity style={[styles.deleteBtn, loading && styles.btnDisabled]} onPress={handleDelete} disabled={loading}>
                {loading ? <ActivityIndicator color="#FFF" size="small" /> :
                  <Text style={styles.deleteBtnText}>DELETE GAME FOREVER</Text>}
              </TouchableOpacity>
            </>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}

          <PickerModal
            visible={showPicker}
            title="Select Game"
            options={games.map((g) => g.game_name)}
            selected={selected?.game_name ?? null}
            onSelect={(name) => {
              const g = games.find((gm) => gm.game_name === name);
              if (g) { setSelectedId(g.game_id); setStep('select'); setMsg(null); }
            }}
            onClose={() => setShowPicker(false)}
          />
        </>
      )}
    </View>
  );
}

// ── Delete Stat ───────────────────────────────────────────────────────────────
function DeleteStat({ jwt }: { jwt: string }) {
  const [stats, setStats] = useState<StatEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [step, setStep] = useState<'select' | 'confirm'>('select');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getRecentStats(jwt);
      setStats(data);
      setLoaded(true);
      setStep('select');
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setLoading(true);
    try {
      await deleteStats(jwt, selectedId);
      setMsg({ ok: true, text: `Stat ID ${selectedId} deleted.` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
      setLoading(false);
    }
  }

  const selected = stats.find((s) => s.stat_id === selectedId);
  const pickerOptions = stats.map((s) =>
    `(${s.stat_id}) ${s.game_name} — ${s.stat_type}: ${s.stat_value}`
  );

  return (
    <View style={styles.tabContent}>
      <Text style={styles.hint}>Delete individual stat entries (e.g. a single match).</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Stats' : 'Load Data for Deletion'}</Text>}
      </TouchableOpacity>

      {loaded && (
        <>
          <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowPicker(true)}>
            <Text style={[styles.selectorText, !selected && styles.placeholder]} numberOfLines={1}>
              {selected
                ? `(${selected.stat_id}) ${selected.game_name} — ${selected.stat_type}: ${selected.stat_value}`
                : '— Select entry —'}
            </Text>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>

          {selectedId && step === 'select' && (
            <>
              <Text style={styles.confirmHint}>
                Delete stat ID {selectedId} —{' '}
                <Text style={{ color: GOLD }}>
                  {selected?.game_name}: {selected?.stat_type} = {selected?.stat_value}
                </Text>?
              </Text>
              <TouchableOpacity style={styles.warnBtn} onPress={() => setStep('confirm')}>
                <Text style={styles.warnBtnText}>Confirm Delete</Text>
              </TouchableOpacity>
            </>
          )}

          {step === 'confirm' && (
            <TouchableOpacity style={[styles.deleteBtn, loading && styles.btnDisabled]} onPress={handleDelete} disabled={loading}>
              {loading ? <ActivityIndicator color="#FFF" size="small" /> :
                <Text style={styles.deleteBtnText}>DELETE STAT FOREVER</Text>}
            </TouchableOpacity>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}

          <PickerModal
            visible={showPicker}
            title="Select Entry"
            options={pickerOptions}
            selected={selected ? `(${selected.stat_id}) ${selected.game_name} — ${selected.stat_type}: ${selected.stat_value}` : null}
            onSelect={(label) => {
              const match = label.match(/^\((\d+)\)/);
              if (match) { setSelectedId(Number(match[1])); setStep('select'); setMsg(null); }
            }}
            onClose={() => setShowPicker(false)}
          />
        </>
      )}
    </View>
  );
}

// ── Main DeleteScreen ─────────────────────────────────────────────────────────
export function DeleteScreen() {
  const { user } = useAuth();
  const jwt = (user as { jwt?: string })?.jwt ?? '';
  const isTrusted = (user as { is_trusted?: boolean })?.is_trusted === true;
  const [subTab, setSubTab] = useState<SubTab>('player');

  if (!isTrusted) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.container}>
          <Text style={styles.heading}>Delete Data</Text>
          <View style={styles.guestCard}>
            <Text style={styles.guestTitle}>🔒 Trusted Access Required</Text>
            <Text style={styles.guestBody}>Contact the admin for delete access.</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text style={styles.heading}>Delete Data</Text>

        {/* Sub-tabs */}
        <View style={styles.subTabRow}>
          {(['player', 'game', 'stat'] as SubTab[]).map((t) => (
            <TouchableOpacity
              key={t}
              style={[styles.subTab, subTab === t && styles.subTabActive]}
              onPress={() => setSubTab(t)}
            >
              <Text style={[styles.subTabText, subTab === t && styles.subTabTextActive]}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Section title={`Delete ${subTab.charAt(0).toUpperCase() + subTab.slice(1)}`} />
        {subTab === 'player' && <DeletePlayer jwt={jwt} />}
        {subTab === 'game'   && <DeleteGame jwt={jwt} />}
        {subTab === 'stat'   && <DeleteStat jwt={jwt} />}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  container: { flex: 1, padding: 20 },
  scroll: { padding: 20, paddingBottom: 60 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 16 },
  section: {
    fontSize: 12, fontWeight: '700', color: '#888',
    marginTop: 16, marginBottom: 10,
    textTransform: 'uppercase', letterSpacing: 1,
  },
  hint: { fontSize: 13, color: '#666', marginBottom: 12 },
  warningText: { fontSize: 13, color: '#E57373', fontWeight: '600', marginBottom: 12 },
  confirmHint: { fontSize: 13, color: '#FFD54F', marginBottom: 10 },
  dangerText: { fontSize: 13, color: '#E57373', fontWeight: '700', marginBottom: 10 },
  subTabRow: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  subTab: {
    flex: 1, paddingVertical: 8, borderRadius: 8,
    backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, alignItems: 'center',
  },
  subTabActive: { backgroundColor: RED, borderColor: RED },
  subTabText: { color: '#888', fontSize: 13, fontWeight: '600' },
  subTabTextActive: { color: '#FFF' },
  tabContent: { marginTop: 4 },
  loadBtn: {
    borderWidth: 1, borderColor: BORDER, borderRadius: 8,
    padding: 12, alignItems: 'center', marginBottom: 12,
  },
  loadBtnText: { color: GOLD, fontSize: 14, fontWeight: '600' },
  selectorBtn: {
    backgroundColor: CARD, borderRadius: 8, padding: 12,
    borderWidth: 1, borderColor: BORDER, marginBottom: 12,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  selectorText: { color: '#FFF', fontSize: 15, flex: 1 },
  placeholder: { color: '#555' },
  arrow: { color: '#666', fontSize: 18 },
  warnBtn: {
    borderWidth: 1, borderColor: '#B7950B', borderRadius: 8,
    padding: 12, alignItems: 'center', marginBottom: 12,
  },
  warnBtnText: { color: '#FFD54F', fontSize: 14 },
  deleteBtn: {
    backgroundColor: RED, borderRadius: 8, padding: 12,
    alignItems: 'center', marginBottom: 12,
  },
  deleteBtnText: { color: '#FFF', fontWeight: '700', fontSize: 14 },
  btnDisabled: { opacity: 0.4 },
  feedback: { borderRadius: 8, padding: 12, marginTop: 8 },
  feedbackOk: { backgroundColor: 'rgba(76,175,80,0.15)', borderWidth: 1, borderColor: '#4CAF50' },
  feedbackErr: { backgroundColor: 'rgba(244,67,54,0.15)', borderWidth: 1, borderColor: '#F44336' },
  feedbackText: { color: '#CCC', fontSize: 13 },
  guestCard: {
    backgroundColor: 'rgba(202,138,4,0.12)', borderWidth: 1,
    borderColor: '#92400e', borderRadius: 10, padding: 16, marginTop: 8,
  },
  guestTitle: { color: '#fde68a', fontWeight: '700', fontSize: 15, marginBottom: 6 },
  guestBody: { color: '#fde68a', fontSize: 13 },
});
