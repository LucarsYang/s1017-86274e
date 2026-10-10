#!/bin/zsh
# 從工作區 assets/ 產生網站用 WebP（背景長邊 ≤1600、立繪 ≤600、貼圖原尺寸）。
# 用法：zsh tools/build_assets.sh   （在 site/ 底下跑）
set -e
cd "${0:A:h}/.."
SRC=../assets
mkdir -p assets/bg assets/portraits assets/stickers
for f in $SRC/round2/2026-10-10-bg*.png; do
  n=${${f:t:r}#2026-10-10-}
  cwebp -quiet -q 80 -resize 0 0 "$f" -o assets/bg/$n.webp
done
for who in lucas sandy cheng hua; do
  for e in happy surprised thinking laugh front; do
    cwebp -quiet -q 85 -alpha_q 90 "$SRC/portraits/$who-$e.png" -o assets/portraits/$who-$e.webp
  done
done
# 機車三貼（1033×956）縮到長邊 600
cwebp -quiet -q 85 -alpha_q 90 -resize 600 0 "$SRC/portraits/scooter-trio.png" -o assets/portraits/scooter-trio.webp
stickers=(lucas/03 lucas/09 lucas/10 lucas/11 lucas/14 lucas/16 lucas/41 lucas/33
          sandy/05 sandy/12 sandy/20 sandy/37
          cheng/08 cheng/11 cheng/25 cheng/36
          hua/18 hua/21)
for s in $stickers; do
  mkdir -p assets/stickers/${s:h}
  cwebp -quiet -q 85 -alpha_q 90 "$SRC/stickers/$s.png" -o assets/stickers/$s.webp
done
du -sh assets
