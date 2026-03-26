import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, ActivityIndicator, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/useAuth';
import {
  getPlayers, getAllGames, getRecentStats,
  updatePlayer, updateGame, updateStats,
  type Player, type GameDetails, type StatEntry,
} from '@/api/stats';
import { PickerModal } from '@/components/PickerModal';
import { GENRES } from '@/lib/constants';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

type SubTab = 'player' | 'game' | 'stats';

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

// ── Edit Player ───────────────────────────────────────────────────────────────
function EditPlayer({ jwt }: { jwt: string }) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [newName, setNewName] = useState('');
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getPlayers(jwt);
      setPlayers(data);
      setLoaded(true);
      setConfirmed(false);
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      Alert.alert('Error', (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const selected = players.find((p) => p.player_id === selectedId);

  async function handleUpdate() {
    if (!selectedId || !newName.trim()) return;
    setLoading(true);
    try {
      await updatePlayer(jwt, selectedId, newName.trim());
      setMsg({ ok: true, text: `Renamed to "${newName.trim()}"` });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.tabContent}>
      <Text style={styles.hint}>Select a player profile to rename.</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Players' : 'Load Players to Edit'}</Text>}
      </TouchableOpacity>

      {loaded && (
        <>
          <TouchableOpacity
            style={styles.selectorBtn}
            onPress={() => setShowPicker(true)}
          >
            <Text style={[styles.selectorText, !selected && styles.placeholder]}>
              {selected ? selected.player_name : '— Select player —'}
            </Text>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>

          {selectedId && !confirmed && (
            <TouchableOpacity style={styles.confirmBtn} onPress={() => {
              setConfirmed(true);
              setNewName(selected?.player_name ?? '');
            }}>
              <Text style={styles.confirmBtnText}>Confirm Edit Player</Text>
            </TouchableOpacity>
          )}

          {confirmed && selected && (
            <View style={styles.editCard}>
              <Text style={styles.editCardLabel}>
                Editing: <Text style={{ color: GOLD }}>{selected.player_name}</Text>{' '}
                (ID: {selected.player_id})
              </Text>
              <Text style={styles.label}>New Player Name</Text>
              <TextInput
                style={styles.input}
                value={newName}
                onChangeText={setNewName}
                placeholder="Enter name…"
                placeholderTextColor="#555"
              />
              <TouchableOpacity
                style={[styles.updateBtn, (!newName.trim() || newName === selected.player_name) && styles.btnDisabled]}
                onPress={handleUpdate}
                disabled={!newName.trim() || newName === selected.player_name || loading}
              >
                <Text style={styles.updateBtnText}>Update Player Name</Text>
              </TouchableOpacity>
            </View>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </>
      )}

      <PickerModal
        visible={showPicker}
        title="Select Player"
        options={players.map((p) => p.player_name)}
        selected={selected?.player_name ?? ''}
        onSelect={(name) => {
          const p = players.find((pl) => pl.player_name === name);
          setSelectedId(p?.player_id ?? null);
          setConfirmed(false);
          setMsg(null);
        }}
        onClose={() => setShowPicker(false)}
      />
    </View>
  );
}

// ── Edit Game ─────────────────────────────────────────────────────────────────
function EditGame({ jwt }: { jwt: string }) {
  const [games, setGames] = useState<GameDetails[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [form, setForm] = useState({ game_name: '', game_series: '', game_genre: '', game_subgenre: '' });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showGamePicker, setShowGamePicker] = useState(false);
  const [showGenrePicker, setShowGenrePicker] = useState(false);
  const [showSubgenrePicker, setShowSubgenrePicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getAllGames(jwt);
      setGames(data);
      setLoaded(true);
      setConfirmed(false);
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      Alert.alert('Error', (e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function handleSelect(id: number) {
    setSelectedId(id);
    setConfirmed(false);
    setMsg(null);
    const g = games.find((g) => g.game_id === id);
    if (g) setForm({
      game_name: g.game_name ?? '',
      game_series: g.game_series ?? '',
      game_genre: g.game_genre ?? '',
      game_subgenre: g.game_subgenre ?? '',
    });
  }

  async function handleUpdate() {
    if (!selectedId) return;
    setLoading(true);
    try {
      await updateGame(jwt, selectedId, form);
      setMsg({ ok: true, text: 'Game updated successfully.' });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  const selected = games.find((g) => g.game_id === selectedId);
  const subgenreOptions = GENRES[form.game_genre] ?? [];

  return (
    <View style={styles.tabContent}>
      <Text style={styles.hint}>Select a game to edit its details.</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Games' : 'Load Games to Edit'}</Text>}
      </TouchableOpacity>

      {loaded && (
        <>
          <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowGamePicker(true)}>
            <Text style={[styles.selectorText, !selected && styles.placeholder]}>
              {selected ? selected.game_name : '— Select game —'}
            </Text>
            <Text style={styles.arrow}>›</Text>
          </TouchableOpacity>

          {selectedId && !confirmed && (
            <TouchableOpacity style={styles.confirmBtn} onPress={() => setConfirmed(true)}>
              <Text style={styles.confirmBtnText}>Confirm Edit Game</Text>
            </TouchableOpacity>
          )}

          {confirmed && selectedId && (
            <View style={styles.editCard}>
              <Text style={styles.editCardLabel}>
                Editing game ID: <Text style={{ color: GOLD }}>{selectedId}</Text>
              </Text>
              <Text style={styles.label}>Game Name</Text>
              <TextInput style={styles.input} value={form.game_name}
                onChangeText={(v) => setForm((f) => ({ ...f, game_name: v }))}
                placeholderTextColor="#555" />

              <Text style={styles.label}>Game Series</Text>
              <TextInput style={styles.input} value={form.game_series}
                onChangeText={(v) => setForm((f) => ({ ...f, game_series: v }))}
                placeholder="e.g. Call of Duty" placeholderTextColor="#555" />

              <Text style={styles.label}>Game Genre</Text>
              <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowGenrePicker(true)}>
                <Text style={[styles.selectorText, !form.game_genre && styles.placeholder]}>
                  {form.game_genre || '— Select genre —'}
                </Text>
                <Text style={styles.arrow}>›</Text>
              </TouchableOpacity>

              <Text style={styles.label}>Game Subgenre</Text>
              <TouchableOpacity style={styles.selectorBtn} onPress={() => setShowSubgenrePicker(true)}>
                <Text style={[styles.selectorText, !form.game_subgenre && styles.placeholder]}>
                  {form.game_subgenre || '— Select subgenre —'}
                </Text>
                <Text style={styles.arrow}>›</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.updateBtn} onPress={handleUpdate} disabled={loading}>
                <Text style={styles.updateBtnText}>Update Game Details</Text>
              </TouchableOpacity>
            </View>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </>
      )}

      <PickerModal visible={showGamePicker} title="Select Game"
        options={games.map((g) => g.game_name)}
        selected={selected?.game_name ?? ''}
        onSelect={(name) => { const g = games.find((g) => g.game_name === name); if (g) handleSelect(g.game_id); }}
        onClose={() => setShowGamePicker(false)} />
      <PickerModal visible={showGenrePicker} title="Game Genre"
        options={Object.keys(GENRES).filter((g) => g !== 'Select a Genre')}
        selected={form.game_genre}
        onSelect={(g) => setForm((f) => ({ ...f, game_genre: g, game_subgenre: '' }))}
        onClose={() => setShowGenrePicker(false)} />
      <PickerModal visible={showSubgenrePicker} title="Game Subgenre"
        options={subgenreOptions.filter((s) => s !== 'Select a Subgenre')}
        selected={form.game_subgenre}
        onSelect={(s) => setForm((f) => ({ ...f, game_subgenre: s }))}
        onClose={() => setShowSubgenrePicker(false)} />
    </View>
  );
}

// ── Edit Stats ────────────────────────────────────────────────────────────────
function EditStats({ jwt }: { jwt: string }) {
  const [stats, setStats] = useState<StatEntry[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [form, setForm] = useState<Partial<StatEntry>>({});
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await getRecentStats(jwt);
      setStats(data);
      setLoaded(true);
      setConfirmed(false);
      setSelectedId(null);
      setMsg(null);
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  function handleSelect(id: number) {
    setSelectedId(id);
    setConfirmed(false);
    const entry = stats.find((s) => s.stat_id === id);
    if (entry) setForm({ ...entry });
  }

  async function handleUpdate() {
    if (!selectedId) return;
    setLoading(true);
    try {
      await updateStats(jwt, selectedId, form);
      setMsg({ ok: true, text: 'Entry updated successfully.' });
      await load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setLoading(false);
    }
  }

  const selected = stats.find((s) => s.stat_id === selectedId);
  const pickerOptions = stats.map((s) =>
    `(${s.stat_id}) ${s.game_name} — ${s.stat_type}: ${s.stat_value}`
  );

  return (
    <View style={styles.tabContent}>
      <Text style={styles.hint}>Edit individual stat entries (e.g. a single match).</Text>
      <TouchableOpacity style={styles.loadBtn} onPress={load} disabled={loading}>
        {loading ? <ActivityIndicator color={GOLD} size="small" /> :
          <Text style={styles.loadBtnText}>{loaded ? 'Reload Stats' : 'Load Data for Editing'}</Text>}
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

          {selectedId && !confirmed && (
            <TouchableOpacity style={styles.confirmBtn} onPress={() => setConfirmed(true)}>
              <Text style={styles.confirmBtnText}>Confirm Edit Selection</Text>
            </TouchableOpacity>
          )}

          {confirmed && selected && (
            <View style={styles.editCard}>
              <Text style={styles.editCardLabel}>
                Editing: <Text style={{ color: GOLD }}>({selected.stat_id}) {selected.game_name} — {selected.stat_type}</Text>
              </Text>

              <Text style={styles.label}>Stat Type</Text>
              <TextInput style={styles.input} value={form.stat_type ?? ''}
                onChangeText={(v) => setForm((f) => ({ ...f, stat_type: v }))}
                placeholderTextColor="#555" />

              <Text style={styles.label}>Stat Value</Text>
              <TextInput style={styles.input}
                value={String(form.stat_value ?? '')}
                onChangeText={(v) => setForm((f) => ({ ...f, stat_value: parseInt(v) || 0 }))}
                keyboardType="numeric" placeholderTextColor="#555" />

              <Text style={styles.label}>Game Mode</Text>
              <TextInput style={styles.input} value={form.game_mode ?? ''}
                onChangeText={(v) => setForm((f) => ({ ...f, game_mode: v }))}
                placeholder="e.g. Warzone" placeholderTextColor="#555" />

              <Text style={styles.label}>Game Level / Wave</Text>
              <TextInput style={styles.input}
                value={String(form.game_level ?? '')}
                onChangeText={(v) => setForm((f) => ({ ...f, game_level: parseInt(v) || 0 }))}
                keyboardType="numeric" placeholder="0" placeholderTextColor="#555" />

              <TouchableOpacity style={styles.updateBtn} onPress={handleUpdate} disabled={loading}>
                <Text style={styles.updateBtnText}>Update Entry</Text>
              </TouchableOpacity>
            </View>
          )}

          {msg && <Feedback ok={msg.ok} text={msg.text} />}
        </>
      )}

      <PickerModal visible={showPicker} title="Select Entry"
        options={pickerOptions}
        selected={selected ? `(${selected.stat_id}) ${selected.game_name} — ${selected.stat_type}: ${selected.stat_value}` : ''}
        onSelect={(label) => {
          const match = label.match(/^\((\d+)\)/);
          if (match) handleSelect(parseInt(match[1]));
        }}
        onClose={() => setShowPicker(false)} />
    </View>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────
export function EditScreen() {
  const { token, isTrusted } = useAuth();
  const jwt = token ?? '';
  const [subTab, setSubTab] = useState<SubTab>('player');

  if (!isTrusted) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.container}>
          <Text style={styles.heading}>Edit Data</Text>
          <View style={styles.guestCard}>
            <Text style={styles.guestTitle}>🔒 Trusted Access Required</Text>
            <Text style={styles.guestBody}>Contact the admin for edit access.</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text style={styles.heading}>Edit Data</Text>

        {/* Sub-tabs */}
        <View style={styles.subTabRow}>
          {(['player', 'game', 'stats'] as SubTab[]).map((t) => (
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

        <Section title={`Edit ${subTab.charAt(0).toUpperCase() + subTab.slice(1)}`} />
        {subTab === 'player' && <EditPlayer jwt={jwt} />}
        {subTab === 'game'   && <EditGame jwt={jwt} />}
        {subTab === 'stats'  && <EditStats jwt={jwt} />}
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
  label: { fontSize: 13, color: '#AAA', marginBottom: 6 },
  hint: { fontSize: 13, color: '#666', marginBottom: 12 },
  input: {
    backgroundColor: CARD, borderRadius: 8, padding: 12,
    fontSize: 15, borderWidth: 1, borderColor: BORDER, marginBottom: 12, color: '#FFF',
  },
  subTabRow: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  subTab: {
    flex: 1, paddingVertical: 8, borderRadius: 8,
    backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, alignItems: 'center',
  },
  subTabActive: { backgroundColor: GOLD, borderColor: GOLD },
  subTabText: { color: '#888', fontSize: 13, fontWeight: '600' },
  subTabTextActive: { color: '#000' },
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
  confirmBtn: {
    borderWidth: 1, borderColor: BORDER, borderRadius: 8,
    padding: 12, alignItems: 'center', marginBottom: 12,
  },
  confirmBtnText: { color: '#AAA', fontSize: 14 },
  editCard: {
    backgroundColor: CARD, borderRadius: 10, borderWidth: 1,
    borderColor: BORDER, padding: 16, marginBottom: 12,
  },
  editCardLabel: { color: '#CCC', fontSize: 13, marginBottom: 14 },
  updateBtn: {
    backgroundColor: GOLD, borderRadius: 8, padding: 12,
    alignItems: 'center', marginTop: 4,
  },
  updateBtnText: { color: '#000', fontWeight: '700', fontSize: 14 },
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
