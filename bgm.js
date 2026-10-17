// Sandy 生日網站 — 背景配樂（原創曲、WebAudio 即時合成，不用音檔、不用函式庫）。
// 每章用哪首在 content.js 的 music.chapters 設定；這個檔只放曲子與合成器。
// 合成器吃任何 BaseAudioContext：網頁用 AudioContext 即時播，tools/bgm_render.py 用 OfflineAudioContext 渲染成 WAV。
(() => {
'use strict';

// ── 曲子（全部原創）──
// mel：每小節一串音，「音名:長度」長度以 unit 拍為單位（預設 1）；r＝休止。每小節要剛好 4 拍。
// chords：每小節一個和弦，用 | 分小節；同一小節兩個和弦用空白隔開（各占半小節）。
// acc：伴奏型態（見 ACC）；legato／ring：主旋律音的延音倍數與尾音秒數（越小越跳音）。
const SONGS = {
  // 神秘：A 小調、72 BPM，音樂盒稀疏地問問題，底下長音 pad
  mystery: { bpm:72, unit:.5, acc:'pad', legato:1.2, ring:.9, mel:[
    'r:2 E5 A5 B5 C6:3', 'B5:2 A5:2 E5:4', 'r:2 F5 A5 C6 E6:3', 'D6:2 B5:2 G#5:4',
    'r:2 E5 A5 B5 C6:3', 'D6:2 C6 B5 A5:4', 'r:2 F5:2 A5:2 D6:2', 'C6 B5 G#5:2 E5:4',
    'r:2 C6:2 A5:2 F5:2', 'r:2 D6:2 B5:2 G5:2', 'E5:2 A5:2 C6:2 E6:2', 'D6:3 C6 B5:4',
    'r:2 A5:2 F5:2 D5:2', 'r:2 C5:2 F5:2 A5:2', 'G#5:3 B5 D6:4', 'r:4 E5:4'],
    chords:'Am|Am|F|E|Am|Am|Dm|E|F|G|Am|Am|Dm|F|E|E' },

  // 輕快 1：C 大調、112 BPM，跳音旋律＋低音蹦蹦、反拍輕和弦（32 小節）
  playful: { bpm:112, unit:.5, acc:'bounce', legato:.6, ring:.18, mel:[
    'E5 G5 r G5 A5 G5 E5:2', 'C5 E5 r E5 D5 C5 A4:2', 'A4 C5 F5 A5 G5 F5 E5 D5', 'D5 r G5 r B4:2 r:2',
    'E5 G5 r G5 A5 G5 E5:2', 'C6 B5 A5 G5 E5:2 C5:2', 'D5 F5 A5 F5 G5 B5 D6 B5', 'C6:2 G5 E5 C5:2 r:2',
    'r A5 A5 G5 F5:2 C5:2', 'r B5 B5 A5 G5:2 D5:2', 'E5 G5 B5 G5 E5 G5 B5:2', 'A5 C6 B5 A5 E5:4',
    'F5 E5 D5 E5 F5:2 A5:2', 'G5 F5 E5 F5 G5:2 B5:2', 'C6 r G5 r E5 r C5 r', 'D5 E5 F5 G5 A5 B5 D6:2',
    'E5 G5 r G5 A5 G5 E5:2', 'C5 E5 r E5 D5 C5 A4:2', 'A4 C5 F5 A5 G5 F5 E5 D5', 'G5 F5 E5 D5 B4:2 r:2',
    'E5 G5 r G5 A5 G5 E5:2', 'C6 B5 A5 B5 C6:2 E6:2', 'F5 A5 D6 A5 G5 B5 D6 F6', 'E6:2 C6 G5 C6:2 r:2',
    'r E5 A5 B5 C6:2 A5:2', 'r E5 G5 A5 B5:2 G5:2', 'r F5 A5 C6 D6:2 C6 A5', 'G5:2 E5 G5 C6:4',
    'r D5 F5 A5 D6:2 C6 A5', 'B5:2 G5 B5 E6:4', 'D6 C6 A5 F5 D6 B5 G5 F5', 'E5:2 G5 E5 C5:2 r:2'],
    chords:'C|Am|F|G|C|Am|Dm G|C|F|G|Em|Am|Dm|G|C|G|C|Am|F|G|C|Am|Dm G|C|Am|Em|F|C|Dm|Em|F G|C' },

  // 輕快 2：F 大調、120 BPM，像騎車兜風，低音走四分音、反拍小和弦（32 小節）
  breezy: { bpm:120, unit:.5, acc:'skip', legato:.6, ring:.22, mel:[
    'C5 F5 A5:2 G5 F5 C5:2', 'D5 F5 A5:2 G5 F5 D5:2', 'Bb4 D5 F5 Bb5 A5 G5 F5 D5', 'E5:2 G5:2 C6:2 r:2',
    'C6 A5 F5:2 G5 A5 C6:2', 'D6 A5 F5:2 E5 F5 A5:2', 'G5 Bb5 D6 Bb5 C6 Bb5 G5 E5', 'F5:2 A5 C6 F6:2 r:2',
    'r D6 Bb5 F5 D5:2 F5:2', 'r E6 C6 G5 E5:2 G5:2', 'A5 C6 E6 C6 A5 E5 C5:2', 'D5 F5 A5 D6 C6:2 A5:2',
    'Bb5 A5 G5 F5 G5:2 D5:2', 'E5 F5 G5 A5 Bb5:2 C6:2', 'A5 G5 F5 C5 F5:2 A5:2', 'G5 F5 E5 D5 C5:2 r:2',
    'D6:2 C6 Bb5 F5:2 D5:2', 'E6:2 D6 C6 G5:2 E5:2', 'F5 A5 C6 A5 F5 A5 C6:2', 'D6 C6 A5 F5 D5:4',
    'Bb4 D5 F5 A5 Bb5:2 D6:2', 'C6 Bb5 G5 E5 C5:2 E5:2', 'F5:2 G5 A5 C6:2 A5:2', 'F5:4 r:4',
    'G5 Bb5 D6 Bb5 G5:2 D5:2', 'A5 C6 E6 C6 A5:2 E5:2', 'F5 G5 A5 Bb5 D6:2 F5:2', 'E5 F5 G5 C6 E6:2 C6:2',
    'D6:2 A5 F5 D5:2 F5:2', 'F5:2 D5 F5 Bb5:2 D6:2', 'Bb5 A5 G5 D5 C6 Bb5 G5 E5', 'F5:2 C5 A4 F4:2 r:2'],
    chords:'F|Dm|Bb|C|F|Dm|Gm C|F|Bb|C|Am|Dm|Gm|C|F|C|Bb|C|F|Dm|Bb|C|F|F|Gm|Am|Bb|C|Dm|Bb|Gm C|F' },

  // 溫暖：D 大調、66 BPM，長音旋律＋分解和弦，收禮物那章用
  warm: { bpm:66, unit:.5, acc:'arp', legato:1.3, ring:.7, mel:[
    'F#5:3 E5 D5:2 A4:2', 'C#5:3 D5 E5:4', 'D5:3 C#5 B4:2 F#5:2', 'E5:6 D5:2',
    'F#5:3 G5 A5:2 D6:2', 'B5:3 A5 G5:4', 'G5:2 F#5:2 E5:2 G5:2', 'E5:6 r:2',
    'D6:3 B5 G5:4', 'C#6:3 A5 E5:4', 'A5:2 C#6:2 F#5:4', 'B5:3 A5 F#5:2 D5:2',
    'G5:3 F#5 E5:2 D5:2', 'C#5:2 E5:2 A5:4', 'F#5:3 E5 D5:4', 'r:4 A4:2 C#5:2'],
    chords:'D|A|Bm|G|D|G|Em|A|G|A|F#m|Bm|G|A|D|D' },
};

// ── 樂理小工具 ──
const PC = { C:0, D:2, E:4, F:5, G:7, A:9, B:11 };
function midi(name) {
  const m = /^([A-G])([#b]?)(\d)$/.exec(name);
  if (!m) throw new Error('bgm：看不懂的音名 ' + name);
  return 12 * (+m[3] + 1) + PC[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
}
const hz = m => 440 * Math.pow(2, (m - 69) / 12);
const fit = (pc, lo) => lo + (((pc - lo) % 12) + 12) % 12;      // 把音高類別放進 [lo, lo+11]
function chord(name) {
  const m = /^([A-G][#b]?)(m?)$/.exec(name);
  if (!m) throw new Error('bgm：看不懂的和弦 ' + name);
  const root = midi(m[1] + '4') % 12;
  return { root, third: root + (m[2] ? 3 : 4), fifth: root + 7 };
}
const triad = (c, lo) => [c.root, c.third, c.fifth].map(p => hz(fit(p, lo)));

// 伴奏型態：在 [t, t+d) 拍之間塞事件
const ACC = {
  pad(ev, c, t, d) {                                   // 長音 pad＋低音長音
    ev.push({ t, d, k:'pad', f: triad(c, 55) });
    ev.push({ t, d, k:'bass', f: hz(fit(c.root, 40)) });
  },
  bounce(ev, c, t, d) {                                // 正拍低音（根音、五度）、反拍輕和弦
    for (let i = 0; i < d; i++) {
      if (i % 2 === 0) ev.push({ t: t + i, d: .9, k:'bass', f: hz(fit(i ? c.fifth : c.root, 40)) });
      else ev.push({ t: t + i, d: .4, k:'stab', f: triad(c, 60) });
    }
  },
  skip(ev, c, t, d) {                                  // 四分音走低音＋後半拍小和弦
    const r = fit(c.root, 40);
    for (let i = 0; i < d; i++) {
      ev.push({ t: t + i, d: .5, k:'bass', f: hz(r + [0, 7, 12, 7][i % 4]) });
      ev.push({ t: t + i + .5, d: .25, k:'stab', f: triad(c, 62) });
    }
  },
  arp(ev, c, t, d) {                                   // 八分音分解和弦＋低音＋很淡的 pad
    const r = fit(c.root, 48), th = c.third - c.root, pat = [0, 7, 12, th + 12, 12, 7, 12, th + 12];
    for (let i = 0; i < d * 2; i++) ev.push({ t: t + i / 2, d: .9, k:'arp', f: hz(r + pat[i % 8]) });
    ev.push({ t, d, k:'bass', f: hz(fit(c.root, 38)) });
    ev.push({ t, d, k:'pad', f: triad(c, 55), soft: true });
  },
};

// 曲子 → 依拍排序的事件表（每首只算一次）
const built = {};
function build(mood) {
  if (built[mood]) return built[mood];
  const s = SONGS[mood], ev = [], BPB = 4;
  const bars = s.chords.split('|').map(x => x.trim().split(/\s+/));
  if (bars.length !== s.mel.length) throw new Error(`bgm ${mood}：和弦 ${bars.length} 小節、旋律 ${s.mel.length} 小節`);
  bars.forEach((chs, b) => {
    const b0 = b * BPB;
    let pos = 0;
    s.mel[b].trim().split(/\s+/).forEach(tok => {
      const [n, l] = tok.split(':'), len = (l ? +l : 1) * s.unit;
      if (n !== 'r') ev.push({ t: b0 + pos, d: len, k:'mel', f: hz(midi(n)) });
      pos += len;
    });
    if (Math.abs(pos - BPB) > 1e-6) throw new Error(`bgm ${mood}：第 ${b + 1} 小節是 ${pos} 拍`);
    const seg = BPB / chs.length;
    chs.forEach((cn, j) => ACC[s.acc](ev, chord(cn), b0 + j * seg, seg));
  });
  ev.sort((x, y) => x.t - y.t);
  return (built[mood] = { ev, beats: bars.length * BPB, spb: 60 / s.bpm, s });
}

// ── 合成 ──
let liveNodes = 0;    // 還沒結束的發聲 node 數（測試看有沒有洩漏）
function osc(ctx, dest, type, f, t, a, peak, end, detune) {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.value = f; if (detune) o.detune.value = detune;
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(peak, t + a);
  g.gain.exponentialRampToValueAtTime(.0001, end);
  o.connect(g); g.connect(dest);
  o.start(t); o.stop(end + .03);
  liveNodes++;
  o.onended = () => { liveNodes--; try { o.disconnect(); g.disconnect(); } catch (e) {} };
}
function padTone(ctx, dest, f, t, dur, peak) {        // 慢起音、持續、慢收尾
  const A = Math.min(1.2, dur * .35), R = .9;
  [-7, 7].forEach(dt => {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.type = 'triangle'; o.frequency.value = f; o.detune.value = dt;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(peak, t + A);
    g.gain.setValueAtTime(peak, t + dur);
    g.gain.linearRampToValueAtTime(0, t + dur + R);
    o.connect(g); g.connect(dest);
    o.start(t); o.stop(t + dur + R + .03);
    liveNodes++;
    o.onended = () => { liveNodes--; try { o.disconnect(); g.disconnect(); } catch (e) {} };
  });
}
function play(v, e, t) {
  const ctx = v.ctx, s = v.data.s, sec = e.d * v.data.spb;
  switch (e.k) {
    case 'mel': {                                      // 音樂盒／鋼片琴：基音＋八度泛音（泛音收得快）＋一點點亮點
      const end = t + Math.max(.28, Math.min(2.8, sec * s.legato + s.ring));
      osc(ctx, v.melLP, 'sine', e.f, t, .006, .5, end);
      osc(ctx, v.melLP, 'sine', e.f * 2, t, .004, .11, t + (end - t) * .55);
      osc(ctx, v.melLP, 'triangle', e.f * 4, t, .002, .025, t + .12);
      break;
    }
    case 'arp': {
      const end = t + Math.min(1.6, sec + .5);
      osc(ctx, v.melLP, 'sine', e.f, t, .008, .13, end);
      osc(ctx, v.melLP, 'sine', e.f * 2, t, .005, .03, t + (end - t) * .5);
      break;
    }
    case 'bass': {
      const end = t + Math.min(3, sec * .95 + .25);
      osc(ctx, v.padLP, 'sine', e.f, t, .015, .3, end);
      osc(ctx, v.padLP, 'sine', e.f * 2, t, .01, .07, t + (end - t) * .5);
      break;
    }
    case 'stab':
      e.f.forEach(f => osc(ctx, v.melLP, 'sine', f, t, .005, .055, t + .24));
      break;
    case 'pad':
      e.f.forEach(f => padTone(ctx, v.padLP, f, t, sec, e.soft ? .022 : .045));
      break;
  }
}

function ramp(p, val, now, dur) {
  p.cancelScheduledValues(now);
  p.setValueAtTime(p.value, now);
  p.linearRampToValueAtTime(val, now + Math.max(.01, dur));
}

// 一首曲子的播放頭：自己的 bus（交叉淡入淡出用）＋濾波
class Voice {
  constructor(eng, mood) {
    const ctx = this.ctx = eng.ctx;
    this.mood = mood; this.data = build(mood);
    this.bus = ctx.createGain(); this.bus.gain.value = 0; this.bus.connect(eng.mix);
    this.melLP = ctx.createBiquadFilter(); this.melLP.type = 'lowpass'; this.melLP.frequency.value = 4200; this.melLP.Q.value = .5;
    this.padLP = ctx.createBiquadFilter(); this.padLP.type = 'lowpass'; this.padLP.frequency.value = 1100; this.padLP.Q.value = .5;
    this.melLP.connect(this.bus); this.padLP.connect(this.bus);
    this.idx = 0; this.anchor = 0; this.beat = 0; this.running = false;
  }
  resume(at) {                                         // 從暫停的那一拍接著播
    if (this.running) return;
    const ev = this.data.ev;
    this.anchor = at - this.beat * this.data.spb;
    this.idx = ev.findIndex(e => e.t >= this.beat - 1e-9); if (this.idx < 0) this.idx = 0;
    this.running = true;
  }
  pause() {
    if (!this.running) return;
    const ev = this.data.ev;
    this.beat = this.idx < ev.length ? ev[this.idx].t : 0;
    this.running = false;
  }
  tick(until) {                                        // lookahead：把 until 之前該響的音排進去
    const ev = this.data.ev, spb = this.data.spb, now = this.ctx.currentTime;
    let guard = 0;
    while (this.running && guard++ < 512) {
      if (this.idx >= ev.length) { this.idx = 0; this.anchor += this.data.beats * spb; }
      const e = ev[this.idx], t = this.anchor + e.t * spb;
      if (t > until) break;
      if (t >= now - .05) play(this, e, Math.max(t, now));   // 太晚的（卡頓後）就跳過，不要一次全擠出來
      this.idx++;
    }
  }
  retire(now, dur) {
    this.pause();
    ramp(this.bus.gain, 0, now, dur);
    const nodes = [this.bus, this.melLP, this.padLP];
    setTimeout(() => nodes.forEach(n => { try { n.disconnect(); } catch (e) {} }), (dur + 3.5) * 1000);
  }
}

// ── 播放器 ──
// opt.volume：主音量（0.12～0.18 合適）；opt.fade：換曲交叉淡入淡出秒數
function create(ctx, opt = {}) {
  const vol = Math.max(0, Math.min(.3, opt.volume == null ? .15 : +opt.volume));
  const FADE = opt.fade == null ? 1 : +opt.fade;
  const eng = { ctx };
  const master = ctx.createGain(); master.gain.value = 0; master.connect(ctx.destination);
  const mix = eng.mix = ctx.createGain(); mix.connect(master);
  // 簡單殘響：回授延遲（濕訊號再過 lowpass，比較柔）
  const dl = ctx.createDelay(1), fb = ctx.createGain(), wlp = ctx.createBiquadFilter(), wet = ctx.createGain();
  dl.delayTime.value = .34; fb.gain.value = .3; wlp.type = 'lowpass'; wlp.frequency.value = 2400; wet.gain.value = .3;
  mix.connect(dl); dl.connect(wlp); wlp.connect(fb); fb.connect(dl); wlp.connect(wet); wet.connect(master);

  let mood = null, voice = null, muted = false, hidden = false, ducked = false, timer = 0, quietAt = 0;
  const active = () => !!mood && !muted && !hidden && !ducked;
  const tick = () => { if (voice && voice.running) voice.tick(ctx.currentTime + .15); };
  const startTimer = () => { if (!timer) timer = setInterval(tick, 25); tick(); };
  const stopTimer = () => { clearInterval(timer); timer = 0; };

  function apply(dur) {
    const now = ctx.currentTime;
    if (active()) {
      ramp(master.gain, vol, now, dur);
      if (voice && !voice.running) voice.resume(now + .08);
      startTimer();
    } else {
      ramp(master.gain, 0, now, dur);
      quietAt = Math.max(quietAt > now ? quietAt : 0, now + Math.max(.01, dur));
      if (voice) voice.pause();                        // 立刻停止排新音，已排的 0.15 秒跟著主音量淡掉
      stopTimer();
    }
  }
  return {
    setMood(m) {
      m = m && SONGS[m] ? m : null;
      if (m === mood) return;
      const now = ctx.currentTime, audible = active() && voice && voice.running;
      mood = m;
      if (voice) voice.retire(now, audible ? FADE : .05);
      voice = m ? new Voice(eng, m) : null;
      if (voice) { if (audible) ramp(voice.bus.gain, 1, now, FADE); else voice.bus.gain.value = 1; }
      apply(FADE);
    },
    setMuted(b) { if (muted === !!b) return; muted = !!b; apply(muted ? .4 : .8); },
    setHidden(b) { if (hidden === !!b) return; hidden = !!b; apply(hidden ? .25 : .8); },
    setDucked(b) { if (ducked === !!b) return; ducked = !!b; apply(ducked ? .6 : 1); },
    // 主音量確定歸零的時間（AC 時間）；正在播就回 Infinity
    quietUntil() { return active() ? Infinity : quietAt; },
    state() {
      return { mood, muted, hidden, ducked, playing: active(), gain: +master.gain.value.toFixed(4),
               now: +ctx.currentTime.toFixed(3), quietAt: +quietAt.toFixed(3), liveNodes, timer: !!timer };
    },
    // 離線渲染用：直接以主音量從頭排到 sec 秒
    renderAll(m, sec) {
      mood = m; voice = new Voice(eng, m); voice.bus.gain.value = 1; master.gain.value = vol;
      voice.resume(.05); voice.tick(sec);
    },
  };
}

// OfflineAudioContext 渲染一段（tools/bgm_render.py 呼叫）
function renderOffline(mood, sec = 20, sr = 44100, opt = {}) {
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const ctx = new OAC(2, Math.round(sec * sr), sr);
  create(ctx, opt).renderAll(mood, sec);
  return ctx.startRendering();
}

window.SandyBGM = { create, renderOffline, moods: Object.keys(SONGS), build,
  info: m => { const b = build(m); return { bpm: b.s.bpm, bars: b.beats / 4, loopSec: +(b.beats * b.spb).toFixed(1), events: b.ev.length }; } };
})();
