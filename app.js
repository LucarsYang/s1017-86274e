// Sandy 生日網站 — 播放引擎（劇本與檔名在 content.js）。
// 沿用草稿 v3 的 render 邏輯，改成全螢幕單頁、一次一章。
(() => {
'use strict';
const CT = window.CONTENT;
const C = CT.chars, HEIGHT = CT.height, scenes = CT.scenes, UI = CT.ui;
const P = 'assets/portraits/', S = 'assets/stickers/', BG = 'assets/bg/', M = 'media/';
const COLORS = ['#ff6b8b','#ffd166','#4fc3f7','#81c784','#ba68c8','#ff8a65'];
const $ = id => document.getElementById(id);
const app = $('app'), stage = $('stage'), bgLayer = $('bgLayer'), chipEl = $('chip'), locEl = $('loc'),
      skipBtn = $('skip'), fadeEl = $('fade'), startEl = $('start'), saveEl = $('save'), saveLink = $('saveLink'),
      saveHint = $('saveHint'), lightbox = $('lightbox');

let MEDIA = new Set();
let ci = 0, li = 0, solved = false, pending = null, busy = false, started = false;
let lineTimers = [], lineCleanups = [];

// ── 小工具 ──
const img = (src, cls, style = '') => `<img class="${cls}" src="${src}" style="${style}" alt="" draggable="false">`;
const later = (fn, ms) => { const t = setTimeout(fn, ms); lineTimers.push(t); return t; };
const hasMedia = name => MEDIA.has(name);
function letterFiles() {
  const pre = CT.media.huaLetterPrefix;
  return [...MEDIA].filter(f => f.startsWith(pre) && /\.(jpe?g|png|webp|gif)$/i.test(f))
    .sort((a, b) => (parseInt(a.slice(pre.length), 10) || 0) - (parseInt(b.slice(pre.length), 10) || 0));
}
function stop(ev) { ev.stopPropagation(); }

// ── 預載 ──
const preloaded = [];
function preload(urls) { urls.forEach(u => { const im = new Image(); im.src = u; preloaded.push(im); }); }
function chapterUrls(i) {
  const s = scenes[i]; if (!s) return [];
  const u = new Set([BG + s.bg + '.webp']);
  if (s.anim === 'scooter') u.add(P + 'scooter-trio.webp');
  s.lines.forEach(l => {
    if (l.w in C && !s.noPortrait) u.add(`${P}${C[l.w].key}-${l.e || 'happy'}.webp`);
    if (l.s) u.add(`${S}${l.s}.webp`);
    if (l.quiz) { u.add(`${P}${C[l.quiz].key}-thinking.webp`); l.opts.forEach(o => u.add(`${P}${C[l.quiz].key}-${o[2]}.webp`)); }
    if (l.wrong) u.add(`${P}${C[l.wrong.w].key}-${l.wrong.e}.webp`);
    if (l.w === 'party') {
      ['lucas/33','cheng/36','hua/21','sandy/37'].forEach(k => u.add(`${S}${k}.webp`));
      CT.slides.forEach(sl => { if (sl.bg) u.add(BG + sl.bg + '.webp'); if (sl.who) u.add(P + sl.who + '.webp'); });
      ['cheng-laugh','lucas-laugh','hua-happy','sandy-laugh'].forEach(k => u.add(P + k + '.webp'));
    }
  });
  return [...u];
}

// ── 音訊（開始畫面那一下解鎖 iOS）──
let AC = null;
function audioSession(type) { try { if (navigator.audioSession) navigator.audioSession.type = type; } catch (e) {} }
function unlockAudio() {
  try {
    audioSession('playback');   // iOS 17+：靜音開關打開時也能出聲
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    if (AC.state === 'suspended') AC.resume();
    const b = AC.createBuffer(1, 1, 22050), src = AC.createBufferSource();
    src.buffer = b; src.connect(AC.destination); src.start(0);
  } catch (e) { AC = null; }
}
// 生日快樂歌音樂盒（同草稿）
let songPlaying = false;
function playSong() {
  if (songPlaying) return;
  try {
    audioSession('playback');
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    if (AC.state === 'suspended') AC.resume();
  } catch (e) { return; }
  songPlaying = true;
  const ac = AC;
  const N = { G4:392, A4:440, B4:493.9, C5:523.3, D5:587.3, E5:659.3, F5:698.5, G5:784 };
  const tune = [['G4',.75],['G4',.25],['A4',1],['G4',1],['C5',1],['B4',2],['G4',.75],['G4',.25],['A4',1],['G4',1],['D5',1],['C5',2],
                ['G4',.75],['G4',.25],['G5',1],['E5',1],['C5',1],['B4',1],['A4',2],['F5',.75],['F5',.25],['E5',1],['C5',1],['D5',1],['C5',2.5]];
  let t = ac.currentTime + .1; const beat = .42;
  tune.forEach(([n, d]) => {
    [1, 2].forEach((mul, j) => {   // 基音＋八度泛音，像音樂盒
      const o = ac.createOscillator(), g = ac.createGain();
      o.type = 'sine'; o.frequency.value = N[n] * mul;
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(j ? .05 : .18, t + .01); g.gain.exponentialRampToValueAtTime(.0005, t + d * beat + .6);
      o.connect(g).connect(ac.destination); o.start(t); o.stop(t + d * beat + .7);
    });
    t += d * beat;
  });
  setTimeout(() => { songPlaying = false; }, (t - ac.currentTime + 1) * 1000);
}

// ── 背景、標籤 ──
function setBackground(s) {
  if (s.anim === 'scooter') {
    bgLayer.innerHTML = `<div class="street" style="background-image:url(${BG}${s.bg}.webp)"></div><div class="street-floor"></div>
      <div class="wind">💨</div>${img(P + 'scooter-trio.webp', 'scooter')}`;
    fitStreet();
  } else {
    bgLayer.innerHTML = `<div class="bg ${s.dim ? 'dim' : ''}" style="background-image:url(${BG}${s.bg}.webp)"></div>`;
  }
}
function fitStreet() {   // 街景圖 3:2，捲動距離＝一張圖寬，才會無縫
  const st = bgLayer.querySelector('.street');
  if (st) st.style.setProperty('--tile', (st.clientHeight * 1.5).toFixed(1) + 'px');
}
window.addEventListener('resize', fitStreet);
function slideIn(el) { el.classList.remove('in'); void el.offsetWidth; el.classList.add('in'); }
function updateChip(animate) {
  const s = scenes[ci];
  let txt = s.chip || '';
  for (let k = 0; k <= li && k < s.lines.length; k++) if (s.lines[k].chip) txt = s.lines[k].chip;
  const changed = chipEl.textContent !== txt;
  chipEl.textContent = txt; chipEl.style.display = txt ? '' : 'none';
  if (txt && (changed || animate)) slideIn(chipEl);
}

// ── 派對裝飾（同草稿）──
function fxHTML() {
  let h = '<div class="glow"></div>';
  for (let i = 0; i < 46; i++) h += `<span class="cf" style="left:${Math.random() * 100}%;background:${COLORS[i % 6]};animation-duration:${2.6 + Math.random() * 2}s;animation-delay:${Math.random() * 2.5}s"></span>`;
  for (let i = 0; i < 6; i++) h += `<span class="bl" style="left:${8 + i * 15}%;--dx:${(i % 2 ? 1 : -1) * 20}px;--rot:${(i % 2 ? 8 : -8)}deg;animation-duration:${6 + i % 3}s;animation-delay:${.3 + i * .7}s;filter:hue-rotate(${i * 55}deg)">🎈</span>`;
  return h;
}
const U = n => `calc(${n} * var(--u))`;
function slideHTML(sl, i) {
  const ph = (k, e, st) => `<img src="${P}${k}-${e}.webp" style="${st}" alt="">`;
  let inner;
  if (sl.family)  // 後排丞丞（最高）、老公；前排小花、Sandy（戴皇冠）
    inner = ph('cheng', 'laugh', `left:${U(8)};top:${U(6)};height:${U(92)}`) + ph('lucas', 'laugh', `right:${U(10)};top:${U(10)};height:${U(87)}`) +
            ph('hua', 'happy', `left:${U(18)};top:${U(62)};height:${U(83)}`) + ph('sandy', 'laugh', `right:${U(16)};top:${U(62)};height:${U(83)}`) +
            `<span class="crown" style="right:${U(42)};top:${U(46)}">👑</span>`;
  else if (sl.scooter) inner = `<img src="${P}scooter-trio.webp" style="left:${U(18)};bottom:${U(2)};height:${U(120)}" alt="">`;
  else inner = `<img src="${P}${sl.who}.webp" style="left:50%;bottom:${U(-6)};height:${U(118)};transform:translateX(-50%)" alt="">`;
  const bg = sl.bg ? `background-image:url(${BG}${sl.bg}.webp)` : '';
  return `<div class="slide ${i === 0 ? 'on' : ''}"><div class="photo" style="${bg}">${inner}</div><div class="cap">${sl.cap}</div></div>`;
}
function partyDecor() {
  const flags = 'SANDY'.split('').map((c, i) => `<span style="background:${COLORS[i]};animation-delay:${.35 + i * .1}s">${c}</span>`).join('');
  const stk = (f, st, d) => `<img class="stk" src="${S}${f}.webp" style="${st};animation-delay:${d}s" alt="">`;
  const top = n => `calc(var(--sat) + ${n - 40} * var(--u))`;
  return `<div class="hb">Happy Birthday</div><div class="flags">${flags}</div>
    <div class="polaroid">${CT.slides.map(slideHTML).join('')}</div>
    ${stk('lucas/33', `left:${U(4)};top:${top(176)};--r:-10deg`, 1.5)}${stk('cheng/36', `right:${U(4)};top:${top(176)};--r:10deg`, 1.8)}
    ${stk('hua/21', `left:${U(2)};top:${top(352)};--r:-6deg`, 2.1)}${stk('sandy/37', `right:${U(2)};top:${top(352)};--r:8deg`, 2.4)}`;
}
let carousel = null;
function setParty(on) {
  app.classList.toggle('party', on);
  let fx = app.querySelector('.fx');
  if (on && !fx) {
    fx = document.createElement('div'); fx.className = 'fx'; fx.innerHTML = fxHTML(); app.insertBefore(fx, stage);
    const deco = document.createElement('div'); deco.className = 'deco'; deco.innerHTML = partyDecor(); app.insertBefore(deco, stage);
    const pol = deco.querySelector('.polaroid');
    setTimeout(() => { pol.classList.add('swing'); deco.querySelectorAll('.stk').forEach(x => x.classList.add('bob')); }, 2900);
    let k = 0; const slides = deco.querySelectorAll('.slide');
    carousel = setInterval(() => { slides[k].classList.remove('on'); k = (k + 1) % slides.length; slides[k].classList.add('on'); }, 2600);
    setTimeout(showSave, 3000);
  }
  if (!on && fx) { fx.remove(); app.querySelector('.deco').remove(); clearInterval(carousel); saveEl.hidden = true; }
}

// ── 對話 ──
function charLine(c, e, t, extraCls = '', more = true) {
  const s = scenes[ci];
  const por = s.noPortrait && !extraCls ? '' : img(`${P}${c.key}-${e || 'happy'}.webp`, `portrait ${c.side} ${extraCls}`, `--h:${HEIGHT[c.key]}`);
  return por + `<div class="dlg ${c.side}"><span class="name" style="background:${c.color}">${c.name}</span>${t}${more ? '<span class="more">▼ 點一下</span>' : ''}</div>`;
}

// ── 猜謎（同草稿：答對才往下）──
function renderQuiz(l, picked) {
  const c = C[l.quiz];
  const opts = l.opts.map((o, i) => {
    const cls = picked && picked.has(i) ? (o[1] ? 'yes' : 'no') : '';
    return `<span class="opt ${cls}" data-o="${i}">${String.fromCharCode(65 + i)}. ${o[0]}</span>`;
  }).join('');
  let reply = '', e = 'thinking';
  if (picked && picked.last !== undefined) { const o = l.opts[picked.last]; reply = o[3]; e = o[2]; }
  stage.innerHTML = `<div class="act quiz"><div class="q">${l.q}</div><div class="opts">${opts}</div></div>` +
    (reply ? charLine(c, e, reply, picked.lastCorrect ? 'portrait-ok' : 'shake', picked.lastCorrect)
           : img(`${P}${c.key}-thinking.webp`, `portrait ${c.side}`, `--h:${HEIGHT[c.key]}`));
  stage.querySelectorAll('.opt').forEach(op => op.addEventListener('click', ev => {
    stop(ev);
    if (solved) return;
    const i = +op.dataset.o;
    picked = picked || new Set(); picked.add(i); picked.last = i; picked.lastCorrect = l.opts[i][1];
    if (l.opts[i][1]) solved = true;
    renderQuiz(l, picked);
  }));
}

// ── 互動卡 ──
const ACTS = {
  password(l) {
    let entry = '';
    stage.innerHTML = `<div class="act pw"><div class="big lock">🔒</div><div class="t">${l.title}</div>
      <div class="keys">${'<span></span>'.repeat(l.code.length)}</div>${l.hint}
      <div class="pad">${[1,2,3,4,5,6,7,8,9].map(n => `<button type="button" data-k="${n}">${n}</button>`).join('')}
      <button type="button" class="fn" data-k="clr">清除</button><button type="button" data-k="0">0</button><button type="button" class="fn" data-k="del">⌫</button></div></div>
      <div class="hint-slot"></div>`;
    const keys = stage.querySelector('.keys'), slots = keys.querySelectorAll('span'), hintSlot = stage.querySelector('.hint-slot');
    const draw = () => slots.forEach((sp, i) => { sp.textContent = entry[i] || ''; sp.classList.toggle('on', i === entry.length); });
    draw();
    stage.querySelectorAll('.pad button').forEach(b => b.addEventListener('click', ev => {
      stop(ev);
      if (solved || entry.length >= l.code.length && b.dataset.k !== 'clr') return;
      const k = b.dataset.k;
      if (k === 'clr') entry = ''; else if (k === 'del') entry = entry.slice(0, -1); else entry += k;
      keys.classList.remove('bad'); draw();
      if (entry.length === l.code.length) later(() => {
        if (entry === l.code) {
          solved = true; keys.classList.add('good'); stage.querySelector('.lock').textContent = '🔓';
          hintSlot.innerHTML = '';
          later(() => next(), 900);
        } else {
          keys.classList.add('bad');
          const w = l.wrong;   // 錯了：小花提示（卡片蓋住立繪，所以只出對話框）
          hintSlot.innerHTML = `<div class="dlg ${C[w.w].side}"><span class="name" style="background:${C[w.w].color}">${C[w.w].name}</span>${w.t}</div>`;
          later(() => { entry = ''; keys.classList.remove('bad'); draw(); }, 700);
        }
      }, 220);
    }));
    return { gate: true };
  },
  bulbOff(l) {
    stage.innerHTML = `<div class="act"><div class="big bulb off">💡</div><div class="t">${l.title}</div>${l.before}<span class="after"></span></div>`;
    const bulb = stage.querySelector('.bulb');
    const play = () => {
      if (!pending) return; pending = null;
      bulb.classList.remove('off'); bulb.classList.add('flicker');
      later(() => { bulb.classList.add('off'); bulb.classList.remove('flicker'); stage.querySelector('.after').textContent = l.after; }, 1100);
    };
    bulb.addEventListener('click', ev => { stop(ev); play(); });
    pending = play;   // 第一下點哪裡都會先點燈泡
    return {};
  },
  bulbOn(l) {
    stage.innerHTML = `<div class="act"><div class="big bulb lit">💡</div><div class="t">${l.title}</div>${l.text}</div>`;
    return {};
  },
  vote(l) {
    stage.innerHTML = `<div class="act"><div class="t">${l.title}</div><div class="vote">${l.lines.join('<br>')}<br>贊成 <b class="yes">0</b> 票　反對 ${l.no} 票<br>${l.note}</div><div class="gavel">${l.gavel}</div></div>`;
    const yes = stage.querySelector('.yes');
    for (let n = 1; n <= l.yes; n++) later(() => { yes.textContent = n; }, 250 + n * 220);
    return {};
  },
  target(l) {
    stage.innerHTML = `<div class="act"><div class="target">🎯</div><div class="t">${l.title}</div>${l.text}</div>`;
    return {};
  },
  search(l) {
    stage.innerHTML = `<div class="act"><div class="search">🔍 <span class="q"></span><span class="caret"></span></div><div class="res-slot"></div></div>`;
    const q = stage.querySelector('.q'), chars = [...l.query];
    chars.forEach((ch, i) => later(() => { q.textContent += ch; }, 300 + i * 160));
    later(() => { stage.querySelector('.caret').remove(); stage.querySelector('.res-slot').innerHTML = `<div class="result">${l.result}</div>`; }, 300 + chars.length * 160 + 350);
    return {};
  },
  progress(l) {
    stage.innerHTML = `<div class="act"><div class="t">${l.title}</div><div class="bar"><i></i></div><span class="pct">${l.from}%</span></div>`;
    const bar = stage.querySelector('.bar i'), pct = stage.querySelector('.pct');
    bar.style.width = l.from + '%';
    const dur = l.to - l.from > 50 ? 2200 : 700, t0 = performance.now();
    const tick = now => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3), v = Math.round(l.from + (l.to - l.from) * e);
      bar.style.width = (l.from + (l.to - l.from) * e) + '%';
      pct.innerHTML = k < 1 ? v + '%' : (l.to === 100 ? `<b>100%</b>${l.done || ''}` : l.to + '%');
      if (k < 1 && stage.contains(pct)) requestAnimationFrame(tick);
    };
    later(() => requestAnimationFrame(tick), 450);
    return {};
  },
  giftVideo(l) {
    const f = CT.media.chengAnimation;
    const body = hasMedia(f)
      ? `<video src="${M}${f}" playsinline controls preload="metadata"></video>`
      : `<div class="gift-box ph">${UI.giftPlaceholder}</div>`;
    stage.innerHTML = `<div class="act gift"><div class="t">${l.title}</div>${body}</div>`;
    const v = stage.querySelector('video');
    if (v) { v.addEventListener('click', stop); lineCleanups.push(() => { try { v.pause(); } catch (e) {} }); }
    return {};
  },
  giftLetter(l) {
    const files = letterFiles();
    if (!files.length) {
      stage.innerHTML = `<div class="act gift"><div class="big">💌</div><div class="t">${l.title}</div><div class="gift-box ph">${UI.giftPlaceholder}</div></div>`;
      return {};
    }
    stage.innerHTML = `<div class="act gift"><div class="env">💌</div><div class="t">${l.title}</div><div class="desc">${l.text}</div><div class="letters"></div></div>`;
    const open = () => {
      if (!pending) return; pending = null;
      stage.querySelector('.env').textContent = '💌✨'; stage.querySelector('.desc').remove();
      const box = stage.querySelector('.letters');
      box.innerHTML = files.map((f, i) => `<img src="${M}${f}" data-i="${i}" style="animation-delay:${i * .12}s" alt="">`).join('');
      box.querySelectorAll('img').forEach(im => im.addEventListener('click', ev => { stop(ev); openLightbox(files, +im.dataset.i); }));
    };
    stage.querySelector('.env').addEventListener('click', ev => { stop(ev); open(); });
    pending = open;
    return {};
  },
  candle(l) {
    stage.innerHTML = `<div class="act candle"><div class="cake"><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="48"/></svg>🎂</div>
      <div class="t main">${l.blow}</div><div class="sub">${l.blowSub}</div><div class="meter" hidden><i></i></div><div class="mic"></div></div>`;
    const cake = stage.querySelector('.cake'), ring = cake.querySelector('circle'), mainT = stage.querySelector('.main'),
          sub = stage.querySelector('.sub'), micEl = stage.querySelector('.mic'), meter = stage.querySelector('.meter'), meterI = meter.querySelector('i');
    const holdMode = () => { mainT.textContent = l.hold; sub.textContent = ''; meter.hidden = true; };
    let done = false;
    const finish = () => { if (done) return; done = true; solved = true; cleanupLine(); next(); };
    // 按住蛋糕 2 秒（永遠可用）
    let holdStart = 0, raf = 0;
    const L = 301.6;
    const reset = () => { holdStart = 0; cancelAnimationFrame(raf); ring.style.strokeDashoffset = L; cake.classList.remove('holding'); };
    const step = now => {
      if (!holdStart) return;
      const k = Math.min(1, (now - holdStart) / 2000);
      ring.style.strokeDashoffset = L * (1 - k);
      if (k >= 1) { reset(); finish(); return; }
      raf = requestAnimationFrame(step);
    };
    cake.addEventListener('pointerdown', ev => { ev.preventDefault(); stop(ev); try { cake.setPointerCapture(ev.pointerId); } catch (e) {}
      holdStart = performance.now(); cake.classList.add('holding'); raf = requestAnimationFrame(step); });
    ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(t => cake.addEventListener(t, reset));
    cake.addEventListener('click', stop);
    lineCleanups.push(reset);
    // 吹氣偵測：HTTPS＋允許麥克風才用；其他情況自動改按住
    const canMic = window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && (window.AudioContext || window.webkitAudioContext);
    if (!canMic) { holdMode(); return { gate: true, finish }; }
    micEl.textContent = '🎤 等待麥克風…';
    audioSession('play-and-record');
    let stream = null, srcNode = null, micRaf = 0, alive = true;
    lineCleanups.push(() => {
      alive = false; cancelAnimationFrame(micRaf);
      try { srcNode && srcNode.disconnect(); } catch (e) {}
      if (stream) stream.getTracks().forEach(t => t.stop());
      audioSession('playback');
    });
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation:false, noiseSuppression:false, autoGainControl:false } })
      .then(st => {
        stream = st;
        if (!alive) { st.getTracks().forEach(t => t.stop()); return; }
        AC = AC || new (window.AudioContext || window.webkitAudioContext)();
        if (AC.state === 'suspended') AC.resume();
        srcNode = AC.createMediaStreamSource(st);
        const an = AC.createAnalyser(); an.fftSize = 1024; srcNode.connect(an);
        const buf = new Float32Array(an.fftSize);
        micEl.textContent = '🎤 對著手機下方吹氣'; meter.hidden = false;
        let loud = 0;
        const loop = () => {
          if (!alive) return;
          an.getFloatTimeDomainData(buf);
          let sum = 0; for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
          const rms = Math.sqrt(sum / buf.length);
          meterI.style.width = Math.min(100, rms / .25 * 100) + '%';
          loud = rms > .2 ? loud + 1 : Math.max(0, loud - 1);
          if (loud >= 10) { finish(); return; }   // 約 0.15 秒連續大聲氣流
          micRaf = requestAnimationFrame(loop);
        };
        loop();
      })
      .catch(() => { if (alive) { micEl.textContent = ''; holdMode(); } });
    return { gate: true, finish };
  },
};

// ── 主 render ──
let curAct = null;
function cleanupLine() {
  lineTimers.forEach(clearTimeout); lineTimers = [];
  lineCleanups.forEach(f => { try { f(); } catch (e) {} }); lineCleanups = [];
}
function render() {
  cleanupLine();
  const s = scenes[ci], l = s.lines[li];
  solved = false; pending = null; curAct = null;
  updateChip(false);
  const isParty = l.w === 'party';
  setParty(isParty);
  skipBtn.hidden = isParty;
  if (l.act) { curAct = ACTS[l.act](l); return; }
  if (l.quiz) { renderQuiz(l); return; }
  if (isParty) {
    stage.innerHTML = `<div class="puff">💨</div>
      <div class="dlg" style="animation-delay:1.2s"><span class="name" style="left:${U(16)};background:#e2667f">${l.name}</span>${l.t}</div>`;
    playSong();
    return;
  }
  const side = l.w in C ? (C[l.w].side === 'left' ? 'at-right' : 'at-left') : l.w === 'nar' ? 'at-center' : 'at-right';
  const react = l.s ? img(`${S}${l.s}.webp`, `react ${side}`) : '';
  if (l.w === 'nar') { stage.innerHTML = react + `<div class="dlg nar"><div>${l.t}</div></div>`; return; }
  stage.innerHTML = react + charLine(C[l.w], l.e, l.t);
}
function isGated() {
  const l = scenes[ci].lines[li];
  return (l.quiz || (curAct && curAct.gate)) && !solved;
}
function next() {
  const s = scenes[ci];
  if (li + 1 < s.lines.length) { li++; render(); }
  else if (ci + 1 < scenes.length) goChapter(ci + 1);
}
function goChapter(i) {
  busy = true; cleanupLine();
  fadeEl.classList.add('on');
  setTimeout(() => {
    ci = i; li = 0;
    stage.innerHTML = '';
    setBackground(scenes[ci]);
    locEl.textContent = scenes[ci].loc;
    render();
    updateChip(true); slideIn(locEl);
    preload(chapterUrls(ci + 1));
    fadeEl.classList.remove('on');
    setTimeout(() => { busy = false; }, 300);
  }, 480);
}
function onTap() {
  if (busy || !started) return;
  const l = scenes[ci].lines[li];
  if (l.w === 'party') { playSong(); return; }      // 結尾：點一下再唱一次
  if (pending) { pending(); return; }                 // 互動卡第一下＝觸發效果
  if (isGated()) return;                              // 密碼／猜謎／吹蠟燭要過關才往下
  next();
}
function skip(ev) {
  stop(ev);
  if (busy || !started) return;
  const s = scenes[ci], l = s.lines[li];
  if (l.act === 'candle' && curAct && curAct.finish) { curAct.finish(); return; }
  for (let j = li + 1; j < s.lines.length; j++) {
    const x = s.lines[j];
    if (x.act || x.quiz || x.w === 'party') { li = j; render(); return; }
  }
  if (ci + 1 < scenes.length) goChapter(ci + 1);
}

// ── 小花的信放大 ──
function openLightbox(files, i) {
  const im = lightbox.querySelector('img'), nav = lightbox.querySelector('.nav');
  const show = () => { im.src = M + files[i]; nav.textContent = files.length > 1 ? `${i + 1} / ${files.length}（點信紙看下一張）` : ''; };
  show(); lightbox.hidden = false;
  im.onclick = ev => { stop(ev); if (files.length > 1) { i = (i + 1) % files.length; show(); } };
}
lightbox.addEventListener('click', ev => { stop(ev); if (ev.target !== lightbox.querySelector('img')) lightbox.hidden = true; });

// ── 保存回顧影片：Web Share（檔案）→ <a download> → 開新頁長按儲存 ──
let shareFile = null, wantShare = false, fetching = false;
function canShareFiles() {
  // 只在手機／平板用分享：Mac 版 Chrome 也支援分享檔案，但會跳出關不掉的空白分享框
  if (!(navigator.maxTouchPoints > 0 || matchMedia('(pointer: coarse)').matches)) return false;
  try { return !!(navigator.canShare && navigator.share && navigator.canShare({ files: [new File([new Blob(['x'])], 'x.mp4', { type: 'video/mp4' })] })); }
  catch (e) { return false; }
}
const supportsDownload = () => 'download' in document.createElement('a');
function showSave() {
  if (!app.classList.contains('party')) return;
  const f = CT.media.recap;
  saveLink.href = M + f; saveLink.setAttribute('download', f);
  saveLink.textContent = UI.save; saveHint.textContent = UI.saveHint;
  if (!hasMedia(f)) { saveLink.classList.add('busy'); saveHint.textContent = '（回顧影片還沒放進 media/）'; }
  saveEl.hidden = false;
  if (hasMedia(f) && canShareFiles() && !fetching) {   // 先抓好檔案，按下去才能立刻叫出分享選單（iOS 要求在點擊當下呼叫）
    fetching = true;
    fetch(M + f).then(r => { if (!r.ok) throw new Error(r.status); return r.blob(); })
      .then(b => {
        shareFile = new File([b], f, { type: 'video/mp4' });
        if (!navigator.canShare({ files: [shareFile] })) { shareFile = null; return; }
        if (wantShare) { saveLink.textContent = UI.saveReady; saveLink.classList.remove('busy'); }
      })
      .catch(() => { shareFile = null; })
      .finally(() => { fetching = false; });
  }
}
function openSavePage() {
  const w = window.open('save.html', '_blank');
  if (!w) location.href = 'save.html';
}
function downloadFallback() {
  if (supportsDownload()) {
    const a = document.createElement('a'); a.href = saveLink.href; a.download = CT.media.recap; a.type = 'video/mp4';
    document.body.appendChild(a); a.click(); a.remove();
  } else openSavePage();
}
saveLink.addEventListener('click', ev => {
  stop(ev);
  if (!hasMedia(CT.media.recap)) { ev.preventDefault(); return; }
  if (shareFile) {                                   // 路徑 1：Web Share（iOS 選「儲存影片」進相簿）
    ev.preventDefault();
    navigator.share({ files: [shareFile], title: 'Sandy 生日快樂' })
      .catch(err => { if (err && err.name !== 'AbortError') downloadFallback(); });
    return;
  }
  if (fetching && canShareFiles()) {                 // 還在抓檔：等好了再點一次
    ev.preventDefault(); wantShare = true;
    saveLink.textContent = UI.savePreparing; saveLink.classList.add('busy');
    return;
  }
  if (supportsDownload()) return;                    // 路徑 2：<a download> 直接下載（瀏覽器預設行為）
  ev.preventDefault(); openSavePage();               // 路徑 3：開新頁播影片，長按儲存
});

// ── 開始 ──
function start() {
  if (started) return;
  started = true;
  unlockAudio();
  startEl.hidden = true;
  locEl.textContent = scenes[0].loc; locEl.style.display = '';
  render(); updateChip(true); slideIn(locEl);
  preload(chapterUrls(1));
}
function init() {
  MEDIA = new Set(Array.isArray(window.MEDIA_FILES) ? window.MEDIA_FILES : []);
  $('startGo').textContent = UI.start; $('startSub').textContent = UI.startSub;
  $('rotate').textContent = UI.rotate; skipBtn.textContent = UI.skip;
  setBackground(scenes[0]); chipEl.style.display = 'none'; locEl.style.display = 'none';
  app.addEventListener('click', () => { if (!started) start(); else onTap(); });
  app.addEventListener('contextmenu', ev => ev.preventDefault());
  skipBtn.addEventListener('click', skip);
  // 測試用掛鉤（不影響播放）
  window.__sandy = { get ci() { return ci; }, get li() { return li; }, get solved() { return solved; }, get busy() { return busy; },
    line: () => scenes[ci].lines[li], media: () => [...MEDIA] };
}
// media/manifest.js 由 tools/update_media.py 產生（列出 media/ 裡實際有的檔）；加時間戳避免快取到舊清單
const sc = document.createElement('script');
sc.src = 'media/manifest.js?t=' + Date.now();
sc.onload = sc.onerror = init;
document.head.appendChild(sc);
})();
