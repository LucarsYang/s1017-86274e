#!/usr/bin/env python3
"""Sandy 生日回顧影片（spec F4）一鍵重產。

用法（在任何目錄都可）：
    python3 site/tools/build_video.py            # 產 site/media/sandy-birthday-recap.mp4
    python3 site/tools/build_video.py --preview 3,12.5   # 只出指定秒數的單格 PNG（調版面用）
    python3 site/tools/build_video.py --snapshots        # 產完後抽 6 格到 evidence/video-*.png

site/media/cheng-animation.mp4 存在時，自動插在「今晚」段落（丞丞台詞之後），
有聲音就把音樂壓低、放動畫原音。動畫過長會截到總長 ≤ 90 秒（--anim-max 可改）。

劇本、章節、全家福排法、生日快樂歌旋律照 views/2026-10-10-sandy-birthday-mockup-v3.html。
需求：python3 + Pillow、ffmpeg/ffprobe（libx264、aac）、macOS 內建字型（PingFang／Apple Color Emoji）。
"""
import argparse
import glob
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import wave
from array import array

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
TOOLS = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(TOOLS)
PROJ = os.path.dirname(SITE)

# ---------------------------------------------------------------- 字型
def _pingfang():
    for p in sorted(glob.glob('/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*/AssetData/PingFang.ttc')) + \
             ['/System/Library/Fonts/PingFang.ttc', '/Library/Fonts/PingFang.ttc']:
        if os.path.exists(p):
            return {'regular': (p, 2), 'medium': (p, 6), 'semibold': (p, 10)}
    p = '/System/Library/Fonts/STHeiti Medium.ttc'   # 備援：系統一定有
    return {'regular': (p, 0), 'medium': (p, 0), 'semibold': (p, 0)}

PF = _pingfang()
EMOJI = ('/System/Library/Fonts/Apple Color Emoji.ttc', 0)
SNELL = ('/System/Library/Fonts/Supplemental/SnellRoundhand.ttc', 2)
BRADLEY = ('/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf', 0)

_font_cache, _glyph_cache, _notdef = {}, {}, {}

def font(spec, size):
    key = (spec, size)
    if key not in _font_cache:
        p, i = spec
        _font_cache[key] = ImageFont.truetype(p, 160 if spec == EMOJI else size, index=i)
    return _font_cache[key]

def _glyph_sig(f, ch, emoji):
    s = int(f.size * 2.2)
    im = Image.new('RGBA' if emoji else 'L', (s, s))
    ImageDraw.Draw(im).text((f.size * .4, f.size * .2), ch, font=f, fill=(255, 255, 255, 255) if emoji else 255,
                            embedded_color=emoji)
    return im.tobytes()

def has_glyph(spec, size, ch):
    """字型裡有沒有這個字（跟 .notdef 方塊比對）——防破字。"""
    key = (spec, size, ch)
    if key not in _glyph_cache:
        f, emoji = font(spec, size), spec == EMOJI
        nk = (spec, size)
        if nk not in _notdef:
            _notdef[nk] = _glyph_sig(f, '\U0010FFFD', emoji)
        sig = _glyph_sig(f, ch, emoji)
        # 空白字元畫出來本來就是空的：.notdef 也是空的字型無從判斷，視為有；否則跟 .notdef 方塊比
        _glyph_cache[key] = sig != _notdef[nk] or (ch.isspace() and not any(_notdef[nk]))
    return _glyph_cache[key]

_emoji_cache = {}
def emoji_img(ch, h):
    key = (ch, h)
    if key not in _emoji_cache:
        f = font(EMOJI, 160)
        im = Image.new('RGBA', (220, 220))
        ImageDraw.Draw(im).text((20, 10), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        _emoji_cache[key] = im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)
    return _emoji_cache[key]

CLOSE = set('，。！？、；：」』）】…—～．,.!?;:)%')
OPEN = set('（「『【(')

class Style:
    def __init__(self, chain, size, color, line_h=1.5, tracking=0, stroke=0, stroke_fill=None):
        self.chain, self.size, self.color = list(chain) + [EMOJI], size, color
        self.line_h, self.tracking, self.stroke, self.stroke_fill = line_h, tracking, stroke, stroke_fill

    def pick(self, ch):
        for spec in self.chain:
            if has_glyph(spec, self.size, ch):
                return spec
        raise SystemExit(f'破字：字型裡沒有「{ch}」(U+{ord(ch):04X})')

    def _runs(self, line):
        runs = []
        for ch in line:
            spec = self.pick(ch)
            if runs and runs[-1][0] == spec and spec != EMOJI:
                runs[-1][1] += ch
            else:
                runs.append([spec, ch])
        return runs

    def _w(self, s):
        w = 0
        for spec, txt in self._runs(s):
            if spec == EMOJI:
                w += sum(emoji_img(c, self._eh()).width + self.size * .08 for c in txt)
            else:
                w += font(spec, self.size).getlength(txt) + self.tracking * len(txt)
        return w

    def _eh(self):
        return int(self.size * 1.02)

    def wrap(self, text, max_w):
        """斷行；每段先照 max_w 斷，再找同行數的最小寬度，讓各行長度平均（避免一兩個字孤零零掉到下一行）。"""
        text = text.replace('\ufe0f', '')
        lines = []
        for para in text.split('\n'):
            ls = self._wrap1(para, max_w)
            if max_w and len(ls) > 1:
                pl = self._wrap_punct(para, max_w)   # 先試只在標點後斷行（不拆詞）
                if pl and len(pl) <= len(ls):
                    lines += pl
                    continue
                lo, hi = max_w / len(ls) * .8, max_w
                while hi - lo > 2:
                    mid = (lo + hi) / 2
                    if len(self._wrap1(para, mid)) <= len(ls):
                        hi = mid
                    else:
                        lo = mid
                ls = self._wrap1(para, hi)
            lines += ls
        return lines

    def _wrap_punct(self, para, max_w):
        phrases = re.findall(r'[^，。！？、；…—]+[，。！？、；…—]*|[，。！？、；…—]+', para)
        fits = lambda x: self._w(x.strip()) <= max_w + (self.size * .5 if x.strip()[-1:] in CLOSE else 0)
        lines, cur = [], ''
        for ph in phrases:
            if not fits(ph):
                return None
            if cur and not fits(cur + ph):
                lines.append(cur.rstrip())
                cur = ph.lstrip()
            else:
                cur += ph
        lines.append(cur.rstrip())
        return lines

    def _wrap1(self, para, max_w):
        lines = []
        toks = re.findall(r"[A-Za-z0-9.%'/:\-]+|\s+|.", para)
        cur = ''
        for i, tok in enumerate(toks):
            if not cur and tok.isspace():
                continue
            if cur and max_w and self._w(cur + tok) > max_w:
                if tok in CLOSE or (len(tok) == 1 and tok in CLOSE):   # 標點不放行首：掛在行尾
                    cur += tok
                    continue
                nxt = ''
                if cur[-1] in OPEN:   # 開括號不留行尾
                    nxt, cur = cur[-1], cur[:-1]
                lines.append(cur.rstrip())
                cur = nxt + ('' if tok.isspace() else tok)
            else:
                cur += tok
        lines.append(cur.rstrip())
        return lines

    def render(self, text, max_w=None, align='left'):
        lines = self.wrap(text, max_w)
        lh = round(self.size * self.line_h)
        pad = self.stroke + 4
        widths = [self._w(l) for l in lines]
        cw = int(max(widths + [1])) + 2 * pad
        im = Image.new('RGBA', (cw, lh * len(lines) + 2 * pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        asc, desc = font(self.chain[0], self.size).getmetrics()
        for i, (line, lw) in enumerate(zip(lines, widths)):
            x = pad + ((cw - 2 * pad - lw) / 2 if align == 'center' else 0)
            base = pad + i * lh + (lh - (asc + desc)) / 2 + asc
            for spec, txt in self._runs(line):
                if spec == EMOJI:
                    for c in txt:
                        e = emoji_img(c, self._eh())
                        im.alpha_composite(e, (int(x + self.size * .04), int(base - self.size * .9)))
                        x += e.width + self.size * .08
                    continue
                f = font(spec, self.size)
                if self.tracking:
                    for c in txt:
                        d.text((x, base), c, font=f, fill=self.color, anchor='ls',
                               stroke_width=self.stroke, stroke_fill=self.stroke_fill)
                        x += f.getlength(c) + self.tracking
                else:
                    d.text((x, base), txt, font=f, fill=self.color, anchor='ls',
                           stroke_width=self.stroke, stroke_fill=self.stroke_fill)
                    x += f.getlength(txt)
        return im

def shadowed(im, off=(0, 10), blur=14, alpha=110, pad=None):
    pad = pad if pad is not None else blur * 2 + max(abs(off[0]), abs(off[1]))
    cv = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = im.getchannel('A').point(lambda v: v * alpha // 255)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 0))
    sh.putalpha(a)
    cv.paste(sh, (pad + off[0], pad + off[1]))
    cv = cv.filter(ImageFilter.GaussianBlur(blur))
    cv.alpha_composite(im, (pad, pad))
    return cv, pad

# ---------------------------------------------------------------- 小工具
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def ease_back(x):
    x = clamp(x)
    c1 = 1.70158
    return 1 + (c1 + 1) * (x - 1) ** 3 + c1 * (x - 1) ** 2

def ease_out(x):
    return 1 - (1 - clamp(x)) ** 3

def ease_io(x):
    return -(math.cos(math.pi * clamp(x)) - 1) / 2

_lut = {}
def put(frame, im, x, y, scale=1.0, alpha=1.0, angle=0.0, anchor='center'):
    """把 RGBA 圖貼到 frame；(x, y) 是 anchor 點（center 或 bottom＝底部中點）。"""
    if alpha <= 0.004:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BILINEAR)
    if abs(angle) > 0.05:
        im = im.rotate(angle, Image.BICUBIC, expand=True)
    if alpha < 0.996:
        k = round(alpha * 255)
        if k not in _lut:
            _lut[k] = [v * k // 255 for v in range(256)]
        im = im.copy()
        im.putalpha(im.getchannel('A').point(_lut[k]))
    px = round(x - im.width / 2)
    py = round(y - im.height / 2) if anchor == 'center' else round(y - im.height)
    frame.paste(im, (px, py), im)

def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

# ---------------------------------------------------------------- 劇本（照 mockup v3 的 scenes 挑句）
C = {  # 角色：立繪 key、名牌、顏色、站位
    'dad':   ('lucas', '老公', '#4a7bd0', 'left'),
    'sandy': ('sandy', 'Sandy', '#e2667f', 'right'),
    'cheng': ('cheng', '丞丞', '#3d9a5f', 'right'),
    'hua':   ('hua', '小花', '#e0a020', 'left'),
}
BUST = {'cheng': 192, 'lucas': 184, 'sandy': 174, 'hua': 174}   # 丞丞 > 老公 > Sandy = 小花
SCALE = 3.9
COLORS = ['#ff6b8b', '#ffd166', '#4fc3f7', '#81c784', '#ba68c8', '#ff8a65']
LOC_TODAY = '📍 板橋重慶・明水然．樂'

def L(who, e, t, s=None, chip=None, dur=4.4):
    return dict(kind='nar' if who == 'nar' else 'line', who=who, e=e, t=t, s=s, chip=chip, dur=dur)

def build_script(anim_dur):
    ch5 = ([L('cheng', 'happy', '媽媽，這是我做的動畫！', 'cheng/11', dur=3.4),
            dict(kind='anim', dur=anim_dur, chip=None),
            L('dad', 'laugh', '妳現在看的這個網站，就是我送妳的禮物。', 'lucas/10', dur=4.6)]
           if anim_dur else
           [L('nar', None, '10/17 晚上，明水然．樂。\n也就是——妳自己選的那間 😎', dur=4.2),
            L('dad', 'laugh', '妳現在看的這個網站，就是我送妳的禮物。', 'lucas/10', dur=4.6)])
    return [
        dict(key='open', bg='bg0-mystery', loc='📍 ？？？・機密檔案室', kb=(1.0, 1.12, (.5, .42), (.5, .55)), beats=[
            dict(kind='title', t='TOP SECRET\nSandy 生日作戰檔案', dur=3.6),
            L('dad', 'happy', 'Sandy，這份檔案記錄了我們三個這一個月偷偷在做的事。', dur=4.6)]),
        dict(key='ch1', bg='bg1-home-desk', loc='📍 家裡餐桌・秘密會議室', kb=(1.12, 1.0, (.42, .5), (.55, .5)), beats=[
            L('cheng', 'thinking', '媽媽生日快到了，要送什麼？', chip='9/17 晚上', dur=4.0),
            L('hua', 'happy', '我知道了！！帶媽媽去吃大餐！！', chip='10/3 晚上', dur=4.0)]),
        dict(key='ch2', bg='bg2-gulajazz', loc='📍 愛買 3F・古拉爵', chip='10/9 中午', kb=(1.0, 1.12, (.55, .45), (.45, .55)), beats=[
            L('dad', 'surprised', '啊！說好吃大餐……我竟然忘了訂位！', 'lucas/03', dur=4.8),
            L('nar', None, 'Sandy，妳親手選了自己的生日大餐 😎\n三次秘密會議，都不如壽星一句話。', 'sandy/12', dur=4.6)]),
        dict(key='ch3', scooter=True, loc='📍 板橋街頭・機車移動會議室', chip='10/10 早上', beats=[
            L('nar', None, '10/10 早上，三名特務騎機車出動。', dur=3.6),
            dict(L('dad', None, '機車會議開始！每個人都要準備一份禮物給媽媽。', dur=4.6), noPortrait=True)]),
        dict(key='ch4', bg='bg4-home-sofa', loc='📍 家裡客廳・網站開工現場', chip='10/10 中午', kb=(1.12, 1.0, (.5, .55), (.5, .45)), beats=[
            L('sandy', 'happy', '老公～床單拿去洗一下！', dur=3.8),
            L('dad', 'surprised', '馬上去 🏃（網站進度：還是 3%）', 'lucas/16', dur=4.2)]),
        dict(key='ch5', bg='bg5-mingshuiran', loc=LOC_TODAY, chip='10/17 今晚', kb=(1.0, 1.1, (.5, .5), (.42, .45)), beats=ch5),
        dict(key='ch6', bg='bg5-mingshuiran', loc=LOC_TODAY, chip='10/17 今晚', kb=(1.1, 1.0, (.42, .45), (.5, .5)), party=True, beats=[
            dict(kind='cake', t='惟詩，謝謝妳總把我們放在心上。\n這次許願，也記得把自己放進去。', dur=4.6),
            dict(kind='party', t='🎉 Sandy，生日快樂！\n愛妳的 老公、丞丞、小花', dur=10.4)]),
        dict(key='end', bg='bg5-mingshuiran', kb=(1.0, 1.08, (.5, .5), (.5, .42)), party=True, fade_out=1.8, beats=[
            dict(kind='ending', dur=8.0)]),
    ]

# 派對拍立得輪播（mockup SLIDES；全家福留給結尾）
SLIDES = [
    dict(cap='9/17～10/3　秘密會議', bg='bg1-home-desk', who='hua-happy'),
    dict(cap='10/9　爸爸的演技', bg='bg2-gulajazz', who='lucas-surprised'),
    dict(cap='10/10　機車三貼', bg='bg3-street', scooter=True),
    dict(cap='10/10　進度 3%', bg='bg4-home-sofa', who='lucas-thinking'),
    dict(cap='10/17　妳選的鐵板燒', bg='bg5-mingshuiran', who='sandy-laugh'),
]
FAMILY = dict(cap='2026.10.17　我們家 ♥', family=True)

# ---------------------------------------------------------------- 素材
class Assets:
    def __init__(self, root):
        self.root = root
        self._c = {}

    def path(self, rel):
        p = os.path.join(self.root, rel)
        if not os.path.exists(p):
            raise SystemExit(f'找不到素材：{p}')
        return p

    def img(self, rel, mode='RGBA'):
        k = (rel, mode)
        if k not in self._c:
            self._c[k] = Image.open(self.path(rel)).convert(mode)
        return self._c[k]

    def bg(self, name):
        return self.img(f'round2/2026-10-10-{name}.png', 'RGB')

    def portrait(self, key, e):
        return self.img(f'portraits/{key}-{e}.png')

    def sticker(self, s):
        return self.img(f'stickers/{s}.png')

# ---------------------------------------------------------------- 版面元件
ST_DLG = Style([PF['medium']], 54, (59, 42, 42), line_h=1.55)
ST_NAR = Style([PF['medium']], 54, (255, 255, 255), line_h=1.55)
ST_NAME = Style([PF['semibold']], 40, (255, 255, 255), line_h=1.2)
ST_CHIP = Style([PF['semibold']], 40, (59, 42, 42), line_h=1.25)
ST_LOC = Style([PF['regular']], 38, (255, 255, 255), line_h=1.25)
DLG_BOTTOM = 1760

def pill(text, style, bg, padx=30, pady=14):
    t = style.render(text)
    w, h = t.width + 2 * padx, t.height + 2 * pady
    im = Image.new('RGBA', (w, h))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=bg)
    im.alpha_composite(t, (padx, pady))
    return shadowed(im, (0, 5), 8, 70)[0]

def rounded_mask(size, r):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m

def build_dialog(text, nar=False, name=None, color=None, side='left'):
    BW, PX = 980, 62
    st = ST_NAR if nar else ST_DLG
    txt = st.render(text, max_w=BW - 2 * PX, align='center' if nar else 'left')
    PT, PB = (66 if name else 50), 50
    BH = max(300, PT + txt.height + PB)
    box = Image.new('RGBA', (BW, BH + 60))
    d = ImageDraw.Draw(box)
    top = 60
    d.rounded_rectangle((0, top, BW - 1, top + BH - 1), 54, fill=(20, 14, 14, 216) if nar else (255, 255, 255, 255))
    if name:
        nx = 300 if side == 'left' else BW - 300
        d.polygon([(nx - 32, top + 2), (nx + 32, top + 2), (nx, top - 32)], fill=(255, 255, 255, 255))
        tag = ST_NAME.render(name)
        tw, th = tag.width + 64, 76
        tx = 56 if side == 'left' else BW - 56 - tw
        d.rounded_rectangle((tx, top - 38, tx + tw, top - 38 + th), th // 2, fill=hexrgb(color) + (255,))
        box.alpha_composite(tag, (tx + 32, top - 38 + (th - tag.height) // 2))
    if nar:
        box.alpha_composite(txt, ((BW - txt.width) // 2, top + (BH - txt.height) // 2))
    else:
        box.alpha_composite(txt, (PX - 4, top + PT - 6))
    im, pad = shadowed(box, (0, 16), 22, 120)
    return dict(im=im, x=50 - pad, y=DLG_BOTTOM - BH - top - pad, box_top=DLG_BOTTOM - BH)

def card(w, h, r=56, fill=(255, 255, 255, 255)):
    im = Image.new('RGBA', (w, h))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=fill)
    return im

def cover(src, size):
    sw, sh = src.size
    s = max(size[0] / sw, size[1] / sh)
    im = src.resize((math.ceil(sw * s), math.ceil(sh * s)), Image.LANCZOS)
    x, y = (im.width - size[0]) // 2, (im.height - size[1]) // 2
    return im.crop((x, y, x + size[0], y + size[1]))

def polaroid(A, slide, pw=700):
    """拍立得（mockup slideHTML 的排法，photo 172×150 → pw 寬等比放大）。"""
    k = pw / 172
    ph = round(150 * k)
    if slide.get('family'):
        photo = Image.new('RGB', (pw, ph))
        top, bot = hexrgb('#ffe3ea'), hexrgb('#fff3d1')
        d = ImageDraw.Draw(photo)
        for y in range(ph):
            a = y / (ph - 1)
            d.line([(0, y), (pw, y)], fill=tuple(round(top[i] + (bot[i] - top[i]) * a) for i in range(3)))
        photo = photo.convert('RGBA')
        def ph_(key, e, h):
            im = A.portrait(key, e)
            return im.resize((round(im.width * h / im.height), round(h)), Image.LANCZOS)
        # 後排丞丞（最高）、老公；前排小花、Sandy（戴皇冠）。前排底邊貼齊相片底（切口藏在框外）
        c = ph_('cheng', 'laugh', 92 * k); photo.alpha_composite(c, (round(8 * k), round(6 * k)))
        l = ph_('lucas', 'laugh', 87 * k); photo.alpha_composite(l, (pw - round(10 * k) - l.width, round(10 * k)))
        fh = 83 * k
        ftop = ph + 4 - round(fh)
        hu = ph_('hua', 'happy', fh); photo.alpha_composite(hu, (round(18 * k), ftop))
        sa = ph_('sandy', 'laugh', fh); sx = pw - round(16 * k) - sa.width; photo.alpha_composite(sa, (sx, ftop))
        crown = emoji_img('👑', round(22 * k)).rotate(-14, Image.BICUBIC, expand=True)
        photo.alpha_composite(crown, (pw - round(42 * k) - crown.width, ftop - round(16 * k)))
    else:
        photo = cover(A.bg(slide['bg']), (pw, ph)).convert('RGBA')
        if slide.get('scooter'):
            im = A.img('portraits/scooter-trio.png')
            h = round(120 * k)
            im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
            photo.alpha_composite(im, (round(18 * k), ph - round(2 * k) - h))
        else:
            key, e = slide['who'].split('-')
            im = A.portrait(key, e)
            h = round(118 * k)
            im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
            photo.paste(im, ((pw - im.width) // 2, ph + round(6 * k) - h), im)
    padx, padt = round(8 * k * .55), round(8 * k * .55)
    cap_h = round(pw * .13)
    W_ = pw + 2 * padx
    H_ = padt + ph + cap_h
    pol = Image.new('RGBA', (W_, H_))
    ImageDraw.Draw(pol).rounded_rectangle((0, 0, W_ - 1, H_ - 1), 10, fill=(255, 255, 255, 255))
    pol.paste(photo, (padx, padt), rounded_mask(photo.size, 6))
    st = Style([BRADLEY, PF['medium']], round(pw * .058), (122, 75, 58), line_h=1.2)
    cap = st.render(slide['cap'])
    pol.alpha_composite(cap, ((W_ - cap.width) // 2, padt + ph + (cap_h - cap.height) // 2))
    return shadowed(pol, (0, 22), 26, 120)[0]

# ---------------------------------------------------------------- 背景
def kb_frame(src, z, fx, fy):
    sw, sh = src.size
    w0 = min(sw, sh * W / H)
    h0 = w0 * H / W
    cw, chh = w0 / z, h0 / z
    cx = clamp(fx * sw, cw / 2, sw - cw / 2)
    cy = clamp(fy * sh, chh / 2, sh - chh / 2)
    return src.transform((W, H), Image.EXTENT, (cx - cw / 2, cy - chh / 2, cx + cw / 2, cy + chh / 2), Image.BILINEAR)

class Renderer:
    def __init__(self, A, chapters, anim=None):
        self.A, self.chapters, self.anim = A, chapters, anim
        t = 0
        for c in chapters:
            c['start'] = t
            bt = 0
            for b in c['beats']:
                b['start'] = bt
                bt += b['dur']
            c['dur'] = bt
            t += bt
        self.total = t
        self.cache = {}
        self.dark = Image.new('RGB', (W, H), (20, 12, 12))
        self.black = Image.new('RGB', (W, H), (0, 0, 0))
        bg5 = A.bg('bg5-mingshuiran')
        self.bg5_dim = ImageEnhance.Brightness(bg5).enhance(.82)
        self.bg5_party = ImageEnhance.Color(ImageEnhance.Brightness(bg5).enhance(1.12)).enhance(1.15)
        self.bg5_end = ImageEnhance.Brightness(self.bg5_party).enhance(.62)
        self.glow = self._glow()
        rnd = random.Random(1017)
        self.confetti = [dict(x=rnd.random() * W, c=hexrgb(COLORS[i % 6]), dur=2.6 + rnd.random() * 2,
                              delay=rnd.random() * 2.5, sway=rnd.uniform(-40, 40), rot0=rnd.random() * 360)
                         for i in range(70)]
        self.balloons = [dict(x=(.08 + i * .15) * W, c=hexrgb(COLORS[(i * 2 + 1) % 6]), dur=6 + i % 3,
                              delay=.3 + i * .7, dx=(1 if i % 2 else -1) * 70) for i in range(6)]

    # ---- 快取元件
    def get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def _glow(self):
        g = Image.new('L', (108, 192))
        d = ImageDraw.Draw(g)
        for r in range(70, 0, -1):
            v = round(90 * (1 - r / 70) ** 1.5)
            d.ellipse((54 - r, 86 - r, 54 + r, 86 + r), fill=v)
        return g.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(20))

    def portrait_img(self, key, e):
        def mk():
            im = self.A.portrait(key, e)
            h = round(BUST[key] * SCALE)
            im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
            return shadowed(im, (0, 20), 18, 95)
        return self.get(('por', key, e), mk)

    def sticker_img(self, s, angle):
        def mk():
            im = self.A.sticker(s)
            im = im.resize((340, round(im.height * 340 / im.width)), Image.LANCZOS)
            im = shadowed(im, (0, 12), 14, 90)[0]
            return im.rotate(angle, Image.BICUBIC, expand=True)
        return self.get(('stk', s, angle), mk)

    # ---- 背景
    def draw_bg(self, c, tc, b):
        if c.get('scooter'):
            return self.scooter_bg(tc)
        if c.get('party') or c['key'] == 'end':
            src = self.bg5_end if c['key'] == 'end' else (self.bg5_party if b['kind'] != 'cake' else self.bg5_dim)
        else:
            src = self.A.bg(c['bg'])
        z0, z1, f0, f1 = c['kb']
        p = ease_io(tc / c['dur'])
        return kb_frame(src, z0 + (z1 - z0) * p, f0[0] + (f1[0] - f0[0]) * p, f0[1] + (f1[1] - f0[1]) * p)

    def scooter_bg(self, tc):
        def mk():
            st = self.A.bg('bg3-street')
            sh = 1480
            st = st.resize((round(st.width * sh / st.height), sh), Image.LANCZOS)
            strip = Image.new('RGB', (st.width * 2, sh))
            strip.paste(st, (0, 0))
            strip.paste(st.transpose(Image.FLIP_LEFT_RIGHT), (st.width, 0))   # 鏡像接縫，無限捲動不跳
            sc = self.A.img('portraits/scooter-trio.png')
            sw = 900
            sc = sc.resize((sw, round(sc.height * sw / sc.width)), Image.LANCZOS)
            return strip, shadowed(sc, (0, 22), 16, 80)
        strip, (sc, pad) = self.get('scooter', mk)
        frame = Image.new('RGB', (W, H), (111, 111, 114))
        off = int(tc * 280) % strip.width
        frame.paste(strip, (-off, 0))
        if off + W > strip.width:
            frame.paste(strip, (strip.width - off, 0))
        bump = 6 * (1 - math.cos(2 * math.pi * tc / .7))
        ang = .6 * math.sin(2 * math.pi * tc / .7)
        put(frame, sc, W / 2 + 10, 1450 - bump + pad, angle=ang, anchor='bottom')
        ph = (tc / .6) % 1
        put(frame, emoji_img('💨', 80), 70 - 100 * ph, 1080, alpha=.9 * (1 - ph))
        return frame

    # ---- 派對特效
    def draw_fx(self, frame, t):
        frame.paste(Image.new('RGB', (W, H), (255, 214, 120)), (0, 0), self.glow)
        d = ImageDraw.Draw(frame)
        for p in self.confetti:
            if t < p['delay']:
                continue
            ph = ((t - p['delay']) % p['dur']) / p['dur']
            y = -60 + (H + 120) * ph
            x = p['x'] + p['sway'] * math.sin(ph * 6.28)
            a = math.radians(p['rot0'] + 720 * ph)
            sx = 13 * abs(math.cos(a * 1.3)) + 3
            pts = [(-sx, -21), (sx, -21), (sx, 21), (-sx, 21)]
            ca, sa = math.cos(a), math.sin(a)
            d.polygon([(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts], fill=p['c'])
        for b in self.balloons:
            if t < b['delay']:
                continue
            ph = ((t - b['delay']) % b['dur']) / b['dur']
            q = ph * ph
            x = b['x'] + b['dx'] * q
            y = H + 120 - (H + 600) * q
            c = b['c']
            d.line([(x, y + 80), (x + 10, y + 150), (x - 4, y + 220)], fill=(250, 250, 250), width=3)
            d.polygon([(x - 12, y + 88), (x + 12, y + 88), (x, y + 70)], fill=c)
            d.ellipse((x - 62, y - 80, x + 62, y + 80), fill=c)
            hl = tuple(min(255, v + 90) for v in c)
            d.ellipse((x - 38, y - 56, x - 14, y - 18), fill=hl)

    # ---- 一格
    def frame(self, t):
        t = clamp(t, 0, self.total - 1e-6)
        c = next(c for c in reversed(self.chapters) if t >= c['start'])
        tc = t - c['start']
        b = next(b for b in reversed(c['beats']) if tc >= b['start'])
        tb = tc - b['start']
        fr = self.draw_bg(c, tc, b)
        if c.get('party') and b['kind'] != 'cake':
            self.draw_fx(fr, tb if c['key'] != 'end' else tc + 10.4)
        # 日期 chip＋地點標籤（章首滑入）
        chip = None
        for bb in c['beats']:
            if bb['start'] <= tc:
                chip = bb.get('chip') or chip
        chip = chip or c.get('chip')
        if b['kind'] not in ('ending',):
            if chip:
                im = self.get(('chip', chip), lambda: pill(chip, ST_CHIP, (255, 255, 255, 235)))
                put(fr, im, 56 + im.width / 2, 196, alpha=ease_out((tc - .1) / .4))
            if c.get('loc'):
                im = self.get(('loc', c['loc']), lambda: pill(c['loc'], ST_LOC, (30, 20, 20, 190)))
                x = -im.width / 2 + (56 + im.width) * ease_out((tc - .15) / .7)
                put(fr, im, x, 286)
        getattr(self, 'beat_' + b['kind'])(fr, b, tb, c)
        # 章節轉場：淡入淡出
        fi = .8 if c['start'] == 0 else .45
        fo = c.get('fade_out', .35)
        if tc < fi:
            fr = Image.blend(fr, self.black if c['start'] == 0 else self.dark, 1 - tc / fi)
        elif tc > c['dur'] - fo:
            fr = Image.blend(fr, self.black if 'fade_out' in c else self.dark, (tc - (c['dur'] - fo)) / fo)
        return fr

    # ---- 各種 beat
    def _dialog(self, b):
        def mk():
            if b['kind'] == 'nar':
                return build_dialog(b['t'], nar=True)
            key, name, color, side = C[b['who']]
            return build_dialog(b['t'], name=name, color=color, side=side)
        return self.get(('dlg', id(b)), mk)

    def _pop_dialog(self, fr, dl, tb, delay=0.0):
        p = ease_back((tb - delay) / .42)
        im = dl['im']
        put(fr, im, dl['x'] + im.width / 2, dl['y'] + im.height / 2 + 40 * (1 - p),
            scale=.9 + .1 * p, alpha=clamp((tb - delay) / .2))

    def _sticker(self, fr, b, tb, side):
        if not b.get('s'):
            return
        ang = {'left': -8, 'right': 8, 'center': 0}[side]
        im = self.sticker_img(b['s'], ang)
        x = {'left': 60 + 170, 'right': W - 60 - 170, 'center': W / 2}[side]
        y = 560 if side != 'center' else 640
        p = (tb - .35) / .45
        put(fr, im, x, y, scale=2.2 - 1.2 * ease_back(p), alpha=clamp(p * 2))

    def beat_line(self, fr, b, tb, c):
        dl = self._dialog(b)
        key, name, color, side = C[b['who']]
        if not b.get('noPortrait'):
            im, pad = self.portrait_img(key, b['e'] or 'happy')
            w = im.width - 2 * pad
            x = (24 + w / 2) if side == 'left' else (W - 24 - w / 2)
            bottom = dl['box_top'] + 70 + pad
            p = ease_back(tb / .48)
            put(fr, im, x, bottom + 240 * (1 - p), scale=.5 + .5 * p, alpha=clamp(tb / .2), anchor='bottom')
        self._sticker(fr, b, tb, 'right' if side == 'left' else 'left')
        self._pop_dialog(fr, dl, tb)

    def beat_nar(self, fr, b, tb, c):
        self._sticker(fr, b, tb, 'center')
        self._pop_dialog(fr, self._dialog(b), tb)

    def beat_title(self, fr, b, tb, c):
        def mk():
            cv = card(940, 560, 56, (20, 14, 14, 222))
            lock = emoji_img('🔒', 120)
            cv.alpha_composite(lock, ((940 - lock.width) // 2, 50))
            ts = Style([PF['semibold']], 60, (255, 96, 96), line_h=1.3, tracking=14).render('TOP SECRET')
            stamp = Image.new('RGBA', (ts.width + 60, ts.height + 30))
            ImageDraw.Draw(stamp).rounded_rectangle((0, 0, stamp.width - 1, stamp.height - 1), 14, outline=(255, 96, 96), width=6)
            stamp.alpha_composite(ts, (30, 15))
            big = Style([PF['semibold']], 88, (255, 255, 255), line_h=1.3).render('Sandy 生日作戰檔案')
            cv.alpha_composite(big, ((940 - big.width) // 2, 340))
            return shadowed(cv, (0, 18), 24, 130)[0], stamp.rotate(4, Image.BICUBIC, expand=True)
        cv, stamp = self.get(('title',), mk)
        p = ease_back(tb / .5)
        put(fr, cv, W / 2, 860 + 60 * (1 - p), scale=.85 + .15 * p, alpha=clamp(tb / .25))
        q = (tb - .55) / .45
        put(fr, stamp, W / 2, 800, scale=2.2 - 1.2 * ease_back(q), alpha=clamp(q * 2))

    def beat_cake(self, fr, b, tb, c):
        def mk():
            cv = card(860, 640, 56)
            cake = emoji_img('🎂', 300)
            cv.alpha_composite(cake, ((860 - cake.width) // 2, 70))
            t = Style([PF['semibold']], 50, (59, 42, 42), line_h=1.4).render('許個願，對著手機吹一口氣 🌬️', max_w=760, align='center')
            cv.alpha_composite(t, ((860 - t.width) // 2, 430))
            return shadowed(cv, (0, 18), 24, 120)[0]
        cv = self.get(('cake',), mk)
        p = ease_back((tb - .3) / .45)
        put(fr, cv, W / 2, 760, scale=.6 + .4 * p, alpha=clamp((tb - .3) / .2))
        q = (tb - 2.5) / .9
        if q > 0:
            put(fr, emoji_img('💨', 220), W / 2 + 40, 600 - 120 * ease_out(q), scale=.6 + .6 * ease_out(q), alpha=1 - clamp((q - .6) / .4))
        b2 = self.get(('cakedlg',), lambda: build_dialog(b['t'], nar=True))
        self._pop_dialog(fr, b2, tb)

    def _hb(self):
        def mk():
            fs = 150
            while Style([SNELL], fs, (0, 0, 0)).render('Happy Birthday').width > 960:
                fs -= 4
            st = Style([SNELL], fs, (255, 216, 107), line_h=1.15, stroke=0)
            t = st.render('Happy Birthday')
            sh = Style([SNELL], fs, (181, 101, 29), line_h=1.15).render('Happy Birthday')
            cv = Image.new('RGBA', (t.width + 80, t.height + 80))
            glow = Image.new('RGBA', cv.size)
            glow.alpha_composite(Style([SNELL], fs, (255, 200, 80), line_h=1.15).render('Happy Birthday'), (40, 40))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
            cv.alpha_composite(glow)
            cv.alpha_composite(sh, (40, 47))
            cv.alpha_composite(t, (40, 40))
            return cv
        return self.get(('hb',), mk)

    def _flag(self, i, ch):
        def mk():
            im = Image.new('RGBA', (112, 132))
            ImageDraw.Draw(im).polygon([(0, 0), (111, 0), (56, 131)], fill=hexrgb(COLORS[i]) + (255,))
            t = Style([PF['semibold']], 54, (255, 255, 255), line_h=1.1).render(ch)
            im.alpha_composite(t, ((112 - t.width) // 2, 4))
            return shadowed(im, (0, 6), 6, 70)[0]
        return self.get(('flag', i), mk)

    def _pol_swing(self, tb, t0):
        if tb < t0:
            return -3
        return -3 + 5 * ease_io(((tb - t0) / 3) % 2 if ((tb - t0) / 3) % 2 <= 1 else 2 - ((tb - t0) / 3) % 2)

    def beat_party(self, fr, b, tb, c):
        # 吹完的閃光
        if tb < .35:
            fr.paste(Image.blend(fr, Image.new('RGB', (W, H), (255, 250, 235)), .7 * (1 - tb / .35)))
        hb = self._hb()
        p = ease_back((tb - .2) / .6)
        put(fr, hb, W / 2, 420 - 180 * (1 - p), alpha=clamp((tb - .2) / .3))
        x0 = (W - (5 * 112 + 4 * 14)) / 2
        for i, ch in enumerate('SANDY'):
            fl = self._flag(i, ch)
            q = ease_back((tb - .35 - i * .1) / .5)
            put(fr, fl, x0 + 56 + i * 126, 600 - 180 * (1 - q), alpha=clamp((tb - .35 - i * .1) / .25))
        # 拍立得輪播（準備過程五張）
        pols = [self.get(('pol', i), lambda i=i: polaroid(self.A, SLIDES[i])) for i in range(len(SLIDES))]
        k = clamp((tb - .9) / 1.9, 0, len(SLIDES) - 1e-6)
        i0 = int(k)
        fade = clamp((k - i0 - .74) / .26)
        pol = pols[i0] if fade <= 0 or i0 + 1 >= len(pols) else Image.blend(pols[i0], pols[i0 + 1], fade)
        q = (tb - .9) / .7
        if q > 0:
            ang = (-20 + 17 * ease_back(q)) if q < 1 else self._pol_swing(tb, 2.9)
            put(fr, pol, W / 2, 1070, scale=.3 + .7 * ease_back(q), alpha=clamp(q * 2), angle=-ang)
        # 四張生日貼圖
        for s, x, y, r, dly in (('lucas/33', 150, 790, -10, 1.5), ('cheng/36', W - 150, 790, 10, 1.8),
                                ('hua/21', 140, 1300, -6, 2.1), ('sandy/37', W - 140, 1300, 8, 2.4)):
            im = self.get(('pstk', s), lambda s=s, r=r: shadowed(self.A.sticker(s).resize((270, 270), Image.LANCZOS), (0, 12), 14, 100)[0].rotate(-r, Image.BICUBIC, expand=True))
            q = (tb - dly) / .45
            bob = 0 if tb < 2.9 else -21 * ease_io(((tb - 2.9) / 1.6) % 2 if ((tb - 2.9) / 1.6) % 2 <= 1 else 2 - ((tb - 2.9) / 1.6) % 2)
            put(fr, im, x, y + bob, scale=2.2 - 1.2 * ease_back(q), alpha=clamp(q * 2))
        dl = self.get(('partydlg',), lambda: build_dialog(b['t'], name='老公・丞丞・小花', color='#e2667f', side='left'))
        self._pop_dialog(fr, dl, tb, delay=1.2)

    def beat_ending(self, fr, b, tb, c):
        pol = self.get(('family',), lambda: polaroid(self.A, FAMILY, pw=800))
        q = (tb - .2) / .7
        if q > 0:
            ang = (-20 + 17 * ease_back(q)) if q < 1 else self._pol_swing(tb, 1.6) * .6 - 1.2
            put(fr, pol, W / 2, 760, scale=.3 + .7 * ease_back(q), alpha=clamp(q * 2), angle=-ang)
        def mk():
            a = Style([PF['semibold']], 104, (255, 255, 255), line_h=1.25, stroke=7, stroke_fill=(226, 102, 127)).render('Sandy 生日快樂')
            d = Style([PF['semibold']], 64, (255, 216, 107), line_h=1.25, tracking=6, stroke=4, stroke_fill=(90, 50, 20)).render('2026.10.17')
            e = Style([PF['medium']], 58, (255, 255, 255), line_h=1.3, stroke=4, stroke_fill=(60, 30, 30)).render('愛妳的 老公、丞丞、小花')
            return [shadowed(x, (0, 8), 12, 120)[0] for x in (a, d, e)]
        texts = self.get(('endtxt',), mk)
        for (im, y, dly) in zip(texts, (1370, 1510, 1625), (1.0, 1.6, 2.2)):
            r = ease_out((tb - dly) / .7)
            put(fr, im, W / 2, y + 50 * (1 - r), alpha=clamp((tb - dly) / .5))

    def beat_anim(self, fr, b, tb, c):
        a = clamp(tb / .4) * clamp((b['dur'] - tb) / .4)
        fr.paste(Image.blend(fr, self.dark, .55 * a))
        hd = self.get(('animhd',), lambda: pill('🎬 丞丞的動畫', Style([PF['semibold']], 50, (59, 42, 42), line_h=1.25), (255, 255, 255, 240), 40, 18))
        put(fr, hd, W / 2, 420, alpha=clamp(tb / .3))
        vf = self.anim.frame(tb)
        if vf is None:
            return
        bw = 18
        box = Image.new('RGBA', (vf.width + 2 * bw, vf.height + 2 * bw))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), 30, fill=(255, 255, 255, 255))
        box.paste(vf, (bw, bw), rounded_mask(vf.size, 14))
        p = ease_back(tb / .45)
        fade_tail = clamp((b['dur'] - tb) / .5) if self.anim.trimmed else 1
        put(fr, box, W / 2, ANIM_CY, scale=.9 + .1 * p, alpha=clamp(tb / .25) * fade_tail)

ANIM_BOX = (980, 1140)
ANIM_CY = 1060

# ---------------------------------------------------------------- 丞丞動畫
def ffprobe_json(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                          'stream=index,codec_type,codec_name,width,height,pix_fmt,profile,duration,sample_rate,channels:format=duration,size',
                          '-of', 'json', path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)

class Anim:
    def __init__(self, path, max_dur, tmp):
        info = ffprobe_json(path)
        self.path = path
        self.src_dur = float(info['format']['duration'])
        self.has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])
        self.dur = min(self.src_dur, max_dur)
        self.trimmed = self.src_dur > max_dur + .05
        vf = f'scale={ANIM_BOX[0]}:{ANIM_BOX[1]}:force_original_aspect_ratio=decrease:flags=lanczos,setsar=1'
        first = os.path.join(tmp, 'anim-first.png')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', vf, '-frames:v', '1', first], check=True)
        self.size = Image.open(first).size
        self.proc = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-t', f'{self.dur:.3f}',
                                      '-vf', vf + f',fps={FPS}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                     stdout=subprocess.PIPE)
        self.n = -1
        self.last = None

    def frame(self, tb):
        want = int(tb * FPS + 1e-6)
        nbytes = self.size[0] * self.size[1] * 3
        while self.n < want:
            buf = self.proc.stdout.read(nbytes) if self.proc else b''
            if len(buf) < nbytes:
                break   # 讀完就停在最後一格
            self.last = Image.frombytes('RGB', self.size, buf)
            self.n += 1
        return self.last

    def close(self):
        if self.proc:
            if self.proc.poll() is None:   # 預覽時沒讀完：直接結束解碼程序
                self.proc.terminate()
            self.proc.stdout.close()
            self.proc.wait()

# ---------------------------------------------------------------- 音樂（mockup playSong 同旋律、同音色）
NOTE = {'G4': 392, 'A4': 440, 'B4': 493.9, 'C5': 523.3, 'D5': 587.3, 'E5': 659.3, 'F5': 698.5, 'G5': 784}
TUNE = [('G4', .75), ('G4', .25), ('A4', 1), ('G4', 1), ('C5', 1), ('B4', 2), ('G4', .75), ('G4', .25), ('A4', 1), ('G4', 1), ('D5', 1), ('C5', 2),
        ('G4', .75), ('G4', .25), ('G5', 1), ('E5', 1), ('C5', 1), ('B4', 1), ('A4', 2), ('F5', .75), ('F5', .25), ('E5', 1), ('C5', 1), ('D5', 1), ('C5', 2.5)]
BEAT = .42
SR = 44100

def synth_music(total, path, start=.5, gap=1.4, fade=3.5):
    song_len = sum(d for _, d in TUNE) * BEAT
    one = array('f', bytes(4 * int((song_len + 1.2) * SR)))
    t = 0.0
    for n, d in TUNE:
        for mul, peak in ((1, .18), (2, .05)):   # 基音＋八度泛音，像音樂盒
            f = NOTE[n] * mul
            T, stop = d * BEAT + .6, d * BEAT + .7
            k = math.log(.0005 / peak) / (T - .01)
            w = 2 * math.pi * f / SR
            n0 = int(t * SR)
            for i in range(int(stop * SR)):
                tt = i / SR
                g = peak * tt / .01 if tt < .01 else peak * math.exp(k * (tt - .01))
                one[n0 + i] += g * math.sin(w * i)
        t += d * BEAT
    dl = int(.19 * SR)   # 一點回音，音樂盒的空間感
    for i in range(len(one) - 1, dl - 1, -1):
        one[i] += .25 * one[i - dl]
    N = int(total * SR)
    out = array('f', bytes(4 * N))
    s = start
    while s < total - 2:
        o = int(s * SR)
        for i in range(min(len(one), N - o)):
            out[o + i] += one[i]
        s += song_len + gap
    peak = max(max(out), -min(out)) or 1
    g = .55 / peak
    fs, ffade = int((total - fade) * SR), int(fade * SR)
    pcm = array('h', bytes(2 * N))
    for i in range(N):
        v = out[i] * g
        if i > fs:
            v *= max(0.0, 1 - (i - fs) / ffade)
        pcm[i] = int(v * 32767)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())

# ---------------------------------------------------------------- 驗證
def atom_order(path):
    order = []
    with open(path, 'rb') as f:
        while True:
            hdr = f.read(8)
            if len(hdr) < 8:
                break
            size = int.from_bytes(hdr[:4], 'big')
            typ = hdr[4:8].decode('latin1')
            if size == 1:
                size = int.from_bytes(f.read(8), 'big')
                f.seek(size - 16, 1)
            else:
                f.seek(size - 8, 1)
            order.append(typ)
            if size == 0:
                break
    return order

def check(path):
    info = ffprobe_json(path)
    v = next(s for s in info['streams'] if s['codec_type'] == 'video')
    a = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
    dur = float(info['format']['duration'])
    size = int(info['format']['size'])
    order = [x for x in atom_order(path) if x in ('moov', 'mdat')]
    res = {
        'video': f"{v['codec_name']} {v.get('profile')} {v['pix_fmt']} {v['width']}x{v['height']}",
        'audio': f"{a['codec_name']} {a.get('sample_rate')}Hz ch{a.get('channels')}" if a else None,
        'duration': round(dur, 2), 'size_MB': round(size / 1e6, 2), 'atoms': order,
    }
    ok = (v['codec_name'] == 'h264' and v['pix_fmt'] == 'yuv420p' and v.get('profile') == 'High'
          and (v['width'], v['height']) == (W, H) and a and a['codec_name'] == 'aac'
          and 60 <= dur <= 90 and size <= 40e6 and order[:1] == ['moov'])
    res['A4'] = 'PASS' if ok else 'FAIL'
    return res

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description='產 Sandy 生日回顧影片')
    ap.add_argument('--assets', default=os.path.join(PROJ, 'assets'), help='素材根目錄（portraits/round2/stickers）')
    ap.add_argument('--media', default=os.path.join(SITE, 'media'), help='找 cheng-animation.mp4 的目錄')
    ap.add_argument('--out', default=os.path.join(SITE, 'media', 'sandy-birthday-recap.mp4'))
    ap.add_argument('--tmp', default=os.path.join(PROJ, 'tmp-video'))
    ap.add_argument('--anim-max', type=float, default=None, help='動畫最長秒數（預設：讓總長 ≤ 89.5 秒）')
    ap.add_argument('--no-anim', action='store_true', help='忽略 cheng-animation.mp4')
    ap.add_argument('--preview', help='只出單格 PNG：逗號分隔的秒數')
    ap.add_argument('--snapshots', action='store_true', help='產完後抽 6 格存 evidence/video-*.png')
    ap.add_argument('--crf', type=int, default=20)
    args = ap.parse_args()
    os.makedirs(args.tmp, exist_ok=True)
    A = Assets(args.assets)

    anim = None
    anim_path = os.path.join(args.media, 'cheng-animation.mp4')
    base = sum(b['dur'] for c in build_script(1.0) for b in c['beats']) - 1.0
    if os.path.exists(anim_path) and not args.no_anim:
        max_d = args.anim_max if args.anim_max else 89.5 - base
        anim = Anim(anim_path, max_d, args.tmp)
        msg = f'插入丞丞動畫：{anim_path}（原長 {anim.src_dur:.1f}s，用 {anim.dur:.1f}s'
        print(msg + ('，超過長度上限已截短淡出）' if anim.trimmed else '）'))
    chapters = build_script(anim.dur if anim else 0)
    R = Renderer(A, chapters, anim)
    print(f'總長 {R.total:.1f}s，{len(chapters)} 段')

    if args.preview:
        pdir = os.path.join(args.tmp, 'preview')
        os.makedirs(pdir, exist_ok=True)
        for s in args.preview.split(','):
            t = float(s)
            p = os.path.join(pdir, f'f-{t:06.2f}.png')
            R.frame(t).save(p)
            print(p)
        if anim:
            anim.close()
        return

    wav = os.path.join(args.tmp, 'music.wav')
    t0 = time.time()
    synth_music(R.total, wav)
    print(f'音樂合成 {time.time() - t0:.1f}s')

    tmp_out = os.path.join(args.tmp, 'recap-build.mp4')
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', wav]
    if anim and anim.has_audio:
        ac = next(c for c in chapters if c['key'] == 'ch5')
        ab = next(b for b in ac['beats'] if b['kind'] == 'anim')
        s = ac['start'] + ab['start']
        e = s + ab['dur']
        cmd += ['-i', anim.path]
        duck = f"volume='1-0.8*clip((t-{s - .5:.3f})/0.5,0,1)*clip(({e + .5:.3f}-t)/0.5,0,1)':eval=frame"
        fc = (f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,{duck}[m];"
              f"[2:a]atrim=0:{anim.dur:.3f},asetpts=PTS-STARTPTS,aresample=44100,aformat=sample_rates=44100:channel_layouts=stereo,"
              f"afade=t=in:d=0.2,afade=t=out:st={max(0, anim.dur - .5):.3f}:d=0.5,adelay={int(s * 1000)}:all=1[v];"
              f"[m][v]amix=inputs=2:duration=first:normalize=0[a]")
        cmd += ['-filter_complex', fc, '-map', '0:v', '-map', '[a]']
    else:
        cmd += ['-map', '0:v', '-map', '1:a', '-af', 'aformat=sample_rates=44100:channel_layouts=stereo']
    cmd += ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
            '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'medium', '-crf', str(args.crf),
            '-maxrate', '3000k', '-bufsize', '6000k', '-g', str(FPS * 2),
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
            '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', '-t', f'{R.total:.3f}', tmp_out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = round(R.total * FPS)
    t0 = time.time()
    for i in range(n):
        enc.stdin.write(R.frame(i / FPS).tobytes())
        if i % (FPS * 5) == 0:
            el = time.time() - t0
            print(f'  {i}/{n} 格  {el:.0f}s  預估剩 {el / max(1, i) * (n - i):.0f}s', flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit('ffmpeg 編碼失敗')
    if anim:
        anim.close()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    shutil.move(tmp_out, args.out)
    print(f'完成 {args.out}（算圖 {time.time() - t0:.0f}s）')
    res = check(args.out)
    print(json.dumps(res, ensure_ascii=False))

    if args.snapshots:
        ev = os.path.join(PROJ, 'evidence')
        os.makedirs(ev, exist_ok=True)
        # 六格：每格挑該句字幕已完整出現的時刻（涵蓋四位角色、機車三貼、派對、結尾）
        want = [('open', 1), ('ch1', 1), ('ch3', 1), ('ch4', 0), ('ch6', 1), ('end', 0)]
        picks = []
        for k, bi in want:
            c = next(c for c in chapters if c['key'] == k)
            b = c['beats'][bi]
            hold = {'party': 6.0, 'ending': 4.5}.get(b['kind'], 2.6)
            picks.append((k, b['kind'], c['start'] + b['start'] + min(b['dur'] - .5, hold)))
        for i, (k, kind, t) in enumerate(picks, 1):
            p = os.path.join(ev, f'video-{i}-{k}-{kind}.png')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', args.out, '-frames:v', '1', p], check=True)
            print(p)

if __name__ == '__main__':
    main()
