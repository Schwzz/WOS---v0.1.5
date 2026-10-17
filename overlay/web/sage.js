/*
 * Sage Companion - geometric core renderer (Canvas 2D, no dependencies).
 *
 * Sections:
 *   1. CONFIG / STATES   tunable look + per-state animation targets
 *   2. MODEL             smoothed parameters, phases, audio level
 *   3. DRAW              layered geometry (unit space: outer ring radius ~1)
 *   4. BRIDGE            window.Sage - the only surface the backend should use
 *   5. UI                preview buttons, keys, parallax tilt
 *
 * Future hooks (not wired yet):
 *   Sage.setAudioLevel(0..1)  call ~30-60x/s with mic or TTS RMS
 *   Sage.setState(name)       Python: window.evaluate_js("Sage.setState('thinking')")
 *   Sage.on('state', fn)      JS -> Python: call pywebview.api.<method> from the callback
 */
(() => {
  'use strict';

  /* ---------- 1. CONFIG / STATES ---------- */
  const CFG = { fps: 60, maxDpr: 1.5, simulate: true };   // lower fps (e.g. 30) via Sage.setFps(30)

  const COL = {
    red: [255, 64, 32], amber: [255, 140, 50],
    cyan: [170, 235, 255], white: [245, 252, 255],
  };

  // Numeric fields are eased toward their targets; `dir` and text are discrete.
  const STATES = {
    idle:      { spin: 1.0, pulseHz: 0.30, pulseAmp: 0.05, scan: 0.35, core: 0.85, cyan: 0.10, ripple: 0, dir: 0,  gain: 0.0, a: 'standing by',   sync: 1.00 },
    thinking:  { spin: 3.4, pulseHz: 1.50, pulseAmp: 0.08, scan: 2.40, core: 1.00, cyan: 0.05, ripple: 0, dir: 0,  gain: 0.0, a: 'analysing',     sync: 0.62 },
    listening: { spin: 0.6, pulseHz: 0.75, pulseAmp: 0.04, scan: 0.60, core: 0.95, cyan: 0.90, ripple: 1, dir: -1, gain: 0.8, a: 'receiving',     sync: 0.88 },
    speaking:  { spin: 1.5, pulseHz: 2.00, pulseAmp: 0.05, scan: 0.90, core: 1.10, cyan: 0.35, ripple: 1, dir: 1,  gain: 1.0, a: 'transmitting',  sync: 0.97 },
  };
  const NUM_KEYS = ['spin', 'pulseHz', 'pulseAmp', 'scan', 'core', 'cyan', 'ripple', 'gain', 'sync'];

  /* ---------- 2. MODEL ---------- */
  const TAU = Math.PI * 2;
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const motion = reduced ? 0.3 : 1;

  const canvas = document.getElementById('stage');
  const ctx = canvas.getContext('2d', { alpha: false });
  let DPR = 1, SIZE = 380, R = 1;

  let state = 'idle';
  const cur = {};
  NUM_KEYS.forEach(k => { cur[k] = STATES.idle[k]; });
  let dir = 0;
  const ph = { a: 0, b: 0, c: 0, scan: 0, ripple: 0 };
  const audio = { ext: 0, extAt: -1e9, level: 0 };
  const tilt = { x: 0, y: 0, tx: 0, ty: 0 };
  const listeners = { state: [] };
  let t = 0, pulse = 0;

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, CFG.maxDpr);
    const w = canvas.getBoundingClientRect().width || 380;
    SIZE = Math.max(1, Math.round(w * DPR));
    canvas.width = SIZE; canvas.height = SIZE;
    R = SIZE * 0.46;
  }

  // Speech-like envelope used only for previewing; replaced by real levels later.
  function simSpeech(time) {
    const syll = Math.pow(Math.max(0, Math.sin(time * TAU * 3.1)), 1.4);
    const word = Math.sin(time * 1.9) > -0.35 ? 1 : 0.12;
    return Math.min(1, syll * word * (0.72 + 0.28 * Math.sin(time * 17.3)));
  }

  function update(dt, now) {
    const tgt = STATES[state];
    const k = 1 - Math.exp(-dt * 3.5);
    NUM_KEYS.forEach(n => { cur[n] += (tgt[n] - cur[n]) * k; });
    dir = tgt.dir;

    const s = dt * cur.spin * motion;
    ph.a += s * 0.12; ph.b += s * 0.21; ph.c += s * 0.34;
    ph.scan += dt * cur.scan * 1.3 * motion;
    ph.ripple += dt * 0.5 * dir * motion;
    pulse = Math.sin(t * TAU * cur.pulseHz);

    let raw;
    if (now - audio.extAt < 250) raw = audio.ext;                       // real input wins
    else if (CFG.simulate && state === 'speaking') raw = simSpeech(t);
    else if (CFG.simulate && state === 'listening') raw = 0.15 + 0.3 * simSpeech(t * 0.7 + 3);
    else raw = 0;
    audio.level += (raw - audio.level) * (1 - Math.exp(-dt * 14));

    const tk = 1 - Math.exp(-dt * 5);
    tilt.x += (tilt.tx - tilt.x) * tk; tilt.y += (tilt.ty - tilt.y) * tk;
  }

  /* ---------- 3. DRAW ---------- */
  const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
  const mix = (a, b, f) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
  const px = n => (n * DPR) / R;   // CSS-pixel width -> unit-space width

  function poly(n, r, rot) {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const a = rot + (i * TAU) / n;
      const x = Math.cos(a) * r, y = Math.sin(a) * r;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
  }
  function circle(x, y, r) { ctx.moveTo(x + r, y); ctx.arc(x, y, r, 0, TAU); }

  // Two-pass stroke: wide faint pass fakes glow without costly shadowBlur.
  function ink(col, alpha, w) {
    ctx.strokeStyle = rgba(col, alpha * 0.16); ctx.lineWidth = px(w * 4); ctx.stroke();
    ctx.strokeStyle = rgba(col, alpha);        ctx.lineWidth = px(w);     ctx.stroke();
  }

  function layer(depth, fn) {
    ctx.save();
    ctx.translate(tilt.x * depth * 0.05, tilt.y * depth * 0.05);
    fn();
    ctx.restore();
  }

  function draw() {
    const lv = audio.level;
    const warm = mix(COL.red, COL.amber, 0.35 + 0.15 * pulse);
    const tint = mix(warm, COL.cyan, cur.cyan * 0.8);
    const ice = mix(COL.cyan, COL.white, 0.4);

    // Backdrop
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, SIZE, SIZE);
    const bg = ctx.createRadialGradient(SIZE / 2, SIZE / 2, 0, SIZE / 2, SIZE / 2, SIZE * 0.55);
    bg.addColorStop(0, rgba(COL.red, 0.10 + 0.05 * cur.core + 0.08 * lv));
    bg.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = bg; ctx.fillRect(0, 0, SIZE, SIZE);

    ctx.setTransform(R, 0, 0, R, SIZE / 2, SIZE / 2);
    ctx.globalCompositeOperation = 'lighter';
    ctx.lineJoin = 'miter'; ctx.lineCap = 'butt';

    // Depth 0: outer ring, tick scale, dashed counter-ring
    layer(0.2, () => {
      ctx.beginPath(); circle(0, 0, 0.98); ink(tint, 0.6, 1.2);
      ctx.beginPath(); circle(0, 0, 0.90); ink(ice, 0.25, 0.8);
      ctx.beginPath();
      for (let i = 0; i < 96; i++) {
        const a = ph.a + (i * TAU) / 96;
        const len = i % 12 === 0 ? 0.075 : i % 4 === 0 ? 0.04 : 0.02;
        ctx.moveTo(Math.cos(a) * 0.90, Math.sin(a) * 0.90);
        ctx.lineTo(Math.cos(a) * (0.90 - len), Math.sin(a) * (0.90 - len));
      }
      ink(warm, 0.55, 1);
      ctx.save();
      ctx.setLineDash([0.018, 0.03]); ctx.lineDashOffset = -ph.b * 0.5;
      ctx.beginPath(); circle(0, 0, 0.83); ink(ice, 0.35, 0.9);
      ctx.restore();
    });

    // Depth 1: hexagon + interlocked triangles (hexagram) + inner hexagon
    layer(0.5, () => {
      poly(6, 0.78, -ph.b); ink(tint, 0.85, 1.4);
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = -ph.b + (i * TAU) / 6;
        circle(Math.cos(a) * 0.78, Math.sin(a) * 0.78, 0.014);
      }
      ctx.fillStyle = rgba(ice, 0.9); ctx.fill();
      poly(3, 0.70, ph.c); ink(warm, 0.75, 1.2);
      poly(3, 0.70, ph.c + Math.PI / 3); ink(warm, 0.75, 1.2);
      poly(6, 0.36, -ph.c * 1.6); ink(tint, 0.7, 1.1);
    });

    // Depth 2: trefoil of circles, bounding circle, octagram of squares
    layer(0.9, () => {
      const rot = -ph.b * 1.3;
      ctx.beginPath();
      for (let i = 0; i < 3; i++) {
        const a = rot + (i * TAU) / 3;
        circle(Math.cos(a) * 0.29, Math.sin(a) * 0.29, 0.29);
      }
      ink(ice, 0.55, 1);
      ctx.beginPath(); circle(0, 0, 0.58); ink(warm, 0.5, 1);
      poly(4, 0.50, ph.c * 0.7 + Math.PI / 4); ink(ice, 0.5, 1);
      poly(4, 0.50, ph.c * 0.7);               ink(ice, 0.5, 1);
    });

    // Radial lines
    layer(1.1, () => {
      ctx.beginPath();
      for (let i = 0; i < 24; i++) {
        const a = ph.a * 2 + (i * TAU) / 24, r1 = i % 2 ? 0.34 : 0.50;
        ctx.moveTo(Math.cos(a) * 0.17, Math.sin(a) * 0.17);
        ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1);
      }
      ink(warm, 0.45, 0.9);
      ctx.beginPath();
      for (let i = 0; i < 12; i++) {
        const a = -ph.b + (i * TAU) / 12;
        ctx.moveTo(Math.cos(a) * 0.62, Math.sin(a) * 0.62);
        ctx.lineTo(Math.cos(a) * 0.76, Math.sin(a) * 0.76);
      }
      ink(ice, 0.4, 0.9);
    });

    // Scan sweep (conic gradient wedge + leading edge)
    layer(0.7, () => {
      const a = ph.scan % TAU;
      if (ctx.createConicGradient) {
        const g = ctx.createConicGradient(a, 0, 0);
        g.addColorStop(0, rgba(ice, 0));
        g.addColorStop(0.78, rgba(ice, 0));
        g.addColorStop(1, rgba(ice, 0.22));
        ctx.fillStyle = g;
        ctx.beginPath(); circle(0, 0, 0.74); ctx.fill();
      }
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * 0.12, Math.sin(a) * 0.12);
      ctx.lineTo(Math.cos(a) * 0.74, Math.sin(a) * 0.74);
      ink(ice, 0.7, 1);
    });

    // Ripples: inward while listening, outward while speaking
    if (cur.ripple > 0.02) {
      for (let i = 0; i < 3; i++) {
        const f = (((ph.ripple + i / 3) % 1) + 1) % 1;
        const r = dir < 0 ? 0.92 - 0.68 * f : 0.24 + 0.68 * f;
        const alpha = Math.sin(f * Math.PI) * cur.ripple * (0.25 + lv * 0.6);
        ctx.beginPath(); circle(0, 0, r);
        ink(dir < 0 ? ice : warm, alpha, 1.1);
      }
    }

    // Core
    layer(1.4, () => {
      const base = 0.075 * cur.core;
      const cr = base * (1 + cur.pulseAmp * 3 * pulse + cur.gain * lv * 0.9);
      ctx.beginPath(); circle(0, 0, 0.20 + 0.06 * lv); ink(COL.white, 0.25 + 0.5 * lv, 1);
      poly(4, cr * 2.2, Math.PI / 4 + ph.c * 2); ink(ice, 0.8, 1.2);
      const g = ctx.createRadialGradient(0, 0, 0, 0, 0, cr * 4.2);
      g.addColorStop(0, rgba(COL.white, 1));
      g.addColorStop(0.18, rgba([255, 225, 190], 0.95));
      g.addColorStop(0.45, rgba(COL.amber, 0.55));
      g.addColorStop(0.75, rgba(COL.red, 0.18));
      g.addColorStop(1, rgba(COL.red, 0));
      ctx.fillStyle = g;
      ctx.beginPath(); circle(0, 0, cr * 4.2); ctx.fill();
    });
  }

  /* ---------- 4. BRIDGE ---------- */
  const clamp01 = v => Math.max(0, Math.min(1, +v || 0));
  const lineA = document.getElementById('line-a');
  const lineB = document.getElementById('line-b');
  const hudState = document.getElementById('hud-state');

  const Sage = {
    states: Object.keys(STATES),
    getState: () => state,
    setState(name) {
      if (!STATES[name] || name === state) return false;
      state = name;
      hudState.textContent = name;
      lineA.textContent = STATES[name].a;
      document.querySelectorAll('.states button').forEach(b => b.classList.toggle('on', b.dataset.state === name));
      listeners.state.forEach(fn => fn(name));
      return true;
    },
    setAudioLevel(v) { audio.ext = clamp01(v); audio.extAt = performance.now(); },
    setStatus(text) { lineA.textContent = String(text).slice(0, 40); },
    setFps(n) { CFG.fps = Math.max(10, Math.min(60, n | 0)); },
    // Off when real speech levels drive the core (WOS-Overlay): no made-up motion.
    setSimulation(on) { CFG.simulate = !!on; },
    on(evt, fn) { if (listeners[evt]) listeners[evt].push(fn); },
  };
  window.Sage = Sage;

  /* ---------- 5. UI ---------- */
  document.querySelectorAll('.states button').forEach(b => {
    b.addEventListener('click', () => Sage.setState(b.dataset.state));
  });
  window.addEventListener('keydown', e => {
    if (e.target && e.target.tagName === 'INPUT') return;   // typing in the chat box
    const name = Sage.states[+e.key - 1];
    if (name && !document.body.classList.contains('linked')) Sage.setState(name);
    if (e.key === 'Escape') closeWindow();
  });
  window.addEventListener('pointermove', e => {
    tilt.tx = (e.clientX / window.innerWidth - 0.5) * 2;
    tilt.ty = (e.clientY / window.innerHeight - 0.5) * 2;
  });
  document.addEventListener('pointerleave', () => { tilt.tx = 0; tilt.ty = 0; });

  function closeWindow() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.close) window.pywebview.api.close();
    else window.close();
  }
  document.getElementById('btn-close').addEventListener('click', closeWindow);
  // Canvas size is set by CSS (largest square that fits); re-measure whenever it changes.
  if (typeof ResizeObserver === 'function') new ResizeObserver(resize).observe(canvas);
  window.addEventListener('resize', resize);

  // Readout text refreshes at ~4 Hz; cheap and keeps the HUD alive.
  setInterval(() => {
    const code = ((t * 977) | 0).toString(16).toUpperCase().padStart(4, '0').slice(-4);
    lineB.textContent = `0x${code} \u00B7 sync ${cur.sync.toFixed(2)}`;
  }, 250);

  let last = performance.now();
  function frame(now) {
    requestAnimationFrame(frame);
    if (document.hidden) { last = now; return; }
    if (now - last < 1000 / CFG.fps - 2) return;
    const dt = Math.min((now - last) / 1000, 0.1);
    last = now; t += dt;
    update(dt, now);
    draw();
  }

  resize();
  requestAnimationFrame(frame);
})();
