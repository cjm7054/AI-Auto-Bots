// 항만 AI 화상회의 — 서버 없는 P2P(WebRTC mesh) 회의. 신호 교환만 공용 릴레이(Nostr/MQTT/BitTorrent) 사용, 내용은 AES-GCM 암호화.
import {joinRoom as joinNostr, selfId} from '@trystero-p2p/nostr'
import {joinRoom as joinMqtt} from '@trystero-p2p/mqtt'
import {joinRoom as joinTorrent} from '@trystero-p2p/torrent'

const APP_ID = 'hmd-harbor-meet-v1'
const PORTAL = 'https://claude.ai/artifact/71N92W5sQjyEMxVCoCJpMT'
const $ = id => document.getElementById(id)
const LS = {get(k, d) {try {const v = localStorage.getItem('hm:' + k); return v == null ? d : JSON.parse(v)} catch (e) {return d}}, set(k, v) {try {localStorage.setItem('hm:' + k, JSON.stringify(v))} catch (e) {}}}
function h(tag, p, ...kids) {const e = document.createElement(tag); if (p) for (const k in p) {const v = p[k]; if (v == null || v === false) continue; if (k === 'class') e.className = v; else if (k === 'style') e.style.cssText = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v === true ? '' : v)}
  for (const c of kids.flat(9)) {if (c == null || c === false) continue; e.append(c.nodeType ? c : document.createTextNode(String(c)))} return e}
const rnd = (n = 10) => {const a = new Uint8Array(n); crypto.getRandomValues(a); return [...a].map(b => 'abcdefghjkmnpqrstuvwxyz23456789'[b % 31]).join('')}
async function sha(s) {const b = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('').slice(0, 24)}
const COLORS = ['#0b7480', '#2b62a3', '#9a5b13', '#7a3e9d', '#2c8a4b', '#b23b4e', '#3d5a80', '#8a6d1c', '#16697a', '#6b4f9e']
const colOf = s => {let x = 0; for (const c of s || '') x = (x * 31 + c.charCodeAt(0)) >>> 0; return COLORS[x % COLORS.length]}
const ini = n => (n || '?').replace(/\(.*\)/, '').trim().slice(-2)
const hhmm = t => new Date(t).toLocaleTimeString('ko-KR', {hour: '2-digit', minute: '2-digit'})
let toastT; function toast(m, ms = 3200) {document.querySelectorAll('.toast').forEach(x => x.remove()); const t = h('div', {class: 'toast', role: 'status'}, m); document.body.append(t); clearTimeout(toastT); toastT = setTimeout(() => t.remove(), ms)}
const IC = {
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  micoff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3l18 18M9 9v2a3 3 0 0 0 5 2.2M15 9.3V6a3 3 0 0 0-5.7-1.3M5 11a7 7 0 0 0 11.5 5.3M19 11a7 7 0 0 1-.6 2.8M12 18v3"/></svg>',
  cam: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3z"/></svg>',
  camoff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3l18 18M16 16v0a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h1M10 6h4a2 2 0 0 1 2 2v2l5-3v10"/></svg>',
  screen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4M12 7v6M9 10l3-3 3 3"/></svg>',
  hand: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 11V5a1.5 1.5 0 0 1 3 0v5M10 10V4a1.5 1.5 0 0 1 3 0v6M13 10V5a1.5 1.5 0 0 1 3 0v6M16 11V8a1.5 1.5 0 0 1 3 0v6a7 7 0 0 1-7 7h-1a6 6 0 0 1-5-3l-2.5-4a1.5 1.5 0 0 1 2.5-1.6L7 14"/></svg>',
  chat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/></svg>',
  ppl: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6"/></svg>',
  cc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M10 10.5a2.5 2.5 0 1 0 0 3M17 10.5a2.5 2.5 0 1 0 0 3"/></svg>',
  wb: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20l4-1 11-11-3-3L5 16l-1 4zM14 6l3 3"/></svg>',
  react: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/></svg>',
  more: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>',
  leave: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 15c3-3 15-3 18 0l-2 3-4-1v-3a12 12 0 0 0-6 0v3l-4 1z"/></svg>',
}

/* ---------- 상태 ---------- */
const S = {
  cfg: null, room: null, A: {}, me: {name: '', mic: true, cam: true, hand: false, sharing: false, joinedAt: 0},
  local: null, rawVideo: null, sendVideo: null, screen: null, peers: new Map(), pinned: null, speaker: null,
  chat: [], caps: [], att: [], wb: [], locked: false, isHost: false, startAt: 0, unread: 0, side: null,
  rec: null, recog: null, capOn: false, blur: null, wake: null, devices: {cam: '', mic: '', spk: ''}, quality: 'auto', ns: true,
  audioCtx: null, meters: new Map(),
}

/* ---------- 해시 파라미터 ---------- */
function readHash() {const p = new URLSearchParams(location.hash.slice(1)); return {r: p.get('r') || '', k: p.get('k') || '', t: p.get('t') || '', h: p.get('h') || '', hh: p.get('hh') || '', s: p.get('s') || '', turn: p.get('turn') || ''}}
function linkFor(c, host) {const p = new URLSearchParams(); p.set('r', c.room); p.set('k', c.key); if (c.title) p.set('t', c.title); if (c.hh) p.set('hh', c.hh); if (c.strat && c.strat !== 'nostr') p.set('s', c.strat); if (c.turnRaw) p.set('turn', c.turnRaw); if (host && c.hk) p.set('h', c.hk)
  return location.origin + location.pathname + '#' + p.toString()}

/* ---------- 로비: 미리보기 ---------- */
let pvStream = null, pvMeterStop = null
const Q = {hd: {w: 1280, h: 720, br: 1500000}, sd: {w: 640, h: 360, br: 600000}, low: {w: 426, h: 240, br: 250000}}
function vConstraints(devId) {const q = Q[S.quality === 'auto' ? 'hd' : S.quality]; const v = {width: {ideal: q.w}, height: {ideal: q.h}, frameRate: {ideal: 24, max: 30}}; if (devId) v.deviceId = {exact: devId}; else v.facingMode = 'user'; return v}
function aConstraints(devId) {const a = {echoCancellation: S.ns, noiseSuppression: S.ns, autoGainControl: true}; if (devId) a.deviceId = {exact: devId}; return a}
async function getMedia() {
  const out = new MediaStream()
  try {const s = await navigator.mediaDevices.getUserMedia({audio: aConstraints(S.devices.mic)}); s.getAudioTracks().forEach(t => out.addTrack(t))} catch (e) {console.warn('mic', e); toast('마이크를 사용할 수 없습니다: ' + (e.name === 'NotAllowedError' ? '권한 거부(주소창의 권한 설정 확인)' : e.message))}
  try {const s = await navigator.mediaDevices.getUserMedia({video: vConstraints(S.devices.cam)}); s.getVideoTracks().forEach(t => out.addTrack(t))} catch (e) {console.warn('cam', e); if (e.name !== 'NotFoundError') toast('카메라를 사용할 수 없습니다: ' + (e.name === 'NotAllowedError' ? '권한 거부' : e.message)); S.me.cam = false}
  return out
}
async function listDevices() {
  try {
    const ds = await navigator.mediaDevices.enumerateDevices()
    const fill = (sel, kind, cur) => {sel.replaceChildren(...ds.filter(d => d.kind === kind).map((d, i) => h('option', {value: d.deviceId, selected: d.deviceId === cur ? true : null}, d.label || (kind === 'videoinput' ? '카메라 ' : kind === 'audioinput' ? '마이크 ' : '스피커 ') + (i + 1))))}
    fill($('selCam'), 'videoinput', S.devices.cam); fill($('selMic'), 'audioinput', S.devices.mic); fill($('selSpk'), 'audiooutput', S.devices.spk)
    $('spkBox').hidden = !('setSinkId' in HTMLMediaElement.prototype) || !$('selSpk').options.length
  } catch (e) {}
}
function meter(stream, cb) {
  try {
    const ctx = audioCtx(); const tr = stream.getAudioTracks()[0]; if (!tr) return () => {}
    const src = ctx.createMediaStreamSource(new MediaStream([tr])); const an = ctx.createAnalyser(); an.fftSize = 512; src.connect(an)
    const buf = new Uint8Array(an.fftSize); let stop = false
    const tick = () => {if (stop) return; an.getByteTimeDomainData(buf); let s = 0; for (const v of buf) {const x = (v - 128) / 128; s += x * x} cb(Math.sqrt(s / buf.length)); setTimeout(tick, 120)}
    tick(); return () => {stop = true; try {src.disconnect()} catch (e) {}}
  } catch (e) {return () => {}}
}
function audioCtx() {if (!S.audioCtx) S.audioCtx = new (window.AudioContext || window.webkitAudioContext)(); if (S.audioCtx.state === 'suspended') S.audioCtx.resume().catch(() => {}); return S.audioCtx}
async function startPreview() {
  if (pvStream) pvStream.getTracks().forEach(t => t.stop())
  pvStream = await getMedia(); S.local = pvStream
  $('pvVid').srcObject = pvStream; applyPvButtons(); await listDevices()
  if (pvMeterStop) pvMeterStop(); pvMeterStop = meter(pvStream, l => {$('pvLvl').style.width = Math.min(100, l * 400) + '%'})
}
function applyPvButtons() {
  const a = S.local && S.local.getAudioTracks()[0], v = S.local && S.local.getVideoTracks()[0]
  if (a) a.enabled = S.me.mic; if (v) v.enabled = S.me.cam
  $('pvMic').innerHTML = S.me.mic ? IC.mic : IC.micoff; $('pvMic').classList.toggle('off', !S.me.mic)
  $('pvCam').innerHTML = S.me.cam ? IC.cam : IC.camoff; $('pvCam').classList.toggle('off', !S.me.cam)
  $('pvNo').hidden = !!(v && S.me.cam)
}
$('pvMic').onclick = () => {S.me.mic = !S.me.mic; applyPvButtons()}
$('pvCam').onclick = () => {S.me.cam = !S.me.cam; applyPvButtons()}
$('selCam').onchange = e => {S.devices.cam = e.target.value; LS.set('dev', S.devices); startPreview()}
$('selMic').onchange = e => {S.devices.mic = e.target.value; LS.set('dev', S.devices); startPreview()}
$('selSpk').onchange = e => {S.devices.spk = e.target.value; LS.set('dev', S.devices)}
$('optQ').onchange = e => {S.quality = e.target.value; LS.set('q', S.quality); startPreview()}
$('optNs').onchange = e => {S.ns = e.target.checked; startPreview()}

/* ---------- 로비: 회의 만들기 ---------- */
async function newMeeting() {
  const room = rnd(12), key = rnd(16), hk = rnd(20), hh = await sha(hk)
  $('inRoom').value = room; $('inKey').value = key
  S.pendingHost = {hk, hh}
  const c = curCfg(); c.hk = hk; c.hh = hh
  showInvite(c, true)
}
function curCfg() {
  let turn = null, turnRaw = $('optTurn').value.trim()
  if (turnRaw) {try {turn = JSON.parse(turnRaw); if (!Array.isArray(turn)) turn = [turn]} catch (e) {toast('TURN 설정 JSON 형식이 올바르지 않습니다.'); turn = null; turnRaw = ''}}
  return {room: $('inRoom').value.trim(), key: $('inKey').value.trim(), title: $('inTitle').value.trim(), strat: $('optStrat').value, turn, turnRaw, hh: S.pendingHost?.hh || S.hashHH || '', hk: S.pendingHost?.hk || S.hashHK || ''}
}
function showInvite(c, host) {
  $('invBox').hidden = false; $('invLink').textContent = linkFor(c, false)
  if (host && c.hk) {$('hostBox').hidden = false; $('hostLink').textContent = linkFor(c, true)}
}
$('btnNew').onclick = newMeeting
$('btnCopy').onclick = () => copy($('invLink').textContent, '초대 링크를 복사했습니다.')
function copy(t, msg) {navigator.clipboard?.writeText(t).then(() => toast(msg), () => toast('길게 눌러 복사하세요.'))}
;['inTitle', 'inRoom', 'inKey', 'optStrat', 'optTurn'].forEach(id => $(id).addEventListener('change', () => {if (!$('invBox').hidden) showInvite(curCfg(), !!curCfg().hk)}))

/* ---------- 입장 ---------- */
$('btnJoin').onclick = async () => {
  const name = $('inName').value.trim(); if (!name) {toast('내 이름을 입력하세요.'); $('inName').focus(); return}
  if (!$('inRoom').value.trim()) await newMeeting()
  const c = curCfg(); if (c.key.length < 6) {toast('회의 암호는 6자 이상이어야 합니다.'); return}
  S.me.name = name; LS.set('name', name)
  S.cfg = c; S.isHost = !!(c.hk && c.hh && await sha(c.hk) === c.hh)
  history.replaceState(null, '', '#' + new URLSearchParams(Object.fromEntries(Object.entries({r: c.room, k: c.key, t: c.title, hh: c.hh, s: c.strat !== 'nostr' ? c.strat : '', turn: c.turnRaw, h: S.isHost ? c.hk : ''}).filter(([, v]) => v))).toString())
  enterRoom()
}

function enterRoom() {
  const c = S.cfg
  if (pvMeterStop) {pvMeterStop(); pvMeterStop = null}
  $('lobby').hidden = true; $('room').hidden = false
  $('rTitle').textContent = (c.title || '회의') + (S.isHost ? ' · 진행자' : '')
  document.title = (c.title || '회의') + ' — 항만 AI 화상회의'
  S.me.joinedAt = Date.now(); S.startAt = Date.now()
  S.rawVideo = S.local.getVideoTracks()[0] || null; S.sendVideo = S.rawVideo
  const join = c.strat === 'mqtt' ? joinMqtt : c.strat === 'torrent' ? joinTorrent : joinNostr
  const conf = {appId: APP_ID, password: c.key}
  if (c.turn) conf.turnConfig = c.turn
  S.room = join(conf, c.room, {onJoinError: d => {console.warn('join error', d); sys('연결 실패(' + (d.error || '알 수 없음') + ') — 회사망·LTE 환경이면 고급 설정에서 TURN 서버를 지정하세요.')}})
  wire()
  if (S.local.getTracks().length) S.room.addStream(S.local, {metadata: {kind: 'cam'}})
  att(selfId, S.me.name, 'join')
  buildToolbar(); renderGrid(); renderSide()
  setInterval(() => {const s = Math.floor((Date.now() - S.startAt) / 1000); $('rTime').textContent = (s >= 3600 ? Math.floor(s / 3600) + ':' : '') + String(Math.floor(s / 60) % 60).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0')}, 1000)
  setInterval(stats, 3000)
  watchSpeaking(selfId, S.local)
  wakeLock()
  sys((S.isHost ? '진행자로 ' : '') + '입장했습니다. 초대 링크를 받은 참여자가 들어오면 자동으로 연결됩니다.')
  if (S.blurWanted) toggleBlur(true)
  window.addEventListener('beforeunload', () => {try {S.room.leave()} catch (e) {}})
}

/* ---------- P2P 배선 ---------- */
function wire() {
  const r = S.room, mk = (n, o) => r.makeAction(n, o)
  S.A.st = mk('st'); S.A.chat = mk('chat'); S.A.file = mk('file', {onReceive: ({byteLength}) => byteLength <= 200 * 1024 * 1024})
  S.A.cap = mk('cap'); S.A.wb = mk('wb'); S.A.cmd = mk('cmd'); S.A.re = mk('re'); S.A.hist = mk('hist'); S.A.hreq = mk('hreq')
  r.onPeerJoin = id => {
    if (S.locked && S.isHost) {S.A.cmd.send({c: 'locked'}, {target: id}); return}
    S.peers.set(id, {id, name: '연결 중…', mic: true, cam: true, hand: false, sharing: false, streams: {}, joinedAt: Date.now(), host: false, q: null, gotState: false})
    sendState(id)
    if (S.local.getTracks().length) r.addStream(S.local, {target: id, metadata: {kind: 'cam'}})
    if (S.screen) r.addStream(S.screen, {target: id, metadata: {kind: 'screen'}})
    tuneSenders(); renderGrid(); renderSide()
  }
  r.onPeerLeave = id => {const p = S.peers.get(id); if (p) {att(id, p.name, 'leave'); sys(p.name + ' 님이 나갔습니다.'); stopMeter(id)} S.peers.delete(id); if (S.pinned && S.pinned.startsWith(id)) S.pinned = null; tuneSenders(); renderGrid(); renderSide()}
  r.onPeerStream = (stream, id, meta) => {
    let p = S.peers.get(id); if (!p) {p = {id, name: '연결 중…', mic: true, cam: true, streams: {}, joinedAt: Date.now()}; S.peers.set(id, p)}
    const kind = meta && meta.kind === 'screen' ? 'screen' : 'cam'
    p.streams[kind] = stream
    stream.addEventListener('removetrack', () => {if (!stream.getTracks().length) {delete p.streams[kind]; renderGrid()}})
    if (kind === 'cam') watchSpeaking(id, stream)
    if (kind === 'screen' && !S.pinned) S.pinned = id + ':screen'
    renderGrid()
  }
  S.A.st.onMessage = async (d, {peerId}) => {
    let p = S.peers.get(peerId); if (!p) {p = {id: peerId, streams: {}, joinedAt: Date.now()}; S.peers.set(peerId, p)}
    const first = !p.gotState
    Object.assign(p, {name: String(d.name || '참여자').slice(0, 40), mic: !!d.mic, cam: !!d.cam, hand: !!d.hand, sharing: !!d.sharing, gotState: true})
    if (d.hk && S.cfg.hh) p.host = (await sha(d.hk)) === S.cfg.hh
    if (first) {att(peerId, p.name, 'join'); sys(p.name + ' 님이 입장했습니다.'); if (!S.histDone) {S.histDone = true; S.A.hreq.send(1, {target: peerId})}}
    if (!p.sharing && p.streams.screen) {delete p.streams.screen; if (S.pinned === peerId + ':screen') S.pinned = null}
    if (d.hand && first === false && !p._hand) toast('✋ ' + p.name + ' 님이 발언을 요청했습니다.')
    p._hand = d.hand
    renderGrid(); renderSide()
  }
  S.A.hreq.onMessage = (d, {peerId}) => {S.A.hist.send({chat: S.chat.filter(m => !m.sys && !(m.file && m.file.sending)).slice(-200).map(m => m.file ? {...m, file: {name: m.file.name, size: m.file.size}} : m), wb: S.wb.slice(-3000), caps: S.caps.slice(-200), att: S.att.slice(-300), startAt: S.startAt, locked: S.locked}, {target: peerId})}
  S.A.hist.onMessage = (d) => {
    const ids = new Set(S.chat.map(m => m.id)); for (const m of d.chat || []) if (!ids.has(m.id)) S.chat.push(m); S.chat.sort((a, b) => a.at - b.at)
    const wids = new Set(S.wb.map(s => s.id)); for (const s of d.wb || []) if (!wids.has(s.id)) S.wb.push(s)
    const cids = new Set(S.caps.map(c => c.id)); for (const c of d.caps || []) if (!cids.has(c.id)) S.caps.push(c); S.caps.sort((a, b) => a.at - b.at)
    for (const a of d.att || []) if (!S.att.some(x => x.id === a.id && x.ev === a.ev && x.at === a.at)) S.att.push(a); S.att.sort((a, b) => a.at - b.at)
    if (d.startAt && d.startAt < S.startAt) S.startAt = d.startAt
    redrawWb(); renderSide()
  }
  S.A.chat.onMessage = (m) => {if (!m || !m.id) return; S.chat.push(m); if (S.side !== 'chat') {S.unread++; buildToolbar()} renderSide(); if (S.side !== 'chat') toast('💬 ' + m.name + ': ' + String(m.text).slice(0, 60))}
  S.A.file.onReceiveProgress = (pct, {metadata}) => {if (metadata) setFileProg(metadata.fid, pct)}
  S.A.file.onMessage = (data, {peerId, metadata}) => {const p = S.peers.get(peerId); const blob = new Blob([data], {type: metadata?.type || 'application/octet-stream'}); const url = URL.createObjectURL(blob)
    S.chat.push({id: metadata?.fid || rnd(), name: p ? p.name : '참여자', at: Date.now(), file: {name: metadata?.name || '파일', size: data.byteLength, url}}); if (S.side !== 'chat') {S.unread++; buildToolbar()} renderSide()}
  S.A.cap.onMessage = (c) => {if (!c) return; if (c.final) {S.caps.push(c); renderSide()} showCap(c)}
  S.A.wb.onMessage = (s) => {if (s.clear) {S.wb = []; redrawWb(); return} S.wb.push(s); drawStroke(s)}
  S.A.re.onMessage = (e, {peerId}) => {flyReact(e.e); const p = S.peers.get(peerId); if (p && e.e) sys(p.name + ' ' + e.e)}
  S.A.cmd.onMessage = (c, {peerId}) => {
    const p = S.peers.get(peerId)
    if (c.c === 'locked') {toast('이 회의는 진행자가 잠갔습니다.', 6000); leave(true); return}
    if (!p || !p.host) return // 진행자 명령만 수행
    if (c.c === 'mute' && (!c.to || c.to === selfId)) {setMic(false); toast('진행자가 마이크를 껐습니다.')}
    if (c.c === 'camoff' && (!c.to || c.to === selfId)) {setCam(false); toast('진행자가 카메라를 껐습니다.')}
    if (c.c === 'lower' && (!c.to || c.to === selfId)) {S.me.hand = false; sendState(); buildToolbar()}
    if (c.c === 'kick' && c.to === selfId) {toast('진행자가 회의에서 내보냈습니다.', 6000); leave(true)}
    if (c.c === 'lock') {S.locked = !!c.v; $('rLock').hidden = !S.locked; sys(S.locked ? '진행자가 회의를 잠갔습니다(새 입장 차단).' : '진행자가 회의 잠금을 풀었습니다.')}
    if (c.c === 'end') {toast('진행자가 회의를 종료했습니다.', 6000); leave(true)}
  }
}
function sendState(target) {if (!S.A.st) return; const d = {name: S.me.name, mic: S.me.mic, cam: S.me.cam && !!S.sendVideo, hand: S.me.hand, sharing: !!S.screen}; if (S.isHost) d.hk = S.cfg.hk; S.A.st.send(d, target ? {target} : undefined)}
function sys(t) {S.chat.push({id: rnd(), sys: true, text: t, at: Date.now()}); renderSide()}
function att(id, name, ev) {S.att.push({id, name, ev, at: Date.now()})}

/* ---------- 마이크·카메라·화면 ---------- */
function setMic(on) {S.me.mic = on; const a = S.local.getAudioTracks()[0]; if (a) a.enabled = on; else if (on) toast('마이크 장치가 없습니다.'); sendState(); buildToolbar(); renderGrid()}
function setCam(on) {
  if (on && !S.rawVideo) {toast('카메라 장치가 없거나 권한이 없습니다.'); return}
  S.me.cam = on; if (S.rawVideo) S.rawVideo.enabled = on; if (S.sendVideo && S.sendVideo !== S.rawVideo) S.sendVideo.enabled = on
  sendState(); buildToolbar(); renderGrid()
}
async function toggleScreen() {
  if (S.screen) {stopScreen(); return}
  if (!navigator.mediaDevices.getDisplayMedia) {toast('이 기기 브라우저는 화면 공유를 지원하지 않습니다(PC 브라우저 사용).'); return}
  try {
    S.screen = await navigator.mediaDevices.getDisplayMedia({video: {frameRate: {ideal: 15, max: 30}}, audio: true})
    const vt = S.screen.getVideoTracks()[0]; vt.contentHint = 'detail'; vt.onended = stopScreen
    S.room.addStream(S.screen, {metadata: {kind: 'screen'}}); S.pinned = selfId + ':screen'
    sendState(); tuneSenders(); buildToolbar(); renderGrid()
  } catch (e) {if (e.name !== 'NotAllowedError') toast('화면 공유 실패: ' + e.message); S.screen = null}
}
function stopScreen() {if (!S.screen) return; try {S.room.removeStream(S.screen)} catch (e) {} S.screen.getTracks().forEach(t => t.stop()); S.screen = null; if (S.pinned === selfId + ':screen') S.pinned = null; sendState(); buildToolbar(); renderGrid()}
async function switchCamera() {
  try {
    const cur = S.rawVideo && S.rawVideo.getSettings().facingMode
    const s = await navigator.mediaDevices.getUserMedia({video: Object.assign(vConstraints(''), {facingMode: cur === 'environment' ? 'user' : 'environment'})})
    const nt = s.getVideoTracks()[0]; await replaceVideo(nt, true); toast(cur === 'environment' ? '전면 카메라' : '후면 카메라')
  } catch (e) {toast('카메라 전환 실패: ' + e.message)}
}
async function replaceVideo(nt, isRaw) {
  const old = S.sendVideo
  if (isRaw) {if (S.rawVideo && S.rawVideo !== nt) {S.local.removeTrack(S.rawVideo); S.rawVideo.stop()} S.rawVideo = nt; S.local.addTrack(nt); if (S.blur) {S.blur.setSource(nt); return}}
  nt.enabled = S.me.cam
  if (old && old !== nt) {try {await S.room.replaceTrack(old, nt)} catch (e) {console.warn(e)}} else if (!old) {S.room.addTrack(nt, S.local, {metadata: {kind: 'cam'}})}
  if (!isRaw && old && old !== S.rawVideo) old.stop()
  S.sendVideo = nt; renderGrid()
}

/* ---------- 배경 흐림(MediaPipe 셀피 분할) ---------- */
async function toggleBlur(on) {
  if (on === undefined) on = !S.blur
  if (!on) {if (S.blur) {const b = S.blur; S.blur = null; b.stop(); if (S.rawVideo) await replaceVideo(S.rawVideo, false)} buildToolbar(); return}
  if (!S.rawVideo) {toast('카메라가 없습니다.'); return}
  toast('배경 흐림 준비 중…', 6000)
  try {
    const V = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14'
    const {FilesetResolver, ImageSegmenter} = await import(/* @vite-ignore */ V + '/vision_bundle.mjs')
    const fs = await FilesetResolver.forVisionTasks(V + '/wasm')
    const mkSeg = delegate => ImageSegmenter.createFromOptions(fs, {baseOptions: {modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite', delegate}, runningMode: 'VIDEO', outputCategoryMask: false, outputConfidenceMasks: true})
    let seg; try {seg = await mkSeg('GPU')} catch (e) {seg = await mkSeg('CPU')}
    const vid = h('video', {muted: true, playsinline: true}); vid.muted = true
    const W = 640, H = 360, out = h('canvas', {width: W, height: H}), m = h('canvas', {width: W, height: H}), pc = h('canvas', {width: W, height: H})
    const ox = out.getContext('2d'), mx = m.getContext('2d'), px = pc.getContext('2d'); let stop = false, img = mx.createImageData(W, H), last = -1
    const b = {setSource(t) {vid.srcObject = new MediaStream([t]); vid.play().catch(() => {})}, stop() {stop = true; try {seg.close()} catch (e) {} track.stop()}}
    b.setSource(S.rawVideo)
    const loop = () => {
      if (stop) return
      if (vid.readyState >= 2 && vid.currentTime !== last) {
        last = vid.currentTime
        seg.segmentForVideo(vid, performance.now(), res => {
          const mask = res.confidenceMasks && res.confidenceMasks[0]
          if (mask) {const f = mask.getAsFloat32Array(), mw = mask.width, mh = mask.height
            if (img.width !== mw || img.height !== mh) {m.width = mw; m.height = mh; img = mx.createImageData(mw, mh)}
            for (let i = 0, j = 3; i < f.length; i++, j += 4) img.data[j] = f[i] * 255
            mx.putImageData(img, 0, 0)}
          px.globalCompositeOperation = 'source-over'; px.drawImage(vid, 0, 0, W, H); px.globalCompositeOperation = 'destination-in'; px.drawImage(m, 0, 0, W, H)
          ox.filter = 'blur(14px)'; ox.drawImage(vid, 0, 0, W, H); ox.filter = 'none'; ox.drawImage(pc, 0, 0)
          res.close && res.close()
        })
      }
      requestAnimationFrame(loop)
    }
    loop()
    const track = out.captureStream(24).getVideoTracks()[0]
    S.blur = b; await replaceVideo(track, false); toast('배경 흐림을 켰습니다.')
  } catch (e) {console.warn(e); toast('배경 흐림을 사용할 수 없습니다(브라우저 미지원 또는 네트워크).'); S.blur = null}
  buildToolbar()
}

/* ---------- 인원수 맞춤 화질(mesh 대역폭 관리) ---------- */
function tuneSenders() {
  const n = S.peers.size
  let q = S.quality
  if (q === 'auto') q = n <= 3 ? 'hd' : n <= 7 ? 'sd' : 'low'
  const br = Q[q].br, scale = q === 'hd' ? 1 : q === 'sd' ? 2 : 3
  try {
    for (const pc of Object.values(S.room.getPeers())) for (const s of pc.getSenders()) {
      if (!s.track || s.track.kind !== 'video') continue
      const isScreen = S.screen && S.screen.getVideoTracks().includes(s.track)
      const p = s.getParameters(); if (!p.encodings || !p.encodings.length) p.encodings = [{}]
      p.encodings[0].maxBitrate = isScreen ? Math.max(800000, 2500000 / Math.max(1, n / 2)) : br
      p.encodings[0].scaleResolutionDownBy = isScreen ? 1 : scale
      if (isScreen) p.encodings[0].maxFramerate = 15
      s.setParameters(p).catch(() => {})
    }
  } catch (e) {}
  S.curQ = q
}

/* ---------- 말하는 사람 감지 ---------- */
function watchSpeaking(id, stream) {stopMeter(id); const st = meter(stream, l => {const sp = l > 0.035; const el = document.querySelector(`[data-tid="${CSS.escape(id + ':cam')}"]`); if (el) el.classList.toggle('spk', sp && (id !== selfId || S.me.mic)); if (sp && id !== selfId) {S.speaker = id; S.speakerAt = Date.now()}}); S.meters.set(id, st)}
function stopMeter(id) {const f = S.meters.get(id); if (f) f(); S.meters.delete(id)}

/* ---------- 화면 배치 ---------- */
const tiles = new Map()
function tileList() {
  const L = []
  if (S.screen) L.push({tid: selfId + ':screen', id: selfId, self: true, screen: true, stream: S.screen, name: S.me.name + ' (화면)', mic: true, cam: true})
  for (const p of S.peers.values()) if (p.streams.screen) L.push({tid: p.id + ':screen', id: p.id, screen: true, stream: p.streams.screen, name: p.name + ' (화면)', mic: true, cam: true})
  if (!S.selfView || S.selfView.getVideoTracks()[0] !== S.sendVideo) S.selfView = S.sendVideo ? new MediaStream([S.sendVideo]) : null
  L.push({tid: selfId + ':cam', id: selfId, self: true, stream: S.selfView, name: S.me.name + ' (나)', mic: S.me.mic, cam: S.me.cam && !!S.sendVideo, hand: S.me.hand, host: S.isHost})
  for (const p of S.peers.values()) L.push({tid: p.id + ':cam', id: p.id, stream: p.streams.cam || null, name: p.name, mic: p.mic, cam: p.cam, hand: p.hand, host: p.host, q: p.q})
  return L
}
function renderGrid() {
  const g = $('grid'), L = tileList(), seen = new Set()
  for (const t of L) {
    seen.add(t.tid); let el = tiles.get(t.tid)
    if (!el) {
      const v = h('video', {autoplay: true, playsinline: true}); v.muted = !!t.self || t.screen && t.self
      el = h('div', {class: 'tile', 'data-tid': t.tid}, v, h('div', {class: 'av'}, h('b')), h('div', {class: 'q'}), h('div', {class: 'nm'}, h('span')), h('div', {class: 'ic'}),
        h('div', {class: 'tb2'}, h('button', {type: 'button', onclick: () => {S.pinned = S.pinned === t.tid ? null : t.tid; renderGrid()}}, '고정'), h('button', {type: 'button', onclick: () => pip(el.querySelector('video'))}, 'PIP'), h('button', {type: 'button', onclick: () => el.requestFullscreen?.().catch(() => {})}, '전체')))
      el.ondblclick = () => {S.pinned = S.pinned === t.tid ? null : t.tid; renderGrid()}
      tiles.set(t.tid, el)
    }
    const v = el.querySelector('video')
    if (t.stream && v.srcObject !== t.stream) {v.srcObject = t.stream; v.play().catch(() => {})}
    if (!t.self && S.devices.spk && v.setSinkId) v.setSinkId(S.devices.spk).catch(() => {})
    el.classList.toggle('self', !!t.self); el.classList.toggle('screen', !!t.screen); el.classList.toggle('pin', S.pinned === t.tid)
    const showVid = !!t.stream && (t.screen || t.cam)
    v.style.visibility = showVid ? 'visible' : 'hidden'
    const av = el.querySelector('.av'); av.hidden = showVid; const b = av.querySelector('b'); b.textContent = ini(t.name); b.style.background = colOf(t.id)
    el.querySelector('.nm span').textContent = t.name
    const nm = el.querySelector('.nm'); nm.querySelector('i')?.remove(); if (!t.screen && !t.mic) nm.prepend(h('i', {style: 'font-style:normal'}, '🔇'))
    el.querySelector('.ic').replaceChildren(...[t.host ? h('i', null, '진행자') : null, t.hand ? h('i', null, '✋') : null].filter(Boolean))
    el.querySelector('.q').textContent = t.q ? t.q : ''; el.querySelector('.q').hidden = !t.q
  }
  for (const [tid, el] of tiles) if (!seen.has(tid)) {el.querySelector('video').srcObject = null; el.remove(); tiles.delete(tid)}
  // 배치: 고정/화면공유는 크게, 나머지 하단 띠
  const pin = S.pinned && tiles.get(S.pinned) ? S.pinned : null
  const order = L.map(t => tiles.get(t.tid))
  const st = $('stage'), W = st.clientWidth - 20, H = st.clientHeight - 20
  g.style.gridTemplateColumns = ''; g.style.gridTemplateRows = ''
  if (pin && L.length > 1) {
    const others = order.filter(e => e.dataset.tid !== pin), narrow = W < 700
    const strip = narrow ? Math.min(others.length, 3) : Math.min(others.length, 6)
    const big = tiles.get(pin)
    if (narrow) {g.style.gridTemplateColumns = `repeat(${Math.max(strip, 1)},minmax(0,1fr))`; g.style.gridTemplateRows = `minmax(0,1fr) ${Math.round(H * 0.22)}px`; big.style.gridColumn = `1 / -1`}
    else {g.style.gridTemplateColumns = `minmax(0,1fr) ${Math.round(Math.min(W * 0.22, 260))}px`; g.style.gridTemplateRows = `repeat(${Math.max(strip, 1)},minmax(0,1fr))`; big.style.gridColumn = '1'; big.style.gridRow = `1 / span ${Math.max(strip, 1)}`}
    big.style.width = '100%'; big.style.height = '100%'; big.style.aspectRatio = 'auto'; big.classList.add('fit')
    g.replaceChildren(big, ...others.slice(0, strip).map(e => {e.style.cssText = 'width:100%;height:100%;aspect-ratio:auto'; e.classList.remove('fit'); return e}))
    g.style.alignContent = 'stretch'; g.style.justifyContent = 'stretch'
    return
  }
  // 균등 격자: 화면에 맞는 최적 열 수
  const n = order.length; let best = {c: 1, w: 0}
  for (let c = 1; c <= n; c++) {const r = Math.ceil(n / c); const w = Math.min((W - (c - 1) * 8) / c, ((H - (r - 1) * 8) / r) * 16 / 9); if (w > best.w) best = {c, w}}
  g.style.gridTemplateColumns = `repeat(${best.c},${Math.floor(best.w)}px)`; g.style.alignContent = 'center'; g.style.justifyContent = 'center'
  g.replaceChildren(...order.map(e => {e.style.cssText = ''; e.classList.remove('fit'); return e}))
  $('rCount').textContent = (S.peers.size + 1) + '명'
}
window.addEventListener('resize', () => {if (S.room) renderGrid()})
async function pip(v) {try {if (document.pictureInPictureElement) await document.exitPictureInPicture(); else await v.requestPictureInPicture()} catch (e) {toast('이 브라우저는 PIP를 지원하지 않습니다.')}}

/* ---------- 도구 모음 ---------- */
function buildToolbar() {
  const B = (id, ic, lab, cls, fn, badge) => h('button', {type: 'button', class: cls || '', id, 'aria-label': lab, onclick: fn}, h('span', {class: 'ci', html: ''}), h('span', null, lab), badge ? h('span', {class: 'badge'}, badge) : null)
  const items = [
    B('tMic', S.me.mic ? 'mic' : 'micoff', S.me.mic ? '음소거' : '음소거 해제', S.me.mic ? '' : 'off', () => setMic(!S.me.mic)),
    B('tCam', S.me.cam ? 'cam' : 'camoff', S.me.cam ? '비디오 끄기' : '비디오 켜기', S.me.cam ? '' : 'off', () => setCam(!S.me.cam)),
    B('tScr', 'screen', S.screen ? '공유 중지' : '화면 공유', (S.screen ? 'on ' : '') + 'opt', toggleScreen),
    B('tHand', 'hand', S.me.hand ? '손 내리기' : '손들기', (S.me.hand ? 'on ' : '') + 'opt', () => {S.me.hand = !S.me.hand; sendState(); buildToolbar(); renderGrid()}),
    B('tRe', 'react', '반응', 'opt', e => reactMenu(e.currentTarget)),
    B('tChat', 'chat', '채팅', S.side === 'chat' ? 'on' : '', () => openSide('chat'), S.unread ? String(S.unread) : null),
    B('tPpl', 'ppl', '참여자 ' + (S.peers.size + 1), S.side === 'ppl' ? 'on' : '', () => openSide('ppl')),
    B('tCc', 'cc', S.capOn ? '자막 끄기' : '자막', (S.capOn ? 'on ' : '') + 'opt', toggleCaptions),
    B('tWb', 'wb', '화이트보드', ($('wb').hidden ? '' : 'on ') + 'opt', toggleWb),
    B('tMore', 'more', '더보기', '', e => moreMenu(e.currentTarget)),
    B('tLeave', 'leave', '나가기', 'leave', () => leaveMenu()),
  ]
  $('tb').replaceChildren(...items)
  const icmap = {tMic: S.me.mic ? 'mic' : 'micoff', tCam: S.me.cam ? 'cam' : 'camoff', tScr: 'screen', tHand: 'hand', tRe: 'react', tChat: 'chat', tPpl: 'ppl', tCc: 'cc', tWb: 'wb', tMore: 'more', tLeave: 'leave'}
  for (const [id, ic] of Object.entries(icmap)) $(id).querySelector('.ci').innerHTML = IC[ic]
  $('rRec').hidden = !S.rec
}
function popMenu(anchor, kids, cls) {document.querySelectorAll('.menu').forEach(m => m.remove()); const m = h('div', {class: 'menu ' + (cls || '')}, kids); document.body.append(m)
  setTimeout(() => document.addEventListener('click', function f(e) {if (!m.contains(e.target)) {m.remove(); document.removeEventListener('click', f)}}), 0); return m}
function reactMenu(a) {popMenu(a, h('div', {class: 'rmenu'}, ['👍', '👏', '😄', '🎉', '❤️', '🤔', '🙏'].map(e => h('button', {type: 'button', onclick: () => {S.A.re.send({e}); flyReact(e); document.querySelector('.menu')?.remove()}}, e))))}
function flyReact(e) {const f = h('div', {class: 'fly', style: `left:${10 + Math.random() * 80}%`}, e); $('reacts').append(f); setTimeout(() => f.remove(), 3100)}
function moreMenu(a) {
  const M = (t, fn) => h('button', {type: 'button', onclick: () => {document.querySelector('.menu')?.remove(); fn()}}, t)
  const narrow = matchMedia('(max-width:640px)').matches
  popMenu(a, [
    narrow ? M(S.me.hand ? '✋ 손 내리기' : '✋ 손들기(발언 요청)', () => {S.me.hand = !S.me.hand; sendState(); buildToolbar(); renderGrid()}) : null,
    narrow ? M('😄 반응 보내기', () => reactMenu(a)) : null,
    narrow ? M(S.screen ? '🖥 화면 공유 중지' : '🖥 화면 공유', toggleScreen) : null,
    narrow ? M(S.capOn ? '💬 자막 끄기' : '💬 실시간 자막 켜기', toggleCaptions) : null,
    narrow ? M($('wb').hidden ? '✏ 화이트보드' : '✏ 화이트보드 닫기', toggleWb) : null,
    M('🔗 초대 링크 복사', () => copy(linkFor(S.cfg, false), '초대 링크를 복사했습니다.')),
    M(S.rec ? '⏹ 녹화 중지·저장' : '⏺ 회의 녹화(이 기기에 저장)', toggleRec),
    M('📝 회의록 저장(.txt)', saveMinutes),
    M('📋 회의록 복사(포털 붙여넣기용)', () => copy(minutesText(), '회의록을 복사했습니다. 과업 포털 회의록에 붙여넣으세요.')),
    M(S.blur ? '🌫 배경 흐림 끄기' : '🌫 배경 흐림(AI)', () => toggleBlur()),
    S.rawVideo ? M('🔄 전면/후면 카메라 전환', switchCamera) : null,
    M('⚙ 장치·화질 설정', settingsModal),
    M('📶 연결 품질·통계', statsModal),
    M(S.pinned ? '▦ 격자 보기' : '▣ 발표자 보기', () => {S.pinned = S.pinned ? null : (S.speaker ? S.speaker + ':cam' : [...tiles.keys()][0]); renderGrid()}),
    M('⛶ 전체 화면', () => document.documentElement.requestFullscreen?.().catch(() => {})),
    S.isHost ? M('🔇 전체 음소거(진행자)', () => {S.A.cmd.send({c: 'mute'}); toast('전체 음소거를 요청했습니다.')}) : null,
    S.isHost ? M(S.locked ? '🔓 회의 잠금 해제' : '🔐 회의 잠금(새 입장 차단)', () => {S.locked = !S.locked; S.A.cmd.send({c: 'lock', v: S.locked}); $('rLock').hidden = !S.locked; sys(S.locked ? '회의를 잠갔습니다.' : '잠금을 풀었습니다.')}) : null,
    M('↗ 과업 포털 열기', () => window.open(PORTAL, '_blank', 'noopener')),
  ].filter(Boolean))
}
function leaveMenu() {
  if (!S.isHost) {leave(); return}
  const m = h('div', {class: 'modal', onclick: e => {if (e.target === m) m.remove()}}, h('div', {class: 'card'}, h('b', null, '회의를 나가시겠습니까?'), h('div', {class: 'small muted'}, '진행자가 “모두 종료”하면 모든 참여자의 회의가 끝납니다.'),
    h('div', {style: 'display:flex;gap:8px;flex-wrap:wrap'}, h('button', {class: 'btn', type: 'button', onclick: () => {m.remove(); leave()}}, '나만 나가기'), h('button', {class: 'btn dng', type: 'button', onclick: () => {S.A.cmd.send({c: 'end'}); setTimeout(() => leave(), 400); m.remove()}}, '모두 종료'), h('button', {class: 'btn', type: 'button', onclick: () => m.remove()}, '취소'))))
  $('host').replaceChildren(m)
}
function leave(forced) {
  if (S.rec) toggleRec()
  try {S.room.leave()} catch (e) {}
  S.local?.getTracks().forEach(t => t.stop()); S.screen?.getTracks().forEach(t => t.stop()); S.blur?.stop()
  if (S.recog) try {S.recog.stop()} catch (e) {}
  const m = h('div', {class: 'modal'}, h('div', {class: 'card'}, h('b', null, forced ? '회의가 종료되었습니다.' : '회의에서 나왔습니다.'), h('div', {class: 'small muted'}, '회의 시간 ' + $('rTime').textContent + ' · 참석 ' + new Set(S.att.filter(a => a.ev === 'join').map(a => a.name)).size + '명'),
    h('div', {style: 'display:flex;gap:8px;flex-wrap:wrap'}, h('button', {class: 'btn pri', type: 'button', onclick: saveMinutes}, '회의록 저장'), h('button', {class: 'btn', type: 'button', onclick: () => copy(minutesText(), '회의록을 복사했습니다.')}, '회의록 복사'), h('button', {class: 'btn', type: 'button', onclick: () => location.reload()}, '다시 참여'), h('a', {class: 'btn', href: PORTAL, target: '_blank', rel: 'noopener', style: 'text-decoration:none'}, '과업 포털'))))
  $('host').replaceChildren(m)
}

/* ---------- 사이드 패널: 채팅·참여자·자막 ---------- */
function openSide(p) {S.side = S.side === p ? null : p; if (S.side === 'chat') S.unread = 0; renderSide(); buildToolbar(); setTimeout(renderGrid, 0)}
document.querySelectorAll('.stabs button').forEach(b => b.onclick = () => {const p = b.dataset.p; if (p === 'x') {S.side = null} else {S.side = p; if (p === 'chat') S.unread = 0} renderSide(); buildToolbar(); setTimeout(renderGrid, 0)})
const fileProg = new Map()
function setFileProg(fid, pct) {fileProg.set(fid, pct); const el = document.querySelector(`[data-fid="${CSS.escape(fid)}"]`); if (el) el.textContent = Math.round(pct * 100) + '%'}
function renderSide() {
  $('side').hidden = !S.side
  document.querySelectorAll('.stabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.p === S.side)))
  $('pChat').hidden = S.side !== 'chat'; $('pPpl').hidden = S.side !== 'ppl'; $('pCap').hidden = S.side !== 'cap'; $('chatForm').hidden = S.side !== 'chat'
  if (S.side === 'chat') {
    const box = $('pChat'), atB = box.scrollHeight - box.scrollTop - box.clientHeight < 60
    box.replaceChildren(...(S.chat.length ? S.chat.map(m => m.sys ? h('div', {class: 'msg sys'}, hhmm(m.at) + ' · ' + m.text) :
      h('div', {class: 'msg'}, h('b', {style: `color:${colOf(m.name)}`}, m.name), h('span', {class: 't'}, hhmm(m.at)),
        m.file ? h('div', null, '📎 ', m.file.url ? h('a', {href: m.file.url, download: m.file.name}, m.file.name) : h('span', null, m.file.name), h('span', {class: 't'}, (m.file.size / 1048576).toFixed(1) + 'MB'), m.file.sending ? h('span', {class: 't', 'data-fid': m.id}, '전송 중') : null) : h('div', {class: 'x'}, m.text))) : [h('div', {class: 'muted small'}, '메시지가 없습니다.')]))
    if (atB) box.scrollTop = box.scrollHeight
  }
  if (S.side === 'ppl') {
    const rows = [{id: selfId, name: S.me.name + ' (나)', mic: S.me.mic, cam: S.me.cam, hand: S.me.hand, host: S.isHost, self: true}, ...S.peers.values()]
    $('pPpl').replaceChildren(h('div', {class: 'small muted'}, '참여자 ' + rows.length + '명' + (S.locked ? ' · 잠김' : '')),
      ...rows.map(p => h('div', {class: 'prow'}, h('span', {class: 'avs', style: `background:${colOf(p.id)}`}, ini(p.name)), h('span', {class: 'n'}, p.name + (p.host ? ' · 진행자' : '')), h('span', null, (p.hand ? '✋' : '') + (p.mic ? '' : '🔇') + (p.cam ? '' : '📷✕')),
        S.isHost && !p.self ? [h('button', {type: 'button', onclick: () => S.A.cmd.send({c: 'mute', to: p.id}, {target: p.id})}, '음소거'), p.hand ? h('button', {type: 'button', onclick: () => S.A.cmd.send({c: 'lower', to: p.id}, {target: p.id})}, '손 내림') : null, h('button', {type: 'button', onclick: () => {S.A.cmd.send({c: 'kick', to: p.id}, {target: p.id}); sys(p.name + ' 님을 내보냈습니다.')}}, '내보내기')] : null)),
      h('div', {class: 'small muted', style: 'margin-top:8px'}, '출석 기록'), ...attSummary().map(a => h('div', {class: 'small'}, a)),
      h('div', {style: 'margin-top:8px'}, h('button', {class: 'btn', type: 'button', onclick: () => copy(linkFor(S.cfg, false), '초대 링크를 복사했습니다.')}, '초대 링크 복사')))
  }
  if (S.side === 'cap') {
    $('pCap').replaceChildren(h('div', {style: 'display:flex;gap:6px;flex-wrap:wrap'}, h('button', {class: 'btn' + (S.capOn ? ' pri' : ''), type: 'button', onclick: toggleCaptions}, S.capOn ? '내 자막 끄기' : '내 음성 자막 켜기'), h('button', {class: 'btn', type: 'button', onclick: saveMinutes}, '회의록 저장'), h('button', {class: 'btn', type: 'button', onclick: () => copy(minutesText(), '회의록을 복사했습니다.')}, '복사')),
      h('div', {class: 'small muted'}, '각 참여자가 “자막 켜기”를 하면 그 사람의 말이 텍스트로 모두에게 표시되고 회의록에 기록됩니다(Chrome·Edge·Safari).'),
      ...(S.caps.length ? S.caps.map(c => h('div', {class: 'cap'}, h('b', null, hhmm(c.at) + ' ' + c.name), c.text)) : [h('div', {class: 'muted small'}, '자막 기록이 없습니다.')]))
  }
}
function attSummary() {const by = new Map(); for (const a of S.att) {const k = a.name; if (!by.has(k)) by.set(k, []); by.get(k).push(a)} return [...by].map(([n, es]) => n + ' — ' + es.map(e => (e.ev === 'join' ? '입장 ' : '퇴장 ') + hhmm(e.at)).join(', '))}
$('chatForm').onsubmit = e => {e.preventDefault(); const t = $('chatIn').value.trim(); if (!t) return; const m = {id: rnd(), name: S.me.name, text: t.slice(0, 2000), at: Date.now()}; S.chat.push(m); S.A.chat.send(m); $('chatIn').value = ''; renderSide()}
$('btnFile').onclick = () => $('fileIn').click()
$('fileIn').onchange = async e => {
  const f = e.target.files[0]; e.target.value = ''; if (!f) return; if (f.size > 200 * 1024 * 1024) {toast('200MB 이하 파일만 보낼 수 있습니다.'); return}
  if (!S.peers.size) {toast('받을 참여자가 없습니다.'); return}
  const fid = rnd(); const m = {id: fid, name: S.me.name, at: Date.now(), file: {name: f.name, size: f.size, url: URL.createObjectURL(f), sending: true}}; S.chat.push(m); renderSide()
  try {await S.A.file.send(await f.arrayBuffer(), {metadata: {name: f.name, type: f.type, fid}, onProgress: p => setFileProg(fid, p)}); m.file.sending = false; renderSide(); toast('파일을 보냈습니다: ' + f.name)} catch (err) {toast('파일 전송 실패: ' + err.message)}
}

/* ---------- 실시간 자막(Web Speech API) ---------- */
function toggleCaptions() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SR) {toast('이 브라우저는 음성 인식을 지원하지 않습니다(Chrome·Edge·Safari 사용).'); return}
  if (S.capOn) {S.capOn = false; try {S.recog.stop()} catch (e) {} buildToolbar(); renderSide(); return}
  const r = new SR(); r.lang = 'ko-KR'; r.continuous = true; r.interimResults = true
  r.onresult = ev => {for (let i = ev.resultIndex; i < ev.results.length; i++) {const res = ev.results[i]; const c = {id: rnd(), name: S.me.name, text: res[0].transcript.trim(), at: Date.now(), final: res.isFinal}; if (!c.text) continue; if (!S.me.mic) continue; S.A.cap.send(c); showCap(c); if (c.final) {S.caps.push(c); renderSide()}}}
  r.onend = () => {if (S.capOn) try {r.start()} catch (e) {}}
  r.onerror = e => {if (e.error === 'not-allowed') {S.capOn = false; toast('음성 인식 권한이 거부되었습니다.'); buildToolbar()}}
  S.recog = r; S.capOn = true; try {r.start()} catch (e) {} buildToolbar(); toast('내 음성 자막을 켰습니다. 말하는 내용이 모두에게 표시되고 회의록에 기록됩니다.')
}
let capT; function showCap(c) {const b = $('capbar'); b.hidden = false; b.textContent = c.name + ': ' + c.text; clearTimeout(capT); capT = setTimeout(() => b.hidden = true, 4000)}

/* ---------- 화이트보드 ---------- */
const WB = {color: '#1b2a38', size: 3, erase: false, cur: null}
function toggleWb() {const w = $('wb'); w.hidden = !w.hidden; if (!w.hidden) {buildWbTools(); fitWb(); redrawWb()} buildToolbar()}
function buildWbTools() {
  const t = $('wbt'); const cols = ['#1b2a38', '#c4362b', '#2b62a3', '#2c8a4b', '#cf7a1d']
  t.replaceChildren(...cols.map(c => h('button', {class: 'sw', type: 'button', style: `background:${c}`, 'aria-pressed': String(!WB.erase && WB.color === c), 'aria-label': '색 ' + c, onclick: () => {WB.color = c; WB.erase = false; buildWbTools()}})),
    h('button', {type: 'button', 'aria-pressed': String(WB.size === 3), onclick: () => {WB.size = 3; buildWbTools()}}, '가늘게'), h('button', {type: 'button', 'aria-pressed': String(WB.size === 8), onclick: () => {WB.size = 8; buildWbTools()}}, '굵게'),
    h('button', {type: 'button', 'aria-pressed': String(WB.erase), onclick: () => {WB.erase = !WB.erase; buildWbTools()}}, '지우개'),
    h('button', {type: 'button', onclick: () => {S.wb = []; S.A.wb.send({clear: 1}); redrawWb()}}, '모두 지우기'),
    h('button', {type: 'button', onclick: () => {const a = h('a', {href: $('wbc').toDataURL('image/png'), download: '화이트보드_' + new Date().toISOString().slice(0, 16).replace(/[:T]/g, '') + '.png'}); a.click()}}, 'PNG 저장'),
    h('button', {type: 'button', onclick: toggleWb}, '닫기'))
}
function fitWb() {const c = $('wbc'), r = c.getBoundingClientRect(), d = devicePixelRatio || 1; c.width = Math.round(r.width * d); c.height = Math.round(r.height * d)}
function drawStroke(s) {const c = $('wbc'); if ($('wb').hidden) return; const x = c.getContext('2d'), W = c.width, H = c.height, d = devicePixelRatio || 1
  x.lineCap = 'round'; x.lineJoin = 'round'; x.strokeStyle = s.e ? '#f6f7f2' : s.c; x.lineWidth = (s.e ? 24 : s.w) * d; x.beginPath()
  s.p.forEach(([px, py], i) => i ? x.lineTo(px * W, py * H) : x.moveTo(px * W, py * H)); if (s.p.length === 1) x.lineTo(s.p[0][0] * W + 0.1, s.p[0][1] * H); x.stroke()}
function redrawWb() {const c = $('wbc'); if ($('wb').hidden) return; c.getContext('2d').clearRect(0, 0, c.width, c.height); S.wb.forEach(drawStroke)}
;(() => {
  const c = $('wbc'), pos = e => {const r = c.getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]}
  c.addEventListener('pointerdown', e => {c.setPointerCapture(e.pointerId); WB.cur = {id: rnd(), c: WB.color, w: WB.size, e: WB.erase ? 1 : 0, p: [pos(e)]}})
  c.addEventListener('pointermove', e => {if (!WB.cur) return; WB.cur.p.push(pos(e)); const s = {...WB.cur, p: WB.cur.p.slice(-2)}; drawStroke(s)})
  c.addEventListener('pointerup', () => {if (!WB.cur) return; const s = WB.cur; WB.cur = null; s.p = s.p.map(([a, b]) => [Math.round(a * 1e4) / 1e4, Math.round(b * 1e4) / 1e4]); S.wb.push(s); S.A.wb.send(s)})
  window.addEventListener('resize', () => {if (!$('wb').hidden) {fitWb(); redrawWb()}})
})()

/* ---------- 녹화(격자 합성 + 음성 믹스) ---------- */
function toggleRec() {
  if (S.rec) {S.rec.stop(); return}
  if (!window.MediaRecorder) {toast('이 브라우저는 녹화를 지원하지 않습니다.'); return}
  const W = 1280, H = 720, cv = h('canvas', {width: W, height: H}), x = cv.getContext('2d')
  const ctx = audioCtx(), dest = ctx.createMediaStreamDestination(), srcs = new Map()
  const mix = () => {const streams = [S.local, ...[...S.peers.values()].map(p => p.streams.cam), S.screen].filter(Boolean)
    for (const s of streams) {const a = s.getAudioTracks()[0]; if (a && !srcs.has(a.id)) {try {const n = ctx.createMediaStreamSource(new MediaStream([a])); n.connect(dest); srcs.set(a.id, n)} catch (e) {}}}}
  let stop = false
  const draw = () => {
    if (stop) return; mix()
    x.fillStyle = '#0b141c'; x.fillRect(0, 0, W, H)
    const vids = [...document.querySelectorAll('#grid .tile')].map(t => ({v: t.querySelector('video'), n: t.querySelector('.nm span').textContent, show: t.querySelector('video').style.visibility !== 'hidden', screen: t.classList.contains('screen')}))
    const pinned = vids.find(v => v.screen)
    const list = pinned ? [pinned, ...vids.filter(v => v !== pinned)] : vids
    if (pinned) {const bw = W * 0.78; place(list[0], 0, 0, bw, H); list.slice(1, 6).forEach((v, i) => place(v, bw, i * H / 5, W - bw, H / 5))}
    else {const n = list.length, c = Math.ceil(Math.sqrt(n)), r = Math.ceil(n / c); list.forEach((v, i) => place(v, (i % c) * W / c, Math.floor(i / c) * H / r, W / c, H / r))}
    x.fillStyle = 'rgba(0,0,0,.55)'; x.fillRect(0, 0, 420, 28); x.fillStyle = '#fff'; x.font = '14px sans-serif'; x.fillText((S.cfg.title || '회의') + ' · ' + new Date().toLocaleString('ko-KR'), 8, 19)
    setTimeout(draw, 1000 / 15)
  }
  function place(v, px, py, pw, ph) {x.save(); x.beginPath(); x.rect(px + 2, py + 2, pw - 4, ph - 4); x.clip(); x.fillStyle = '#05090d'; x.fillRect(px, py, pw, ph)
    if (v.show && v.v.videoWidth) {const s = Math.min(pw / v.v.videoWidth, ph / v.v.videoHeight); const w = v.v.videoWidth * s, hh = v.v.videoHeight * s; x.drawImage(v.v, px + (pw - w) / 2, py + (ph - hh) / 2, w, hh)}
    else {x.fillStyle = '#93a6b6'; x.font = '20px sans-serif'; x.textAlign = 'center'; x.fillText(v.n, px + pw / 2, py + ph / 2); x.textAlign = 'start'}
    x.fillStyle = 'rgba(0,0,0,.55)'; x.fillRect(px + 6, py + ph - 26, Math.min(pw - 12, 12 + v.n.length * 13), 20); x.fillStyle = '#fff'; x.font = '13px sans-serif'; x.fillText(v.n, px + 12, py + ph - 11); x.restore()}
  draw()
  const out = new MediaStream([...cv.captureStream(15).getVideoTracks(), ...dest.stream.getAudioTracks()])
  const type = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm', 'video/mp4'].find(t => MediaRecorder.isTypeSupported(t)) || ''
  const rec = new MediaRecorder(out, type ? {mimeType: type, videoBitsPerSecond: 2500000} : undefined), chunks = []
  rec.ondataavailable = e => e.data.size && chunks.push(e.data)
  rec.onstop = () => {stop = true; srcs.forEach(n => n.disconnect()); const blob = new Blob(chunks, {type: rec.mimeType || 'video/webm'}); const ext = (rec.mimeType || '').includes('mp4') ? 'mp4' : 'webm'
    const a = h('a', {href: URL.createObjectURL(blob), download: (S.cfg.title || '회의') + '_' + new Date().toISOString().slice(0, 16).replace(/[:T]/g, '') + '.' + ext}); document.body.append(a); a.click(); a.remove(); S.rec = null; buildToolbar(); toast('녹화 파일을 저장했습니다.')}
  rec.start(1000); S.rec = rec; S.A.chat.send({id: rnd(), name: S.me.name, text: '⏺ 이 회의를 녹화하기 시작했습니다.', at: Date.now()}); sys('녹화를 시작했습니다(이 기기에 저장).'); buildToolbar()
}

/* ---------- 회의록 ---------- */
function minutesText() {
  const d = new Date(S.startAt), dur = Math.round((Date.now() - S.startAt) / 60000)
  const L = ['[회의록] ' + (S.cfg.title || '회의'), '일시: ' + d.toLocaleString('ko-KR') + ' (약 ' + dur + '분)', '방식: 항만 AI 화상회의(P2P 종단간 암호화)', '', '■ 참석자']
  L.push(...attSummary().map(a => '  - ' + a))
  L.push('', '■ 발언 자막'); if (S.caps.length) L.push(...S.caps.map(c => '  ' + hhmm(c.at) + ' ' + c.name + ': ' + c.text)); else L.push('  (자막 없음)')
  L.push('', '■ 채팅'); const ch = S.chat.filter(m => !m.sys); if (ch.length) L.push(...ch.map(m => '  ' + hhmm(m.at) + ' ' + m.name + ': ' + (m.file ? '[파일] ' + m.file.name : m.text))); else L.push('  (채팅 없음)')
  L.push('', '■ 결정 사항', '  - ', '', '■ 조치 사항(담당·기한)', '  - ')
  return L.join('\n')
}
function saveMinutes() {const blob = new Blob(['﻿' + minutesText()], {type: 'text/plain;charset=utf-8'}); const a = h('a', {href: URL.createObjectURL(blob), download: '회의록_' + (S.cfg.title || '회의') + '_' + new Date(S.startAt).toISOString().slice(0, 10) + '.txt'}); document.body.append(a); a.click(); a.remove()}

/* ---------- 연결 품질 ---------- */
const prevStats = new Map()
async function stats() {
  if (!S.room) return
  for (const [id, pc] of Object.entries(S.room.getPeers())) {
    try {
      const r = await pc.getStats(); let rtt = null, bytes = 0, w = 0, hgt = 0, lost = 0, recv = 0, type = ''
      r.forEach(s => {
        if (s.type === 'candidate-pair' && s.nominated && s.state === 'succeeded') {rtt = s.currentRoundTripTime; const lc = r.get(s.localCandidateId); type = lc ? lc.candidateType : ''}
        if (s.type === 'inbound-rtp' && s.kind === 'video') {bytes += s.bytesReceived || 0; w = s.frameWidth || w; hgt = s.frameHeight || hgt; lost += s.packetsLost || 0; recv += s.packetsReceived || 0}
      })
      const pv = prevStats.get(id), now = Date.now(); const kbps = pv ? Math.round((bytes - pv.bytes) * 8 / (now - pv.at)) : 0; prevStats.set(id, {bytes, at: now})
      const loss = recv ? lost / (lost + recv) * 100 : 0
      const p = S.peers.get(id); if (p) {p.stat = {rtt: rtt != null ? Math.round(rtt * 1000) : null, kbps, w, h: hgt, loss: Math.round(loss * 10) / 10, type}
        const bad = (rtt && rtt > 0.4) || loss > 5; const mid = (rtt && rtt > 0.2) || loss > 2
        p.q = bad ? '● 불안정' : mid ? '● 보통' : ''
        const el = tiles.get(id + ':cam'); if (el) {const q = el.querySelector('.q'); q.textContent = p.q; q.hidden = !p.q; q.style.color = bad ? '#e5484d' : '#f0a03c'}}
    } catch (e) {}
  }
}
function statsModal() {
  const rows = [...S.peers.values()].map(p => h('tr', null, h('td', null, p.name), h('td', {class: 'num'}, p.stat?.rtt != null ? p.stat.rtt + 'ms' : '–'), h('td', {class: 'num'}, p.stat ? p.stat.kbps + 'kbps' : '–'), h('td', {class: 'num'}, p.stat?.w ? p.stat.w + '×' + p.stat.h : '–'), h('td', {class: 'num'}, p.stat ? p.stat.loss + '%' : '–'), h('td', null, {host: '직접(LAN)', srflx: '직접(P2P)', prflx: '직접(P2P)', relay: 'TURN 중계'}[p.stat?.type] || '–')))
  const m = h('div', {class: 'modal', onclick: e => {if (e.target === m) m.remove()}}, h('div', {class: 'card'}, h('b', null, '연결 품질'),
    h('div', {class: 'small muted'}, '송출 화질: ' + ({hd: '720p', sd: '360p', low: '240p'}[S.curQ] || '-') + (S.quality === 'auto' ? ' (인원수 자동)' : '') + ' · 연결: 참여자 간 직접 연결(mesh) — 각자 다른 모든 참여자에게 직접 송출'),
    h('div', {style: 'overflow-x:auto'}, h('table', {class: 'st'}, h('tr', null, ['참여자', '지연', '수신', '해상도', '손실', '경로'].map(x => h('th', null, x))), rows.length ? rows : h('tr', null, h('td', {colspan: 6, class: 'muted'}, '연결된 참여자가 없습니다.')))),
    h('div', {class: 'small muted'}, '권장: 영상 포함 10명 이내. 인원이 많으면 “장치·화질 설정”에서 저대역(240p)을 고르거나 발언자 외에는 비디오를 끄세요.'),
    h('button', {class: 'btn', type: 'button', onclick: () => m.remove()}, '닫기')))
  $('host').replaceChildren(m)
}
function settingsModal() {
  const qSel = h('select', {id: 'mq'}, [['auto', '자동(인원수 맞춤)'], ['hd', '고화질 720p'], ['sd', '표준 360p'], ['low', '저대역 240p']].map(([v, l]) => h('option', {value: v, selected: v === S.quality ? true : null}, l)))
  const cam = $('selCam').cloneNode(true), mic = $('selMic').cloneNode(true), spk = $('selSpk').cloneNode(true)
  cam.value = S.devices.cam || cam.value; mic.value = S.devices.mic || mic.value; spk.value = S.devices.spk || spk.value
  const m = h('div', {class: 'modal', onclick: e => {if (e.target === m) m.remove()}}, h('div', {class: 'card'}, h('b', null, '장치·화질 설정'),
    h('label', {class: 'fld'}, '카메라', cam), h('label', {class: 'fld'}, '마이크', mic), spk.options.length ? h('label', {class: 'fld'}, '스피커', spk) : null, h('label', {class: 'fld'}, '송출 화질', qSel),
    h('div', {style: 'display:flex;gap:8px'}, h('button', {class: 'btn pri', type: 'button', onclick: async () => {
      S.quality = qSel.value; LS.set('q', S.quality); tuneSenders()
      if (spk.value !== S.devices.spk) {S.devices.spk = spk.value; renderGrid()}
      if (cam.value && cam.value !== S.devices.cam) {S.devices.cam = cam.value; try {const s = await navigator.mediaDevices.getUserMedia({video: vConstraints(cam.value)}); await replaceVideo(s.getVideoTracks()[0], true)} catch (e) {toast('카메라 변경 실패')}}
      if (mic.value && mic.value !== S.devices.mic) {S.devices.mic = mic.value; try {const s = await navigator.mediaDevices.getUserMedia({audio: aConstraints(mic.value)}); const nt = s.getAudioTracks()[0], old = S.local.getAudioTracks()[0]; nt.enabled = S.me.mic; if (old) {await S.room.replaceTrack(old, nt); S.local.removeTrack(old); old.stop()} else S.room.addTrack(nt, S.local, {metadata: {kind: 'cam'}}); S.local.addTrack(nt); watchSpeaking(selfId, S.local)} catch (e) {toast('마이크 변경 실패')}}
      LS.set('dev', S.devices); m.remove(); toast('설정을 적용했습니다.')}}, '적용'), h('button', {class: 'btn', type: 'button', onclick: () => m.remove()}, '취소'))))
  $('host').replaceChildren(m)
}
async function wakeLock() {try {S.wake = await navigator.wakeLock?.request('screen'); document.addEventListener('visibilitychange', async () => {if (document.visibilityState === 'visible' && S.room) try {S.wake = await navigator.wakeLock?.request('screen')} catch (e) {}})} catch (e) {}}
document.addEventListener('keydown', e => {if (!S.room || e.target.matches('input,textarea')) return; if (e.key === 'm' || e.key === 'ㅡ') setMic(!S.me.mic); if (e.key === 'v' || e.key === 'ㅍ') setCam(!S.me.cam)})

/* ---------- 시작 ---------- */
;(async () => {
  const hp = readHash()
  S.devices = LS.get('dev', {cam: '', mic: '', spk: ''}); S.quality = LS.get('q', 'auto'); $('optQ').value = S.quality
  $('inName').value = LS.get('name', '')
  if (hp.r) {$('inRoom').value = hp.r; $('inKey').value = hp.k; $('inTitle').value = hp.t; if (hp.s) $('optStrat').value = hp.s; if (hp.turn) $('optTurn').value = hp.turn; S.hashHH = hp.hh; S.hashHK = hp.h
    showInvite(curCfg(), !!hp.h); $('btnJoin').textContent = (hp.h ? '진행자로 ' : '') + '회의 참여'}
  $('optBlur').onchange = e => {S.blurWanted = e.target.checked}
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {})
  if (!navigator.mediaDevices?.getUserMedia) {toast('이 브라우저는 카메라·마이크를 지원하지 않습니다. 최신 Chrome·Edge·Safari를 사용하세요.', 8000); S.local = new MediaStream(); return}
  await startPreview()
})()
