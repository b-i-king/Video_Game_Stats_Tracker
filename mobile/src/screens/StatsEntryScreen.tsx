import { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, Alert, ActivityIndicator, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/auth/useAuth';
import {
  getPlayers, getFranchises, getInstallments,
  getGameRanks, getGameModes, getGameStatTypes,
  getObsStatus, setObsActive, setLiveState,
  getRecentStats, addStats,
  type Player, type Installment, type StatEntry, type StatRow,
} from '@/api/stats';
import { PickerModal } from '@/components/PickerModal';
import { sendLocalNotification } from '@/notifications/pushNotifications';
import {
  GENRES, CREDIT_STYLE_OPTIONS,
  MATCH_TYPES, WIN_LOSS_OPTIONS, PARTY_SIZES,
  DIFFICULTY_OPTIONS, INPUT_DEVICES, PLATFORMS,
} from '@/lib/constants';

const GOLD = '#C4A035';
const BG = '#111111';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';

// ── Shared primitives ─────────────────────────────────────────────────────────

function Section({ title }: { title: string }) {
  return <Text style={styles.section}>{title}</Text>;
}

function Label({ children }: { children: string }) {
  return <Text style={styles.label}>{children}</Text>;
}

/** Tappable row that opens a PickerModal — used for all dropdown-style fields */
function SelectorBtn({
  value, placeholder, onPress,
}: { value: string; placeholder: string; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.selectorBtn} onPress={onPress} activeOpacity={0.7}>
      <Text style={[styles.selectorText, !value && styles.selectorPlaceholder]}>
        {value || placeholder}
      </Text>
      <Text style={styles.arrow}>›</Text>
    </TouchableOpacity>
  );
}

/** Horizontal row of pill chips for small fixed option sets */
function ChipRow<T extends string>({
  options, value, onSelect, labelFn,
}: {
  options: readonly T[];
  value: T;
  onSelect: (v: T) => void;
  labelFn?: (v: T) => string;
}) {
  return (
    <View style={styles.chipRow}>
      {options.map((opt) => (
        <TouchableOpacity
          key={opt}
          style={[styles.chip, value === opt && styles.chipActive]}
          onPress={() => onSelect(opt)}
        >
          <Text style={[styles.chipText, value === opt && styles.chipTextActive]}>
            {labelFn ? labelFn(opt) : opt || 'N/A'}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}

function SwitchRow({
  label, hint, value, onChange,
}: { label: string; hint?: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={styles.switchRow}>
      <View style={{ flex: 1, marginRight: 12 }}>
        <Text style={styles.label}>{label}</Text>
        {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: '#333', true: GOLD }}
        thumbColor={value ? '#000' : '#888'}
      />
    </View>
  );
}

// ── Screen ────────────────────────────────────────────────────────────────────

interface StatInput { type: string; value: string; }

export function StatsEntryScreen() {
  const { token, isTrusted } = useAuth();
  const jwt = token ?? '';

  // ── Player ────────────────────────────────────────────────────────────────
  const [players, setPlayers] = useState<Player[]>([]);
  const [playerName, setPlayerName] = useState('');
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [isNewPlayer, setIsNewPlayer] = useState(false);
  const [newPlayerName, setNewPlayerName] = useState('');
  const [playerConfirmed, setPlayerConfirmed] = useState(false);
  const [showPlayerPicker, setShowPlayerPicker] = useState(false);

  // ── Game selection ────────────────────────────────────────────────────────
  const [franchises, setFranchises] = useState<string[]>([]);
  const [selectedFranchise, setSelectedFranchise] = useState('');
  const [isNewFranchise, setIsNewFranchise] = useState(false);
  const [newFranchiseName, setNewFranchiseName] = useState('');
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [selectedInstallment, setSelectedInstallment] = useState('');
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [isNewInstallment, setIsNewInstallment] = useState(false);
  const [newInstallmentName, setNewInstallmentName] = useState('');
  const [gameGenre, setGameGenre] = useState('Select a Genre');
  const [gameSubgenre, setGameSubgenre] = useState('Select a Subgenre');
  const [showFranchisePicker, setShowFranchisePicker] = useState(false);
  const [showInstallmentPicker, setShowInstallmentPicker] = useState(false);
  const [showGenrePicker, setShowGenrePicker] = useState(false);
  const [showSubgenrePicker, setShowSubgenrePicker] = useState(false);

  // ── Credit style ──────────────────────────────────────────────────────────
  const [creditStyle, setCreditStyle] = useState('S/O (Shoutout)');
  const [showCreditPicker, setShowCreditPicker] = useState(false);

  // ── OBS / Streaming / Queue ───────────────────────────────────────────────
  const [isLive, setIsLive] = useState(false);
  const [obsActive, setObsActiveState] = useState(false);
  const [queueMode, setQueueMode] = useState(false);
  const [liveSetMsg, setLiveSetMsg] = useState('');

  // ── Rank ──────────────────────────────────────────────────────────────────
  const [isRanked, setIsRanked] = useState(false);
  const [gameRanks, setGameRanks] = useState<string[]>([]);
  const [preRank, setPreRank] = useState('Unranked');
  const [postRank, setPostRank] = useState('Unranked');
  const [preRankCustom, setPreRankCustom] = useState('');
  const [postRankCustom, setPostRankCustom] = useState('');
  const [showPreRankPicker, setShowPreRankPicker] = useState(false);
  const [showPostRankPicker, setShowPostRankPicker] = useState(false);

  // ── Game context ──────────────────────────────────────────────────────────
  const [gameModes, setGameModes] = useState<string[]>(['Main']);
  const [gameMode, setGameMode] = useState('Main');
  const [gameModeCustom, setGameModeCustom] = useState('');
  const [prevStatTypes, setPrevStatTypes] = useState<string[]>([]);
  const [showGameModePicker, setShowGameModePicker] = useState(false);

  // ── Match details ─────────────────────────────────────────────────────────
  const [matchType, setMatchType] = useState<(typeof MATCH_TYPES)[number]>('Solo');
  const [winLoss, setWinLoss] = useState<(typeof WIN_LOSS_OPTIONS)[number]>('');
  const [partySize, setPartySize] = useState<(typeof PARTY_SIZES)[number]>('1');
  const [gameLevel, setGameLevel] = useState('');
  const [difficulty, setDifficulty] = useState<(typeof DIFFICULTY_OPTIONS)[number]>('');
  const [inputDevice, setInputDevice] = useState<(typeof INPUT_DEVICES)[number]>('Controller');
  const [platform, setPlatform] = useState<(typeof PLATFORMS)[number]>('PC');
  const [overtime, setOvertime] = useState(false);
  const [firstSession, setFirstSession] = useState(true);

  // ── Stats rows (1–3) ──────────────────────────────────────────────────────
  const [statRows, setStatRows] = useState<StatInput[]>([{ type: '', value: '' }]);

  // ── Submit ────────────────────────────────────────────────────────────────
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitMsg, setSubmitMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // ── Today's stats ─────────────────────────────────────────────────────────
  const [todayStats, setTodayStats] = useState<StatEntry[]>([]);

  // ── Derived values ────────────────────────────────────────────────────────
  const finalPlayerName = isNewPlayer ? newPlayerName.trim() : playerName;
  const finalFranchise = isNewFranchise ? newFranchiseName.trim() : selectedFranchise;
  const finalInstallment = isNewInstallment
    ? newInstallmentName.trim() || null
    : selectedInstallment || null;
  const finalGameMode = gameModeCustom.trim() || gameMode || 'Main';
  const finalPreRank = preRankCustom.trim() || preRank;
  const finalPostRank = postRankCustom.trim() || postRank;
  const filledStats = statRows.filter((r) => r.type.trim());
  const rankOptions = ['Unranked', ...gameRanks, '(Enter Custom)'];
  const franchiseOptions = [...franchises, '(Enter New Franchise)'];
  const installmentOptions = [
    ...installments.map((i) => i.installment_name),
    '(Add New Installment)',
  ];
  const gameModeOptions = [...gameModes, '(Enter Custom)'];

  // ── Load on mount ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!jwt || !isTrusted) return;
    getPlayers(jwt).then(setPlayers).catch(() =>
      Alert.alert('Connection Error', 'Could not load players. Check your connection and try again.')
    );
    getFranchises(jwt).then(setFranchises).catch(() =>
      Alert.alert('Connection Error', 'Could not load games. Check your connection and try again.')
    );
    getObsStatus(jwt).then((d) => setObsActiveState(d.obs_active)).catch(() => {/* non-critical */});
  }, [jwt, isTrusted]);

  // ── Installments when franchise changes ───────────────────────────────────
  useEffect(() => {
    if (!jwt || !selectedFranchise || isNewFranchise) { setInstallments([]); return; }
    getInstallments(jwt, selectedFranchise).then(setInstallments).catch(() =>
      Alert.alert('Error', `Could not load installments for "${selectedFranchise}".`)
    );
  }, [jwt, selectedFranchise, isNewFranchise]);

  // ── Game-specific data when installment selected ──────────────────────────
  useEffect(() => {
    if (!jwt || !selectedGameId || isNewInstallment) {
      setGameRanks([]); setGameModes(['Main']); setGameMode('Main');
      setGameModeCustom(''); setPrevStatTypes([]);
      return;
    }
    setGameMode('Main'); setGameModeCustom('');
    // Non-critical — fall back to empty/defaults silently
    getGameRanks(jwt, selectedGameId).then(setGameRanks).catch(() => setGameRanks([]));
    getGameModes(jwt, selectedGameId)
      .then((m) => setGameModes(m.length ? m : ['Main']))
      .catch(() => setGameModes(['Main']));
    getGameStatTypes(jwt, selectedGameId).then(setPrevStatTypes).catch(() => setPrevStatTypes([]));
  }, [jwt, selectedGameId, isNewInstallment]);

  // ── Today's stats loader ──────────────────────────────────────────────────
  const loadTodayStats = useCallback(async () => {
    if (!jwt) return;
    try {
      const all = await getRecentStats(jwt);
      // Use device local timezone, not UTC, to determine "today"
      const today = new Date().toLocaleDateString("en-CA"); // YYYY-MM-DD in local tz
      setTodayStats(all.filter((s) => {
        const utc = s.played_at.includes("T") ? s.played_at : s.played_at.replace(" ", "T");
        const localDate = new Date(utc.endsWith("Z") ? utc : utc + "Z").toLocaleDateString("en-CA");
        return localDate === today;
      }));
    } catch { /* ignore */ }
  }, [jwt]);

  useEffect(() => { loadTodayStats(); }, [loadTodayStats]);

  // ── OBS handlers ─────────────────────────────────────────────────────────
  async function handleObsToggle(val: boolean) {
    setObsActiveState(val);
    try { await setObsActive(jwt, val); } catch { /* ignore */ }
  }

  async function handleSetLiveGame() {
    if (playerId === null || selectedGameId === null) return;
    try {
      await setLiveState(jwt, playerId, selectedGameId);
      setLiveSetMsg('✅ OBS dashboard updated');
    } catch {
      setLiveSetMsg('❌ Failed to update OBS');
    }
    setTimeout(() => setLiveSetMsg(''), 3000);
  }

  // ── Franchise / installment helpers ──────────────────────────────────────
  function handleFranchiseSelect(val: string) {
    if (val === '(Enter New Franchise)') {
      setIsNewFranchise(true);
      setSelectedFranchise('');
    } else {
      setIsNewFranchise(false);
      setSelectedFranchise(val);
    }
    setSelectedInstallment(''); setSelectedGameId(null);
    setIsNewInstallment(false); setNewInstallmentName('');
  }

  function handleInstallmentSelect(val: string) {
    if (val === '(Add New Installment)') {
      setIsNewInstallment(true); setSelectedInstallment(''); setSelectedGameId(null);
    } else {
      setIsNewInstallment(false); setSelectedInstallment(val);
      const found = installments.find((i) => i.installment_name === val);
      setSelectedGameId(found?.game_id ?? null);
    }
  }

  function handleGameModeSelect(val: string) {
    if (val === '(Enter Custom)') {
      setGameMode('(Enter Custom)'); setGameModeCustom('');
    } else {
      setGameMode(val); setGameModeCustom('');
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!confirmed) {
      Alert.alert('Confirm first', 'Toggle the confirmation switch before submitting.');
      return;
    }
    if (!finalPlayerName || !finalFranchise || filledStats.length === 0) {
      Alert.alert('Missing fields', 'Player name, game, and at least one stat are required.');
      return;
    }

    const statsPayload: StatRow[] = filledStats.map((s) => ({
      stat_type: s.type.trim(),
      stat_value: parseFloat(s.value) || 0,
      game_mode: finalGameMode,
      solo_mode: matchType === 'Solo' ? 1 : 0,
      party_size: partySize,
      game_level: gameLevel ? parseInt(gameLevel, 10) : null,
      win: winLoss === 'Win' ? 1 : winLoss === 'Loss' ? 0 : null,
      ranked: isRanked ? 1 : 0,
      pre_match_rank_value: isRanked ? finalPreRank : null,
      post_match_rank_value: isRanked ? finalPostRank : null,
      overtime: overtime ? 1 : 0,
      difficulty: difficulty || null,
      input_device: inputDevice,
      platform,
      first_session_of_day: firstSession ? 1 : 0,
      was_streaming: isLive ? 1 : 0,
    }));

    setLoading(true);
    setSubmitMsg(null);
    try {
      const result = await addStats(jwt, {
        player_name: finalPlayerName,
        game_name: finalFranchise,
        game_installment: finalInstallment,
        game_genre: isNewInstallment ? gameGenre : null,
        game_subgenre: isNewInstallment ? gameSubgenre : null,
        stats: statsPayload,
        is_live: isLive,
        queue_mode: queueMode,
        credit_style: CREDIT_STYLE_OPTIONS[creditStyle] ?? 'shoutout',
      });
      setSubmitMsg({ ok: true, text: result.message });
      setConfirmed(false);
      setStatRows((rows) => rows.map((r) => ({ ...r, value: '' })));
      loadTodayStats();
      await sendLocalNotification(
        'Stats posted!',
        `${filledStats[0]?.type}: ${filledStats[0]?.value}`
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Submit failed';
      setSubmitMsg({ ok: false, text: msg });
    } finally {
      setLoading(false);
    }
  }

  // ── Guest view ────────────────────────────────────────────────────────────
  if (!isTrusted) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.guestContainer}>
          <Text style={styles.heading}>Log Stats</Text>
          <View style={styles.guestCard}>
            <Text style={styles.guestTitle}>🔒 Read-Only Preview</Text>
            <Text style={styles.guestBody}>
              You are signed in as a Registered Guest. Contact the admin for full access.
            </Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // ── Full form ─────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text style={styles.heading}>Log Stats</Text>

        {/* ── Player ────────────────────────────────────────────────────── */}
        <Section title="Player" />

        {!playerConfirmed ? (
          <>
            {!isNewPlayer ? (
              <>
                <Label>Player Name</Label>
                <SelectorBtn
                  value={playerName}
                  placeholder="— Select Player —"
                  onPress={() => setShowPlayerPicker(true)}
                />
                <TouchableOpacity onPress={() => { setIsNewPlayer(true); setPlayerName(''); setPlayerId(null); }}>
                  <Text style={styles.linkText}>+ Add new player</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <Label>New Player Name</Label>
                <TextInput
                  style={styles.input}
                  value={newPlayerName}
                  onChangeText={setNewPlayerName}
                  placeholder="Enter name…"
                  placeholderTextColor="#555"                />
                <TouchableOpacity onPress={() => { setIsNewPlayer(false); setNewPlayerName(''); }}>
                  <Text style={styles.linkText}>← Back to existing players</Text>
                </TouchableOpacity>
              </>
            )}
            <TouchableOpacity
              style={[styles.proceedBtn, !finalPlayerName && styles.btnDisabled]}
              disabled={!finalPlayerName}
              onPress={() => setPlayerConfirmed(true)}
            >
              <Text style={styles.proceedBtnText}>Proceed</Text>
            </TouchableOpacity>
          </>
        ) : (
          <View style={styles.confirmedRow}>
            <Text style={styles.confirmedText}>
              Player: <Text style={{ color: GOLD, fontWeight: '700' }}>{finalPlayerName}</Text>
            </Text>
            <TouchableOpacity onPress={() => {
              setPlayerConfirmed(false); setPlayerName(''); setPlayerId(null);
              setNewPlayerName(''); setIsNewPlayer(false);
            }}>
              <Text style={styles.linkText}>Change</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* ── Game Selection ────────────────────────────────────────────── */}
        {playerConfirmed && (
          <>
            <Section title="Game Selection" />

            <Label>Game Name (Franchise)</Label>
            {!isNewFranchise ? (
              <SelectorBtn
                value={selectedFranchise}
                placeholder="— Select Franchise —"
                onPress={() => setShowFranchisePicker(true)}
              />
            ) : (
              <>
                <TextInput
                  style={styles.input}
                  value={newFranchiseName}
                  onChangeText={setNewFranchiseName}
                  placeholder="New franchise name…"
                  placeholderTextColor="#555"                />
                <TouchableOpacity onPress={() => { setIsNewFranchise(false); setNewFranchiseName(''); }}>
                  <Text style={styles.linkText}>← Back to existing</Text>
                </TouchableOpacity>
              </>
            )}

            {/* Installment */}
            {!isNewFranchise && selectedFranchise ? (
              <>
                <Label>Game Installment</Label>
                {!isNewInstallment ? (
                  <SelectorBtn
                    value={selectedInstallment}
                    placeholder="— Select Installment —"
                    onPress={() => setShowInstallmentPicker(true)}
                  />
                ) : (
                  <>
                    <TextInput
                      style={styles.input}
                      value={newInstallmentName}
                      onChangeText={setNewInstallmentName}
                      placeholder="New installment name…"
                      placeholderTextColor="#555"
                    />
                    <TouchableOpacity onPress={() => { setIsNewInstallment(false); setNewInstallmentName(''); setSelectedGameId(null); }}>
                      <Text style={styles.linkText}>← Back to existing</Text>
                    </TouchableOpacity>
                  </>
                )}
              </>
            ) : null}

            {/* Genre / subgenre for new games */}
            {isNewInstallment && (
              <>
                <Label>Game Genre *</Label>
                <SelectorBtn
                  value={gameGenre === 'Select a Genre' ? '' : gameGenre}
                  placeholder="Select a Genre"
                  onPress={() => setShowGenrePicker(true)}
                />
                <Label>Game Subgenre *</Label>
                <SelectorBtn
                  value={gameSubgenre === 'Select a Subgenre' ? '' : gameSubgenre}
                  placeholder="Select a Subgenre"
                  onPress={() => setShowSubgenrePicker(true)}
                />
              </>
            )}

            {/* ── Credit Style ──────────────────────────────────────────── */}
            <Section title="Credit Style" />
            <Label>How the game is credited in captions</Label>
            <SelectorBtn
              value={creditStyle}
              placeholder="— Select Style —"
              onPress={() => setShowCreditPicker(true)}
            />

            {/* ── Streaming / OBS ───────────────────────────────────────── */}
            <Section title="Streaming Status" />
            <SwitchRow
              label="🔴 Live Now"
              hint="Posts will include #Live hashtags and stream links"
              value={isLive}
              onChange={setIsLive}
            />
            <SwitchRow
              label="🎬 OBS Active"
              hint="Activates overlay and stat ticker for recording/streaming"
              value={obsActive}
              onChange={handleObsToggle}
            />
            <SwitchRow
              label="📥 Queue Mode"
              hint="Posts are queued instead of sent immediately"
              value={queueMode}
              onChange={setQueueMode}
            />

            {/* Set Live Game for OBS */}
            {playerId !== null && selectedGameId !== null && (
              <View style={styles.setLiveRow}>
                <TouchableOpacity style={styles.setLiveBtn} onPress={handleSetLiveGame}>
                  <Text style={styles.setLiveBtnText}>📺 Set as Live Game for OBS</Text>
                </TouchableOpacity>
                {liveSetMsg ? <Text style={styles.hint}>{liveSetMsg}</Text> : null}
              </View>
            )}

            {/* ── Rank Information ──────────────────────────────────────── */}
            <Section title="Rank Information" />
            <SwitchRow label="Ranked?" value={isRanked} onChange={setIsRanked} />

            {isRanked && (
              <>
                <Label>Pre-match Rank</Label>
                {gameRanks.length > 0 ? (
                  <>
                    <SelectorBtn
                      value={preRank === '(Enter Custom)' ? preRankCustom : preRank}
                      placeholder="Select rank"
                      onPress={() => setShowPreRankPicker(true)}
                    />
                    {preRank === '(Enter Custom)' && (
                      <TextInput
                        style={[styles.input, { marginTop: 6 }]}
                        value={preRankCustom}
                        onChangeText={setPreRankCustom}
                        placeholder="Type rank…"
                        placeholderTextColor="#555"
                      />
                    )}
                  </>
                ) : (
                  <TextInput
                    style={styles.input}
                    value={preRankCustom}
                    onChangeText={setPreRankCustom}
                    placeholder="e.g. Gold II"
                    placeholderTextColor="#555"
                  />
                )}

                <Label>Post-match Rank</Label>
                {gameRanks.length > 0 ? (
                  <>
                    <SelectorBtn
                      value={postRank === '(Enter Custom)' ? postRankCustom : postRank}
                      placeholder="Select rank"
                      onPress={() => setShowPostRankPicker(true)}
                    />
                    {postRank === '(Enter Custom)' && (
                      <TextInput
                        style={[styles.input, { marginTop: 6 }]}
                        value={postRankCustom}
                        onChangeText={setPostRankCustom}
                        placeholder="Type rank…"
                        placeholderTextColor="#555"
                      />
                    )}
                  </>
                ) : (
                  <TextInput
                    style={styles.input}
                    value={postRankCustom}
                    onChangeText={setPostRankCustom}
                    placeholder="e.g. Gold III"
                    placeholderTextColor="#555"
                  />
                )}
              </>
            )}

            {/* ── Stats ─────────────────────────────────────────────────── */}
            <Section title={`Stats — ${finalPlayerName} | ${finalFranchise || '…'}`} />

            {/* Previously used stat types as tap-to-fill chips */}
            {prevStatTypes.length > 0 && (
              <View style={styles.prevTypesRow}>
                <Text style={styles.prevTypesLabel}>Previously used:</Text>
                <View style={styles.chipRow}>
                  {prevStatTypes.map((t) => (
                    <TouchableOpacity
                      key={t}
                      style={styles.chip}
                      onPress={() => {
                        const emptyIdx = statRows.findIndex((r) => !r.type.trim());
                        if (emptyIdx !== -1) {
                          setStatRows((rows) =>
                            rows.map((r, i) => (i === emptyIdx ? { ...r, type: t } : r))
                          );
                        }
                      }}
                    >
                      <Text style={styles.chipText}>{t}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            )}

            {statRows.map((row, i) => (
              <View key={i} style={styles.statRow}>
                <View style={{ flex: 2, marginRight: 8 }}>
                  <Label>{`Stat ${i + 1} Type${i > 0 ? ' (opt)' : ''}`}</Label>
                  <TextInput
                    style={styles.input}
                    value={row.type}
                    onChangeText={(v) =>
                      setStatRows((rows) => rows.map((r, idx) => (idx === i ? { ...r, type: v } : r)))
                    }
                    placeholder="e.g. Kills"
                    placeholderTextColor="#555"
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Label>Value</Label>
                  <TextInput
                    style={styles.input}
                    value={row.value}
                    onChangeText={(v) =>
                      setStatRows((rows) => rows.map((r, idx) => (idx === i ? { ...r, value: v } : r)))
                    }
                    keyboardType="numeric"
                    placeholder="0"
                    placeholderTextColor="#555"
                  />
                </View>
              </View>
            ))}

            <View style={styles.statControlRow}>
              <TouchableOpacity
                style={[styles.chip, statRows.length >= 10 && styles.chipDisabled]}
                onPress={() => {
                  if (statRows.length < 10) setStatRows((r) => [...r, { type: '', value: '' }]);
                }}
                disabled={statRows.length >= 10}
              >
                <Text style={styles.chipText}>➕ Add Row</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.chip, statRows.length <= 1 && styles.chipDisabled]}
                onPress={() => {
                  if (statRows.length > 1) setStatRows((r) => r.slice(0, -1));
                }}
                disabled={statRows.length <= 1}
              >
                <Text style={styles.chipText}>➖ Remove Row</Text>
              </TouchableOpacity>
            </View>

            {/* ── Match Context ─────────────────────────────────────────── */}
            <Section title="Match Context" />

            {/* Game Mode */}
            <Label>Game Mode</Label>
            {isNewInstallment || !selectedGameId ? (
              <TextInput
                style={styles.input}
                value={gameMode === 'Main' ? '' : gameMode}
                onChangeText={(v) => setGameMode(v || 'Main')}
                placeholder="e.g. Multiplayer (default: Main)"
                placeholderTextColor="#555"
              />
            ) : (
              <>
                <SelectorBtn
                  value={gameMode === '(Enter Custom)' ? 'Custom…' : gameMode}
                  placeholder="— Select Mode —"
                  onPress={() => setShowGameModePicker(true)}
                />
                {gameMode === '(Enter Custom)' && (
                  <TextInput
                    style={[styles.input, { marginTop: 6 }]}
                    value={gameModeCustom}
                    onChangeText={setGameModeCustom}
                    placeholder="Custom game mode…"
                    placeholderTextColor="#555"
                    autoFocus
                  />
                )}
              </>
            )}

            <Label>Match Type</Label>
            <ChipRow options={MATCH_TYPES} value={matchType} onSelect={setMatchType} />

            <Label>Win / Loss</Label>
            <ChipRow
              options={WIN_LOSS_OPTIONS}
              value={winLoss}
              onSelect={setWinLoss}
              labelFn={(v) => v || 'N/A'}
            />

            <Label>Party Size</Label>
            <ChipRow options={PARTY_SIZES} value={partySize} onSelect={setPartySize} />

            <Label>Game Level / Wave (optional)</Label>
            <TextInput
              style={styles.input}
              value={gameLevel}
              onChangeText={setGameLevel}
              keyboardType="numeric"
              placeholder="0"
              placeholderTextColor="#555"
            />

            <Label>Difficulty</Label>
            <ChipRow
              options={DIFFICULTY_OPTIONS}
              value={difficulty}
              onSelect={setDifficulty}
              labelFn={(v) => v || 'N/A'}
            />

            <Label>Input Device</Label>
            <ChipRow options={INPUT_DEVICES} value={inputDevice} onSelect={setInputDevice} />

            <Label>Platform</Label>
            <ChipRow options={PLATFORMS} value={platform} onSelect={setPlatform} />

            <SwitchRow label="Overtime / Sudden Death" value={overtime} onChange={setOvertime} />
            <SwitchRow label="First Session of Day" value={firstSession} onChange={setFirstSession} />

            {/* ── Confirm + Submit ──────────────────────────────────────── */}
            <Section title="Submit" />
            <SwitchRow
              label="✅ I have reviewed my stats and they are correct"
              value={confirmed}
              onChange={setConfirmed}
            />

            <TouchableOpacity
              style={[styles.submitBtn, (!confirmed || loading || filledStats.length === 0) && styles.btnDisabled]}
              onPress={handleSubmit}
              disabled={!confirmed || loading || filledStats.length === 0}
            >
              {loading ? (
                <ActivityIndicator color="#000" />
              ) : (
                <Text style={styles.submitText}>Submit Stats</Text>
              )}
            </TouchableOpacity>

            {submitMsg && (
              <View style={[
                styles.resultBanner,
                submitMsg.ok ? styles.resultOk : styles.resultErr,
              ]}>
                <Text style={styles.resultText}>{submitMsg.text}</Text>
              </View>
            )}

            {/* ── Today's Stats ─────────────────────────────────────────── */}
            {todayStats.length > 0 && (
              <>
                <Section title={`Today's Entries (${todayStats.length})`} />
                {todayStats.map((s) => (
                  <View key={s.stat_id} style={styles.todayRow}>
                    <Text style={styles.todayGame} numberOfLines={1}>{s.game_name}</Text>
                    <Text style={styles.todayType}>{s.stat_type}</Text>
                    <Text style={styles.todayValue}>{s.stat_value.toLocaleString()}</Text>
                  </View>
                ))}
              </>
            )}
          </>
        )}

        {/* ── Picker Modals ─────────────────────────────────────────────── */}
        <PickerModal
          visible={showPlayerPicker}
          title="Select Player"
          options={players.map((p) => p.player_name)}
          selected={playerName}
          onSelect={(name) => {
            const p = players.find((pl) => pl.player_name === name);
            setPlayerName(p?.player_name ?? name);
            setPlayerId(p?.player_id ?? null);
          }}
          onClose={() => setShowPlayerPicker(false)}
        />
        <PickerModal
          visible={showFranchisePicker}
          title="Select Franchise"
          options={franchiseOptions}
          selected={selectedFranchise}
          onSelect={handleFranchiseSelect}
          onClose={() => setShowFranchisePicker(false)}
        />
        <PickerModal
          visible={showInstallmentPicker}
          title="Select Installment"
          options={installmentOptions}
          selected={selectedInstallment}
          onSelect={handleInstallmentSelect}
          onClose={() => setShowInstallmentPicker(false)}
        />
        <PickerModal
          visible={showGenrePicker}
          title="Game Genre"
          options={Object.keys(GENRES).filter((g) => g !== 'Select a Genre')}
          selected={gameGenre}
          onSelect={(g) => { setGameGenre(g); setGameSubgenre('Select a Subgenre'); }}
          onClose={() => setShowGenrePicker(false)}
        />
        <PickerModal
          visible={showSubgenrePicker}
          title="Game Subgenre"
          options={(GENRES[gameGenre] ?? ['Select a Subgenre']).filter((s) => s !== 'Select a Subgenre')}
          selected={gameSubgenre}
          onSelect={setGameSubgenre}
          onClose={() => setShowSubgenrePicker(false)}
        />
        <PickerModal
          visible={showCreditPicker}
          title="Credit Style"
          options={Object.keys(CREDIT_STYLE_OPTIONS)}
          selected={creditStyle}
          onSelect={setCreditStyle}
          onClose={() => setShowCreditPicker(false)}
        />
        <PickerModal
          visible={showPreRankPicker}
          title="Pre-match Rank"
          options={rankOptions}
          selected={preRank}
          onSelect={setPreRank}
          onClose={() => setShowPreRankPicker(false)}
        />
        <PickerModal
          visible={showPostRankPicker}
          title="Post-match Rank"
          options={rankOptions}
          selected={postRank}
          onSelect={setPostRank}
          onClose={() => setShowPostRankPicker(false)}
        />
        <PickerModal
          visible={showGameModePicker}
          title="Game Mode"
          options={gameModeOptions}
          selected={gameMode}
          onSelect={handleGameModeSelect}
          onClose={() => setShowGameModePicker(false)}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: BG },
  scroll: { padding: 20, paddingBottom: 60 },
  heading: { fontSize: 24, fontWeight: '700', color: GOLD, marginBottom: 20 },
  section: {
    fontSize: 12, fontWeight: '700', color: '#888',
    marginTop: 24, marginBottom: 10,
    textTransform: 'uppercase', letterSpacing: 1,
  },
  label: { fontSize: 13, color: '#AAA', marginBottom: 6 },
  hint: { fontSize: 12, color: '#666', marginTop: 2 },
  input: {
    backgroundColor: CARD, borderRadius: 8, padding: 12,
    fontSize: 15, borderWidth: 1, borderColor: BORDER, marginBottom: 12,
    color: '#FFF',
  },
  selectorBtn: {
    backgroundColor: CARD, borderRadius: 8, padding: 12,
    borderWidth: 1, borderColor: BORDER, marginBottom: 12,
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
  },
  selectorText: { color: '#FFF', fontSize: 15 },
  selectorPlaceholder: { color: '#555' },
  arrow: { color: '#666', fontSize: 18 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    backgroundColor: CARD, borderWidth: 1, borderColor: BORDER,
  },
  chipActive: { backgroundColor: GOLD, borderColor: GOLD },
  chipDisabled: { opacity: 0.35 },
  chipText: { color: '#AAA', fontSize: 13, fontWeight: '500' },
  chipTextActive: { color: '#000', fontWeight: '700' },
  switchRow: {
    flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', marginVertical: 8,
  },
  linkText: { color: GOLD, fontSize: 13, marginBottom: 10 },
  confirmedRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  confirmedText: { fontSize: 14, color: '#CCC' },
  proceedBtn: {
    backgroundColor: GOLD, borderRadius: 8, padding: 12,
    alignItems: 'center', marginTop: 8, marginBottom: 4,
  },
  proceedBtnText: { color: '#000', fontWeight: '700', fontSize: 15 },
  btnDisabled: { opacity: 0.4 },
  statRow: { flexDirection: 'row', marginBottom: 4 },
  statControlRow: { flexDirection: 'row', gap: 8, marginBottom: 12 },
  setLiveRow: { marginVertical: 8 },
  setLiveBtn: {
    borderWidth: 1, borderColor: BORDER, borderRadius: 8,
    padding: 12, alignItems: 'center',
  },
  setLiveBtnText: { color: '#CCC', fontSize: 14, fontWeight: '500' },
  prevTypesRow: { marginBottom: 12 },
  prevTypesLabel: { fontSize: 12, color: '#666', marginBottom: 6 },
  submitBtn: {
    backgroundColor: GOLD, borderRadius: 10, padding: 16,
    alignItems: 'center', marginTop: 20,
  },
  submitText: { color: '#000', fontWeight: '700', fontSize: 16 },
  resultBanner: { borderRadius: 8, padding: 14, marginTop: 12 },
  resultOk: { backgroundColor: 'rgba(76,175,80,0.15)', borderWidth: 1, borderColor: '#4CAF50' },
  resultErr: { backgroundColor: 'rgba(244,67,54,0.15)', borderWidth: 1, borderColor: '#F44336' },
  resultText: { color: '#CCC', fontSize: 14 },
  todayRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    backgroundColor: CARD, padding: 12, borderRadius: 8, marginBottom: 6,
  },
  todayGame: { color: '#888', fontSize: 12, flex: 1 },
  todayType: { color: '#CCC', fontSize: 12, flex: 1, textAlign: 'center' },
  todayValue: { color: GOLD, fontSize: 12, fontWeight: '700', textAlign: 'right', flex: 0.6 },
  guestContainer: { flex: 1, padding: 20 },
  guestCard: {
    backgroundColor: 'rgba(202,138,4,0.12)', borderWidth: 1,
    borderColor: '#92400e', borderRadius: 10, padding: 16, marginTop: 8,
  },
  guestTitle: { color: '#fde68a', fontWeight: '700', fontSize: 15, marginBottom: 6 },
  guestBody: { color: '#fde68a', fontSize: 13, lineHeight: 20 },
});
