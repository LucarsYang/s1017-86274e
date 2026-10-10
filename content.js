// Sandy 生日網站：可改的設定都在這個檔（檔名、台詞）。程式邏輯在 app.js，不用動。
// 改台詞：直接改下面 t:'…' 的字；<br> 是換行。改完存檔、重新整理即可。

window.CONTENT = {
  // ── 補檔位（丟進 site/media/ 後跑 `python3 tools/update_media.py`）──
  media: {
    chengAnimation: 'cheng-animation.mp4',      // 丞丞的動畫
    huaLetterPrefix: 'hua-letter-',             // 小花的信：hua-letter-1.jpg、hua-letter-2.jpg…（可多張，照數字排序）
    recap: 'sandy-birthday-recap.mp4',          // 回顧影片（保存按鈕用）
  },

  // ── 畫面文字 ──
  ui: {
    start: '點一下開始',
    startSub: '建議打開聲音 🔊',
    skip: '跳過 ›',
    rotate: '📱 請把手機轉回直式',
    giftPlaceholder: '🎁 今晚揭曉',
    save: '💾 保存回顧影片',
    saveHint: 'iPhone：按下後選「儲存影片」就會存進相簿',
    savePreparing: '影片準備中…',
    saveReady: '💾 好了，再點一下保存',
    saveLongPress: '長按影片 → 儲存',
  },

  // 角色
  chars: {
    dad:   { key:'lucas', name:'老公',  color:'#4a7bd0', side:'left'  },
    sandy: { key:'sandy', name:'Sandy', color:'#e2667f', side:'right' },
    cheng: { key:'cheng', name:'丞丞',  color:'#3d9a5f', side:'right' },
    hua:   { key:'hua',   name:'小花',  color:'#e0a020', side:'left'  },
  },
  // 身高（丞丞 > 老公 > Sandy = 小花），單位＝設計格（草稿 px）
  height: { cheng:192, lucas:184, sandy:174, hua:174 },

  // ── 劇本 ──
  // w：誰說（dad/sandy/cheng/hua/nar 旁白/party 派對）；e：表情（happy/surprised/thinking/laugh/front）
  // s：蓋章的 LINE 貼圖（assets/stickers/{人}/{號}.webp）；chip：左上日期標籤
  // act：互動卡種類（程式處理），其餘欄位是卡上的字
  scenes: [
    { bg:'bg0-mystery', loc:'📍 ？？？・機密檔案室',
      lines:[
        { w:'nar', t:'TOP SECRET<br><b class="big">Sandy 生日作戰檔案</b>' },
        { w:'dad', e:'happy', t:'Sandy，這份檔案記錄了我們三個這一個月偷偷在做的事。' },
        { w:'cheng', e:'happy', t:'要先解鎖才能看喔！' },
        { act:'password', code:'1017', title:'輸入密碼', hint:'提示：今天是什麼日子？',
          wrong:{ w:'hua', e:'surprised', t:'媽媽！是妳的大日子啦！' } },
      ] },

    { bg:'bg1-home-desk', loc:'📍 家裡餐桌・秘密會議室',
      lines:[
        { w:'nar', t:'9/17 晚上，趁媽媽不注意……', chip:'9/17 晚上' },
        { w:'cheng', e:'thinking', t:'媽媽生日快到了，要送什麼？' },
        { w:'hua', e:'thinking', t:'嗯……我也不知道。', s:'hua/18' },
        { w:'dad', e:'thinking', t:'那……下次再想。', s:'lucas/11' },
        { w:'nar', t:'9/26 晚上，第二次秘密會議', chip:'9/26 晚上' },
        { w:'dad', e:'laugh', t:'這次一定要想出來！' },
        { w:'nar', t:'（安靜了五分鐘）' },
        { w:'cheng', e:'surprised', t:'……我先去洗澡。', s:'cheng/25' },
        { act:'bulbOff', title:'點子數：0', before:'點燈泡——', after:'閃了一下……又熄了。' },
        { w:'nar', t:'10/3 晚上，第三次。這次不一樣。', chip:'10/3 晚上' },
        { w:'hua', e:'happy', t:'我知道了！！帶媽媽去吃大餐！！' },
        { act:'bulbOn', title:'點子數：1！', text:'燈泡終於亮了！' },
        { w:'dad', e:'laugh', t:'好！那就去附近的餐廳！' },
        { w:'cheng', e:'happy', t:'附議！！', s:'cheng/08' },
        { act:'vote', title:'📋 家庭會議表決', lines:['提案：帶媽媽吃大餐','地點：附近的餐廳'], yes:3, no:0, note:'（媽媽：不知情）', gavel:'🔨 咚！通過！' },
        { w:'nar', t:'史上最快通過的家庭提案：3 秒。' },
        { w:'hua', e:'thinking', t:'……爸，那「附近的餐廳」是哪一家？' },
        { w:'dad', e:'surprised', t:'…………', s:'lucas/14' },
      ] },

    { bg:'bg2-gulajazz', loc:'📍 愛買 3F・古拉爵', chip:'10/9 中午',
      lines:[
        { w:'nar', t:'10/9 中午，愛買 3F 古拉爵。<br>爸爸、媽媽、小花三個人吃午餐。' },
        { w:'sandy', e:'happy', t:'這家義大利麵好好吃～', s:'sandy/05' },
        { w:'hua', e:'happy', t:'（小聲）爸，餐廳到底訂了沒？' },
        { w:'dad', e:'happy', t:'（小聲）看我的。' },
        { w:'dad', e:'surprised', t:'啊！！糟糕！說好要吃大餐……我、我忘記訂餐廳了！！', s:'lucas/03' },
        { w:'nar', t:'——以上，為爸爸的演技。' },
        { w:'sandy', e:'thinking', t:'蛤～那……吃鐵板燒好了？' },
        { act:'target', title:'命中目標！', text:'Sandy 選擇了：<b>鐵板燒</b>' },
        { w:'dad', e:'happy', t:'鐵板燒！好啊好啊！我馬上找！', s:'lucas/41' },
        { act:'search', query:'板橋　鐵板燒', result:'📍 <b>明水然．樂</b>（板橋重慶）<br>✅ 訂位完成：10/17 晚上 4 位' },
        { w:'nar', t:'Sandy，妳親手選了自己的生日大餐，<br>而且完全沒發現 😎', s:'sandy/12' },
      ] },

    { anim:'scooter', bg:'bg3-street', loc:'📍 板橋街頭・機車移動會議室', chip:'10/10 早上', noPortrait:true,
      lines:[
        { w:'nar', t:'10/10 早上，三名特務騎機車出動。' },
        { w:'dad', t:'機車會議開始！每個人都要準備一份禮物給媽媽。' },
        { w:'cheng', t:'我已經想好了，但是……是秘密。' },
        { w:'hua', t:'我也是！不能說！' },
        { w:'nar', t:'Sandy，換妳猜猜看——<br>他們三個各準備了什麼？' },
        // 選項：[文字, 是否正確, 回話表情, 回話]
        { quiz:'dad', q:'老公準備了什麼？', opts:[
          ['苦練一個月的生日快樂舞', false, 'surprised', '這個……明年再說 😅'],
          ['把床單洗得特別香', false, 'surprised', '那是被派的任務！不算禮物啦！'],
          ['做一個網站', true, 'laugh', '答對！妳現在看的就是 😎'],
          ['包下 101 放煙火', false, 'thinking', '錢包表示：不行。'] ] },
        { quiz:'cheng', q:'丞丞準備了什麼？', opts:[
          ['把房間整理乾淨', false, 'surprised', '媽媽，這個太難了啦！'],
          ['做一段動畫', true, 'laugh', '答對！今晚播給妳看！'],
          ['自己寫完作業不用催', false, 'thinking', '……這是什麼神奇的願望？'],
          ['用零用錢買鑽石', false, 'surprised', '我的零用錢只夠買一顆糖果。'] ] },
        { quiz:'hua', q:'小花準備了什麼？', opts:[
          ['請恐龍來唱生日快樂歌', false, 'thinking', '恐龍在忙。'],
          ['一整天不跟哥哥吵架', false, 'thinking', '……做不到。'],
          ['綁一個超完美的馬尾', false, 'surprised', '我每天都很完美啊！'],
          ['寫一封信', true, 'laugh', '答對！晚上才可以拆喔 💌'] ] },
        { w:'nar', t:'任務分配完成。<br>三名特務，各自開工！' },
      ] },

    { bg:'bg4-home-sofa', loc:'📍 家裡客廳・網站開工現場', chip:'10/10 中午',
      lines:[
        { w:'dad', e:'laugh', t:'好，網站開工！' },
        { act:'progress', title:'網站製作進度', from:0, to:3 },
        { w:'sandy', e:'happy', t:'老公～床單拿去洗一下！' },
        { w:'dad', e:'surprised', t:'……好 🙇', s:'lucas/09' },
        { w:'sandy', e:'thinking', t:'還有，學生交回來的問卷幫我拍一下，研究報告要用。' },
        { w:'dad', e:'surprised', t:'馬上去 🏃（網站進度：還是 3%）', s:'lucas/16' },
        { w:'cheng', e:'happy', t:'（小聲）爸，你的網站……' },
        { w:'dad', e:'surprised', t:'噓！！！' },
        { w:'nar', t:'派這些任務的人……就是妳本人 😆', s:'sandy/20' },
        { act:'progress', title:'經過一個禮拜的深夜趕工……', from:3, to:100, done:' 🎉' },
      ] },

    { bg:'bg5-mingshuiran', loc:'📍 板橋重慶・明水然．樂', chip:'10/17 今晚',
      lines:[
        { w:'nar', t:'10/17 晚上，明水然．樂。<br>也就是——妳自己選的那間 😎' },
        { w:'cheng', e:'happy', t:'媽媽，這是我做的動畫！', s:'cheng/11' },
        { act:'giftVideo', title:'🎬 丞丞的動畫' },
        { w:'hua', e:'happy', t:'這是我寫給妳的信 💌', s:'hua/21' },
        { act:'giftLetter', title:'小花的信', text:'點信封打開' },
        { w:'dad', e:'laugh', t:'妳現在看的這個網站，就是我的禮物。', s:'lucas/10' },
      ] },

    { bg:'bg5-mingshuiran', dim:true, loc:'📍 板橋重慶・明水然．樂', chip:'10/17 今晚',
      lines:[
        { w:'nar', t:'最後一個任務，要由 Sandy 親自完成——' },
        { act:'candle', blow:'許個願，對著手機吹一口氣 🌬️', blowSub:'（或按住蛋糕 2 秒）', hold:'許個願，按住蛋糕 2 秒 🎂' },
        { w:'party', name:'老公・丞丞・小花', t:'🎉 Sandy，生日快樂！<br>愛妳的 老公、丞丞、小花' },
      ] },
  ],

  // 派對拍立得輪播
  slides: [
    { cap:'2026.10.17　我們家 ♥', family:true },
    { cap:'9/17～10/3　秘密會議', bg:'bg1-home-desk', who:'hua-happy' },
    { cap:'10/9　爸爸的演技', bg:'bg2-gulajazz', who:'lucas-surprised' },
    { cap:'10/10　機車三貼', bg:'bg3-street', scooter:true },
    { cap:'10/10　進度 3%', bg:'bg4-home-sofa', who:'lucas-thinking' },
    { cap:'10/17　妳選的鐵板燒', bg:'bg5-mingshuiran', who:'sandy-laugh' },
  ],
};
