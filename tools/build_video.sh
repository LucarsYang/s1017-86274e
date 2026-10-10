#!/bin/sh
# 一鍵重產 Sandy 生日回顧影片 → site/media/sandy-birthday-recap.mp4
# media/cheng-animation.mp4 在就自動插進「今晚」段。參數照傳給 build_video.py（--help 看全部）。
exec python3 "$(dirname "$0")/build_video.py" "$@"
