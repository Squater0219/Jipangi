import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { StatusBar as ExpoStatusBar } from 'expo-status-bar';
import { Audio } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL || 'http://10.0.2.2:8000/api').replace(/\/$/, '');
const TOKEN_KEY = '@jipangi/access-token';
const HISTORY_KEY = '@jipangi/history';
const COLORS = { ink: '#1E2440', muted: '#687089', primary: '#4F46E5', soft: '#EEF0FF', surface: '#FFFFFF', canvas: '#F7F8FC', line: '#E3E6EF', success: '#16835A', danger: '#D84B57', warning: '#A66A00' };
const LEVELS = ['전체', '초급', '중급', '고급'];
const TYPES = ['전체', '받침', '모음', '비음화', '연음', '유음화'];

const demoSentences = [
  { id: 1, text: '발음은 부담이 되지 않습니다.', target_ipa: '/p a r ɯ m ɯ n p u d a m i t w e j i a n s ɯ m n i d a/', level: '초급', category: '받침', recommendation_reason: '받침 연습을 시작해 보세요.' },
  { id: 2, text: '비가 오는 날에는 우산이 필요해요.', target_ipa: '/p i k a o n ɯ n n a r e n ɯ n u s a n i p i r j o h e j o/', level: '초급', category: '모음' },
  { id: 3, text: '나는 맛있는 밥을 먹어요.', target_ipa: '/n a n ɯ n m a s i n n ɯ n p a p ɯ r m ʌ g ʌ j o/', level: '중급', category: '비음화' },
];

function normalizeSentence(item) {
  return { id: item.id, text: item.text || item.sentence || '', target_ipa: item.target_ipa || item.ipa || '', level: item.level || item.difficulty || '초급', category: item.category?.name || item.category || item.type || '기타', recommendation_reason: item.recommendation_reason || item.reason || '' };
}

async function request(path, { method = 'GET', token, body, form } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body: body ? JSON.stringify(body) : form });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.message || `요청에 실패했습니다. (${response.status})`);
  return data;
}

function App() {
  const [screen, setScreen] = useState('select');
  const [token, setToken] = useState(null);
  const [sentences, setSentences] = useState(demoSentences);
  const [selected, setSelected] = useState(demoSentences[0]);
  const [level, setLevel] = useState('전체');
  const [type, setType] = useState('전체');
  const [loadingSentences, setLoadingSentences] = useState(false);
  const [notice, setNotice] = useState('');
  const [recording, setRecording] = useState(null);
  const [recordingStartedAt, setRecordingStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [audioUri, setAudioUri] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [dashboard, setDashboard] = useState(null);

  useEffect(() => { bootstrap(); }, []);
  useEffect(() => {
    if (!recordingStartedAt) return undefined;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - recordingStartedAt) / 1000)), 250);
    return () => clearInterval(id);
  }, [recordingStartedAt]);

  async function bootstrap() {
    const [savedToken, savedHistory] = await Promise.all([AsyncStorage.getItem(TOKEN_KEY), AsyncStorage.getItem(HISTORY_KEY)]);
    if (savedToken) setToken(savedToken);
    if (savedHistory) setHistory(JSON.parse(savedHistory));
    loadSentences(savedToken || undefined);
    if (savedToken) loadAccountData(savedToken);
  }

  async function loadSentences(activeToken = token) {
    setLoadingSentences(true);
    try {
      const query = new URLSearchParams();
      if (level !== '전체') query.set('level', level);
      if (type !== '전체') query.set('category', type);
      const data = await request(`/practice-sentences/${query.toString() ? `?${query}` : ''}`, { token: activeToken });
      const list = (data.results || data).map(normalizeSentence);
      if (list.length) { setSentences(list); setSelected(list[0]); }
      setNotice('');
    } catch (_) {
      setNotice('서버에 연결하지 못해 예시 문장을 표시하고 있습니다.');
      setSentences(demoSentences);
    } finally { setLoadingSentences(false); }
  }

  async function loadAccountData(activeToken = token) {
    try {
      const [records, stats] = await Promise.all([
        request('/pronunciation-analyses/', { token: activeToken }),
        request('/dashboard/', { token: activeToken }),
      ]);
      setHistory(records.results || records);
      setDashboard(stats);
      await AsyncStorage.setItem(HISTORY_KEY, JSON.stringify(records.results || records));
    } catch (_) { setNotice('일부 학습 기록을 불러오지 못했습니다.'); }
  }

  const visibleSentences = useMemo(() => sentences.filter((item) => (level === '전체' || item.level === level) && (type === '전체' || item.category === type)), [sentences, level, type]);
  const navigate = (next) => {
    if (['history', 'profile'].includes(next) && !token) { setScreen('login'); return; }
    setScreen(next);
  };
  const changeFilter = (setter, value) => { setter(value); setTimeout(() => loadSentences(), 0); };

  async function startRecording() {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (!permission.granted) { Alert.alert('마이크 권한 필요', '발음을 녹음하려면 마이크 권한을 허용해 주세요.'); return; }
      await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
      const created = await Audio.Recording.createAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      setAudioUri(null); setElapsed(0); setRecording(created.recording); setRecordingStartedAt(Date.now());
    } catch (error) { Alert.alert('녹음을 시작하지 못했습니다', error.message); }
  }

  async function stopRecording() {
    if (!recording) return;
    try {
      await recording.stopAndUnloadAsync();
      setAudioUri(recording.getURI());
    } catch (error) { Alert.alert('녹음을 저장하지 못했습니다', error.message); }
    finally { setRecording(null); setRecordingStartedAt(null); await Audio.setAudioModeAsync({ allowsRecordingIOS: false }); }
  }

  async function analyze() {
    if (!audioUri) return;
    if (!token) { setScreen('login'); setNotice('분석 결과를 저장하려면 로그인해 주세요.'); return; }
    setAnalyzing(true);
    try {
      const form = new FormData();
      form.append('sentence_id', String(selected.id));
      form.append('audio', { uri: audioUri, name: `pronunciation-${Date.now()}.m4a`, type: 'audio/m4a' });
      const data = await request('/pronunciation-analyses/', { method: 'POST', token, form });
      const normalized = normalizeResult(data, selected);
      setResult(normalized);
      setHistory((old) => [normalized, ...old]);
      setScreen('result');
      loadAccountData(token);
    } catch (error) { Alert.alert('분석에 실패했습니다', error.message || '네트워크 연결과 서버 상태를 확인해 주세요.'); }
    finally { setAnalyzing(false); }
  }

  async function login(email, password) {
    const data = await request('/auth/login/', { method: 'POST', body: { email, password } });
    const nextToken = data.access || data.token;
    if (!nextToken) throw new Error('서버 응답에 access token이 없습니다.');
    await AsyncStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken); setScreen('select'); setNotice('로그인되었습니다.'); loadAccountData(nextToken); loadSentences(nextToken);
  }

  async function logout() { await AsyncStorage.removeItem(TOKEN_KEY); setToken(null); setDashboard(null); setScreen('select'); }

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle="dark-content" /><ExpoStatusBar style="dark" />
    <View style={styles.frame}>
      <View style={styles.header}><Text style={styles.logo}>〰 발음도우미</Text><Text style={styles.headerText}>{token ? '학습 중' : '로그인 필요'}</Text></View>
      {!!notice && <TouchableOpacity style={styles.notice} onPress={() => setNotice('')}><Text style={styles.noticeText}>{notice}</Text></TouchableOpacity>}
      {screen === 'select' && <SelectScreen list={visibleSentences} selected={selected} level={level} type={type} loading={loadingSentences} onLevel={(v) => changeFilter(setLevel, v)} onType={(v) => changeFilter(setType, v)} onSelect={setSelected} onStart={() => navigate('record')} />}
      {screen === 'record' && <RecordScreen sentence={selected} recording={!!recording} elapsed={elapsed} ready={!!audioUri} analyzing={analyzing} onRecord={recording ? stopRecording : startRecording} onAnalyze={analyze} onBack={() => navigate('select')} />}
      {screen === 'result' && <ResultScreen result={result} onRetry={() => { setAudioUri(null); setResult(null); navigate('record'); }} />}
      {screen === 'history' && <HistoryScreen history={history} dashboard={dashboard} onPractice={() => navigate('select')} />}
      {screen === 'profile' && <ProfileScreen dashboard={dashboard} onLogout={logout} />}
      {screen === 'login' && <LoginScreen onLogin={login} onBack={() => navigate('select')} />}
      {screen !== 'login' && <BottomNav screen={screen} onNavigate={navigate} />}
    </View>
  </SafeAreaView>;
}

function SelectScreen({ list, selected, level, type, loading, onLevel, onType, onSelect, onStart }) {
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>오늘의 연습</Text><Text style={styles.title}>내 수준에 맞는 문장을{`\n`}골라 보세요</Text><Text style={styles.subtitle}>난이도와 발음 유형을 선택해 문장을 찾을 수 있습니다.</Text>
    <Text style={styles.label}>난이도</Text><Chips values={LEVELS} selected={level} onChange={onLevel} />
    <Text style={styles.label}>발음 유형</Text><Chips values={TYPES} selected={type} onChange={onType} />
    <View style={styles.rowBetween}><Text style={styles.sectionTitle}>연습 문장</Text>{loading && <ActivityIndicator color={COLORS.primary} />}</View>
    {list.map((item) => <TouchableOpacity key={item.id} onPress={() => onSelect(item)} style={[styles.card, selected?.id === item.id && styles.cardActive]}><View style={styles.rowBetween}><Badge text={item.category} /><Text style={styles.muted}>{item.level}</Text></View><Text style={styles.sentence}>{item.text}</Text><Text style={styles.ipa}>{item.target_ipa}</Text>{item.recommendation_reason ? <Text style={styles.reason}>{item.recommendation_reason}</Text> : null}</TouchableOpacity>)}
    {!list.length && <Text style={styles.empty}>조건에 맞는 문장이 없습니다.</Text>}
    <Button text="이 문장으로 연습 시작" onPress={onStart} disabled={!selected} />
  </ScrollView>;
}

function RecordScreen({ sentence, recording, elapsed, ready, analyzing, onRecord, onAnalyze, onBack }) {
  return <ScrollView contentContainerStyle={styles.content}><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 문장 다시 고르기</Text></TouchableOpacity><Text style={styles.eyebrow}>음성 녹음</Text><Text style={styles.title}>문장을 천천히{`\n`}말해 보세요</Text>
    <View style={styles.practice}><Text style={styles.label}>연습 문장</Text><Text style={styles.sentence}>{sentence.text}</Text><Text style={styles.ipa}>{sentence.target_ipa}</Text></View>
    <View style={[styles.recordBox, recording && styles.recording]}><Text style={styles.recordState}>{recording ? '● 녹음 중' : ready ? '✓ 녹음 완료' : '마이크 버튼을 눌러 시작'}</Text><Text style={styles.timer}>{String(Math.floor(elapsed / 60)).padStart(2, '0')}:{String(elapsed % 60).padStart(2, '0')}</Text><TouchableOpacity accessibilityLabel={recording ? '녹음 정지' : '녹음 시작'} style={[styles.mic, recording && styles.micLive]} onPress={onRecord}><Text style={styles.micText}>{recording ? '■' : '●'}</Text></TouchableOpacity><Text style={styles.muted}>{recording ? '완료되면 버튼을 다시 누르세요.' : '주변 소음이 적은 곳에서 녹음해 주세요.'}</Text></View>
    {ready && <Button text={analyzing ? '발음 분석 중…' : '발음 분석하기'} onPress={onAnalyze} disabled={analyzing} />}
  </ScrollView>;
}

function normalizeResult(data, sentence) {
  const feedback = data.feedback || data.correction_feedback || {};
  return { id: data.id || Date.now(), sentence: normalizeSentence(data.sentence || sentence), score: data.score ?? data.pronunciation_score ?? 0, target_ipa: data.target_ipa || sentence.target_ipa, user_ipa: data.user_ipa || data.predicted_ipa || '', errors: data.errors || data.pronunciation_errors || [], feedback: { summary: feedback.summary || data.feedback_summary || '분석 결과를 확인해 보세요.', detail: feedback.detail || feedback.content || data.feedback_detail || '', priority: feedback.priority || data.priority_correction || '' }, created_at: data.created_at || new Date().toISOString() };
}

function ResultScreen({ result, onRetry }) {
  if (!result) return <View style={styles.center}><Text>분석 결과가 없습니다.</Text></View>;
  return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>분석 결과</Text><Text style={styles.title}>오늘의 발음 점수</Text><View style={styles.scoreCard}><Text style={styles.score}>{Math.round(result.score)}<Text style={styles.scoreUnit}>점</Text></Text><Text style={styles.scoreCaption}>{result.score >= 80 ? '좋아요! 이 흐름을 유지해 보세요.' : '오류 음소를 중심으로 다시 연습해 보세요.'}</Text></View>
    <View style={styles.card}><Text style={styles.label}>연습 문장</Text><Text style={styles.sentence}>{result.sentence.text}</Text></View><Text style={styles.sectionTitle}>발음 비교</Text><IpaLine label="목표 IPA" value={result.target_ipa} /><IpaLine label="내 발음 IPA" value={result.user_ipa} errors={result.errors} />
    <Text style={styles.sectionTitle}>다르게 발음된 음소</Text>{result.errors.length ? result.errors.map((error, index) => <View key={error.id || index} style={styles.errorRow}><Text style={styles.errorToken}>{error.expected_phone || error.target || '∅'} → {error.actual_phone || error.user || '∅'}</Text><Text style={styles.errorDescription}>{error.error_type || error.type || '음소 차이'}</Text></View>) : <Text style={styles.empty}>감지된 음소 오류가 없습니다.</Text>}
    <View style={styles.feedback}><Text style={styles.feedbackTitle}>{result.feedback.summary}</Text>{!!result.feedback.detail && <Text style={styles.feedbackText}>{result.feedback.detail}</Text>}{!!result.feedback.priority && <Text style={styles.priority}>우선 연습: {result.feedback.priority}</Text>}</View><Button text="다시 연습하기" onPress={onRetry} />
  </ScrollView>;
}

function IpaLine({ label, value, errors = [] }) { const errorIndexes = new Set(errors.map((e) => e.user_index ?? e.position).filter(Number.isInteger)); return <View style={styles.ipaCard}><Text style={styles.label}>{label}</Text><View style={styles.ipaTokens}>{String(value || '서버에서 IPA를 받지 못했습니다.').replaceAll('/', '').trim().split(/\s+/).map((token, index) => <Text key={`${token}-${index}`} style={[styles.token, errorIndexes.has(index) && styles.errorToken]}>{token} </Text>)}</View></View>; }

function HistoryScreen({ history, dashboard, onPractice }) { const scores = history.slice(0, 7).reverse().map((item) => Number(item.score ?? item.pronunciation_score ?? 0)); return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>나의 기록</Text><Text style={styles.title}>연습이 쌓이고 있어요</Text><View style={styles.stats}><Stat value={dashboard?.streak_days ?? dashboard?.streak ?? 0} label="연속 학습일" /><Stat value={dashboard?.average_score ?? average(scores)} label="평균 점수" /><Stat value={history.length} label="총 연습" /></View><Text style={styles.sectionTitle}>최근 점수</Text><View style={styles.chart}>{scores.length ? scores.map((score, i) => <View key={i} style={[styles.bar, { height: Math.max(12, Math.min(130, score * 1.3)) }]}><Text style={styles.barText}>{score}</Text></View>) : <Text style={styles.empty}>아직 기록이 없습니다.</Text>}</View><Text style={styles.sectionTitle}>최근 연습</Text>{history.slice(0, 10).map((item, index) => <View key={item.id || index} style={styles.history}><View><Text style={styles.historySentence}>{item.sentence?.text || item.sentence_text || '연습 문장'}</Text><Text style={styles.muted}>{new Date(item.created_at || Date.now()).toLocaleDateString('ko-KR')}</Text></View><Text style={styles.historyScore}>{Math.round(item.score ?? item.pronunciation_score ?? 0)}점</Text></View>)}<Button text="새 문장 연습하기" onPress={onPractice} /></ScrollView>; }

function ProfileScreen({ dashboard, onLogout }) { return <ScrollView contentContainerStyle={styles.content}><Text style={styles.eyebrow}>내 정보</Text><Text style={styles.title}>나의 학습 현황</Text><View style={styles.card}><Text style={styles.profileName}>{dashboard?.user_name || dashboard?.user?.name || '학습자'}</Text><Text style={styles.muted}>{dashboard?.user?.email || '로그인한 계정'}</Text></View><View style={styles.stats}><Stat value={dashboard?.total_practices ?? 0} label="누적 연습" /><Stat value={dashboard?.average_score ?? 0} label="평균 점수" /><Stat value={dashboard?.streak_days ?? 0} label="연속 학습" /></View><Text style={styles.api}>API 주소: {API_BASE_URL}</Text><Button text="로그아웃" danger onPress={onLogout} /></ScrollView>; }

function LoginScreen({ onLogin, onBack }) { const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [submitting, setSubmitting] = useState(false); const submit = async () => { if (!email || !password) return Alert.alert('입력 확인', '이메일과 비밀번호를 입력해 주세요.'); setSubmitting(true); try { await onLogin(email.trim(), password); } catch (e) { Alert.alert('로그인 실패', e.message); } finally { setSubmitting(false); } }; return <ScrollView contentContainerStyle={styles.login}><TouchableOpacity onPress={onBack}><Text style={styles.back}>‹ 홈으로 돌아가기</Text></TouchableOpacity><Text style={styles.title}>다시 만나서 반가워요</Text><Text style={styles.subtitle}>로그인하면 분석 결과와 학습 기록을 저장할 수 있어요.</Text><View style={styles.card}><Text style={styles.label}>이메일</Text><TextInput value={email} onChangeText={setEmail} style={styles.input} placeholder="name@example.com" autoCapitalize="none" keyboardType="email-address" /><Text style={styles.label}>비밀번호</Text><TextInput value={password} onChangeText={setPassword} style={styles.input} placeholder="비밀번호" secureTextEntry /><Button text={submitting ? '로그인 중…' : '로그인'} onPress={submit} disabled={submitting} /></View></ScrollView>; }

function Chips({ values, selected, onChange }) { return <View style={styles.chips}>{values.map((value) => <TouchableOpacity key={value} style={[styles.chip, value === selected && styles.chipActive]} onPress={() => onChange(value)}><Text style={[styles.chipText, value === selected && styles.chipTextActive]}>{value}</Text></TouchableOpacity>)}</View>; }
function Badge({ text }) { return <View style={styles.badge}><Text style={styles.badgeText}>{text}</Text></View>; }
function Button({ text, onPress, disabled, danger }) { return <TouchableOpacity disabled={disabled} onPress={onPress} style={[styles.button, danger && styles.dangerButton, disabled && styles.disabled]}><Text style={styles.buttonText}>{text}</Text><Text style={styles.buttonText}>→</Text></TouchableOpacity>; }
function Stat({ value, label }) { return <View style={styles.stat}><Text style={styles.statValue}>{value}</Text><Text style={styles.muted}>{label}</Text></View>; }
function BottomNav({ screen, onNavigate }) { return <View style={styles.nav}>{[{ id: 'select', label: '문장' }, { id: 'record', label: '연습' }, { id: 'history', label: '기록' }, { id: 'profile', label: '내 정보' }].map((item) => <TouchableOpacity key={item.id} style={styles.navItem} onPress={() => onNavigate(item.id)}><Text style={[styles.navText, screen === item.id && styles.navActive]}>{item.label}</Text></TouchableOpacity>)}</View>; }
const average = (values) => values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : 0;

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.canvas }, frame: { flex: 1, width: '100%', maxWidth: 680, alignSelf: 'center' }, header: { height: 64, paddingHorizontal: 20, backgroundColor: COLORS.surface, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', borderBottomWidth: 1, borderColor: COLORS.line }, logo: { fontSize: 18, fontWeight: '900', color: COLORS.primary }, headerText: { fontSize: 12, fontWeight: '700', color: COLORS.success }, content: { padding: 20, paddingBottom: 100 }, login: { flexGrow: 1, padding: 24, justifyContent: 'center' }, eyebrow: { color: COLORS.primary, fontWeight: '900', marginTop: 6, marginBottom: 7 }, title: { color: COLORS.ink, fontSize: 28, lineHeight: 36, fontWeight: '900' }, subtitle: { color: COLORS.muted, lineHeight: 20, marginTop: 10, marginBottom: 18 }, label: { fontSize: 12, color: COLORS.muted, fontWeight: '800', marginTop: 12, marginBottom: 7 }, sectionTitle: { fontSize: 17, fontWeight: '900', color: COLORS.ink, marginTop: 20, marginBottom: 10 }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 }, chip: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: 20, borderWidth: 1, borderColor: COLORS.line, backgroundColor: COLORS.surface }, chipActive: { backgroundColor: COLORS.soft, borderColor: COLORS.primary }, chipText: { color: COLORS.muted, fontWeight: '700', fontSize: 12 }, chipTextActive: { color: COLORS.primary }, card: { backgroundColor: COLORS.surface, borderRadius: 16, borderWidth: 1, borderColor: COLORS.line, padding: 16, marginBottom: 10 }, cardActive: { borderWidth: 2, borderColor: COLORS.primary }, rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, badge: { alignSelf: 'flex-start', paddingVertical: 4, paddingHorizontal: 8, borderRadius: 8, backgroundColor: COLORS.soft }, badgeText: { color: COLORS.primary, fontSize: 11, fontWeight: '800' }, sentence: { color: COLORS.ink, fontSize: 18, lineHeight: 26, fontWeight: '800', marginTop: 10 }, ipa: { color: COLORS.muted, fontSize: 12, lineHeight: 18, marginTop: 8 }, reason: { color: COLORS.success, fontSize: 12, marginTop: 10, fontWeight: '700' }, muted: { color: COLORS.muted, fontSize: 12 }, button: { minHeight: 54, paddingHorizontal: 18, borderRadius: 15, backgroundColor: COLORS.primary, marginTop: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, dangerButton: { backgroundColor: COLORS.danger }, disabled: { opacity: .5 }, buttonText: { color: '#FFF', fontSize: 15, fontWeight: '900' }, notice: { backgroundColor: '#FFF5D9', paddingHorizontal: 20, paddingVertical: 10 }, noticeText: { color: COLORS.warning, fontSize: 12, fontWeight: '700' }, back: { color: COLORS.muted, fontWeight: '700', marginBottom: 16 }, practice: { backgroundColor: COLORS.soft, padding: 17, borderRadius: 16, marginTop: 20, marginBottom: 15 }, recordBox: { alignItems: 'center', padding: 24, borderRadius: 20, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line }, recording: { borderColor: '#F3C3C8', backgroundColor: '#FFFAFA' }, recordState: { color: COLORS.danger, fontWeight: '900' }, timer: { fontVariant: ['tabular-nums'], fontSize: 38, color: COLORS.ink, fontWeight: '900', marginVertical: 20 }, mic: { width: 76, height: 76, borderRadius: 38, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.primary, marginBottom: 14 }, micLive: { backgroundColor: COLORS.danger }, micText: { color: '#FFF', fontSize: 27 }, scoreCard: { padding: 22, borderRadius: 20, marginTop: 18, backgroundColor: COLORS.primary }, score: { color: '#FFF', fontSize: 53, fontWeight: '900' }, scoreUnit: { fontSize: 19 }, scoreCaption: { color: '#DCDDFF', marginTop: 6, fontWeight: '700' }, ipaCard: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, borderRadius: 14, padding: 14, marginBottom: 9 }, ipaTokens: { flexDirection: 'row', flexWrap: 'wrap' }, token: { color: COLORS.ink, fontSize: 15, fontWeight: '700' }, errorToken: { color: COLORS.danger, fontWeight: '900' }, errorRow: { backgroundColor: '#FFF0F1', borderRadius: 12, padding: 12, marginBottom: 7 }, errorDescription: { color: '#9B3541', fontSize: 12, marginTop: 5 }, feedback: { backgroundColor: '#E9F8F1', padding: 16, borderRadius: 16, marginTop: 18 }, feedbackTitle: { color: COLORS.success, fontWeight: '900', fontSize: 15 }, feedbackText: { color: '#27634E', lineHeight: 20, marginTop: 7 }, priority: { color: COLORS.success, fontWeight: '800', marginTop: 9 }, stats: { flexDirection: 'row', gap: 8, marginTop: 20 }, stat: { flex: 1, minHeight: 82, borderRadius: 14, backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.line, alignItems: 'center', justifyContent: 'center', padding: 8 }, statValue: { fontSize: 22, fontWeight: '900', color: COLORS.primary }, chart: { minHeight: 155, padding: 16, borderRadius: 16, backgroundColor: COLORS.surface, flexDirection: 'row', gap: 10, alignItems: 'flex-end', borderWidth: 1, borderColor: COLORS.line }, bar: { flex: 1, backgroundColor: '#A8ACFF', borderRadius: 6, justifyContent: 'flex-start', alignItems: 'center' }, barText: { color: COLORS.primary, fontSize: 10, fontWeight: '800', marginTop: -16 }, history: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 13, borderBottomWidth: 1, borderColor: COLORS.line }, historySentence: { color: COLORS.ink, fontWeight: '800', maxWidth: 245 }, historyScore: { color: COLORS.primary, fontWeight: '900' }, profileName: { color: COLORS.ink, fontWeight: '900', fontSize: 20 }, api: { color: COLORS.muted, fontSize: 11, marginTop: 24 }, input: { height: 50, borderWidth: 1, borderColor: COLORS.line, borderRadius: 12, paddingHorizontal: 13, color: COLORS.ink, backgroundColor: '#FCFCFE' }, empty: { color: COLORS.muted, paddingVertical: 16, textAlign: 'center' }, center: { flex: 1, alignItems: 'center', justifyContent: 'center' }, nav: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 65, paddingHorizontal: 8, backgroundColor: COLORS.surface, flexDirection: 'row', borderTopWidth: 1, borderColor: COLORS.line }, navItem: { flex: 1, alignItems: 'center', justifyContent: 'center' }, navText: { fontSize: 12, fontWeight: '800', color: COLORS.muted }, navActive: { color: COLORS.primary }
});

export default App;
