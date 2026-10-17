/*
 * WOS-Overlay - chat, voice toggle and backend link for the Sage core.
 *
 * Everything the avatar does comes from the WOS backend (core/overlay.py):
 *   - state:  idle / thinking / speaking, polled from /api/state
 *   - levels: the loudness of the speech WOS is actually playing. They arrive
 *             once per utterance and are stepped through in time with the
 *             playback clock, so the core follows the real audio.
 * The page is served by the backend and sends the token that came in the URL
 * fragment (#token) with every API call. Text is only ever inserted with
 * textContent.
 */
(() => {
  'use strict';

  const Sage = window.Sage;
  const body = document.body;
  const $ = id => document.getElementById(id);
  const log = $('chat-log'), form = $('chat-form'), input = $('chat-input');
  const sendBtn = $('chat-send'), voiceBtn = $('btn-voice'), chatBtn = $('btn-chat');
  const chatPanel = $('chat'), caption = $('line-c');

  const POLL_MS = 150, OFFLINE_POLL_MS = 1000, GIVE_UP_MS = 20000;
  const STATUS = { idle: 'standing by', thinking: 'analysing', speaking: 'transmitting' };

  let token = decodeURIComponent((location.hash || '').replace(/^#/, ''));
  let linked = false, everLinked = false, offlineSince = null;
  let character = 'nexis', chatVersion = -1, sending = false, expanded = false;
  let lastState = 'idle', voice = { enabled: false, available: true };
  let haveAudio = null, env = null, statusDirty = true;

  /* ---------- backend calls ---------- */
  function pyApi() { return window.pywebview && window.pywebview.api; }

  async function refreshToken() {
    // After a WOS /restart the token changes; the desktop shell can re-read it.
    try {
      const api = pyApi();
      const ep = api && api.get_endpoint ? await api.get_endpoint() : null;
      if (ep && ep.token) token = ep.token;
    } catch (_) { /* keep the old token */ }
  }

  async function api(path, options) {
    const res = await fetch(path, Object.assign({}, options, {
      headers: { 'X-WOS-Token': token, 'Content-Type': 'application/json' },
    }));
    let data = null;
    try { data = await res.json(); } catch (_) { /* no body */ }
    if (!res.ok) {
      if (res.status === 401) await refreshToken();
      const err = new Error((data && data.error) || ('HTTP ' + res.status));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  /* ---------- chat log ---------- */
  function addLine(role, text, extra) {
    const row = document.createElement('div');
    row.className = 'msg ' + role + (extra ? ' ' + extra : '');
    const who = document.createElement('b');
    who.textContent = role === 'user' ? 'you' : role === 'assistant' ? character.toLowerCase() : '!';
    const span = document.createElement('span');
    span.textContent = text;
    row.append(who, span);
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  async function loadHistory() {
    try {
      const h = await api('/api/history');
      if (h.character) character = h.character;
      log.textContent = '';
      h.messages.forEach(m => addLine(m.role, m.content));
      const last = h.messages.slice().reverse().find(m => m.role === 'assistant');
      caption.textContent = last ? last.content.replace(/\s+/g, ' ') : '';
    } catch (_) { /* the poll loop reports connection problems */ }
  }

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || sending || !linked) return;
    sending = true; sendBtn.disabled = true; input.value = '';
    addLine('user', text, 'pending');
    let failure = null;
    try {
      await api('/api/message', { method: 'POST', body: JSON.stringify({ text }) });
    } catch (err) {
      failure = err.message;
      input.value = text;           // nothing was sent; let the user retry
    }
    sending = false; sendBtn.disabled = false;
    await loadHistory();
    if (failure) addLine('error', failure);
    input.focus();
  });
  input.addEventListener('keydown', e => { if (e.key === 'Escape') input.blur(); });

  /* ---------- voice output ---------- */
  function renderVoice() {
    const on = voice.enabled;
    voiceBtn.textContent = 'voice: ' + (on ? (voice.available ? 'on' : 'on (no key)') : 'off');
    voiceBtn.classList.toggle('on', on && voice.available);
    voiceBtn.classList.toggle('warn', on && !voice.available);
    voiceBtn.setAttribute('aria-pressed', String(on));
    voiceBtn.title = on && !voice.available ? 'FISH_AUDIO_API_KEY is not set' : 'Speak replies aloud';
  }

  voiceBtn.addEventListener('click', async () => {
    if (!linked) return;
    try {
      const s = await api('/api/voice', { method: 'POST', body: JSON.stringify({ enabled: !voice.enabled }) });
      voice = s.voice;
      renderVoice();
    } catch (err) {
      addLine('error', err.message);
    }
  });

  /* ---------- expand / collapse ---------- */
  function setExpanded(value) {
    expanded = value;
    body.classList.toggle('expanded', value);
    chatPanel.hidden = !value;
    chatBtn.textContent = value ? 'avatar' : 'chat';
    chatBtn.setAttribute('aria-expanded', String(value));
    const shell = pyApi();
    if (shell && shell.set_expanded) Promise.resolve(shell.set_expanded(value)).catch(() => {});
    if (value) { log.scrollTop = log.scrollHeight; setTimeout(() => input.focus(), 60); }
  }
  chatBtn.addEventListener('click', () => setExpanded(!expanded));

  /* ---------- state + audio from the backend ---------- */
  function onState(s, rtt) {
    if (!linked) {
      linked = true; everLinked = true;
      body.classList.add('linked');
      Sage.setSimulation(false);        // only real audio moves the core
    }
    body.classList.remove('offline');
    offlineSince = null;

    if (s.character) {
      character = s.character;
      input.placeholder = 'message ' + character.toLowerCase();
    }
    voice = s.voice || voice;
    renderVoice();

    if (lastState === 'speaking' && s.state !== 'speaking') Sage.setAudioLevel(0);
    Sage.setState(s.state);
    if (s.state !== lastState || statusDirty) { Sage.setStatus(STATUS[s.state] || s.state); statusDirty = false; }
    lastState = s.state;

    if (s.audio) {
      if (s.audio.levels) {
        env = { id: s.audio.id, fps: s.audio.fps || 50, levels: s.audio.levels, t0: 0 };
        haveAudio = s.audio.id;
      }
      // Start of playback on this page's clock (half the round trip is transit).
      if (env && env.id === s.audio.id) env.t0 = performance.now() - s.audio.elapsed * 1000 - rtt / 2;
    } else {
      env = null; haveAudio = null;
    }

    if (s.chat_version !== chatVersion) {
      const first = chatVersion === -1;
      chatVersion = s.chat_version;
      if (first || !sending) loadHistory();
    }
  }

  function onOffline() {
    const now = performance.now();
    if (offlineSince === null) offlineSince = now;
    body.classList.add('offline');
    env = null; haveAudio = null;
    Sage.setAudioLevel(0);
    Sage.setState('idle');
    Sage.setStatus(everLinked ? 'backend offline' : 'waiting for WOS');
    lastState = 'idle'; statusDirty = true;
    if (everLinked && now - offlineSince > GIVE_UP_MS) {
      const shell = pyApi();                // the terminal was closed: close too
      if (shell && shell.close) shell.close();
    }
  }

  async function poll() {
    const started = performance.now();
    try {
      const s = await api('/api/state' + (haveAudio !== null ? '?have=' + haveAudio : ''));
      onState(s, performance.now() - started);
    } catch (_) {
      onOffline();
    }
    setTimeout(poll, offlineSince === null ? POLL_MS : OFFLINE_POLL_MS);
  }

  // Feed the real loudness of the speech being played to the core, in step
  // with the playback clock. Outside speech nothing is fed, so it idles.
  function drive(now) {
    requestAnimationFrame(drive);
    if (env && lastState === 'speaking') {
      const i = Math.floor(((now - env.t0) / 1000) * env.fps);
      Sage.setAudioLevel(i >= 0 && i < env.levels.length ? env.levels[i] : 0);
    }
  }

  renderVoice();
  Sage.setStatus('waiting for WOS');
  requestAnimationFrame(drive);
  poll();
})();
