"""웹 대시보드 HTML (minutes.server 가 GET / 에 서빙).

단일 파일(인라인 CSS/JS, 외부 CDN 없음 → 오프라인/air-gapped 동작).
토스(Toss) 앱인토스 UI/UX 가이드 반영:
 - UX 라이팅: 해요체 · 능동형 · 긍정형 문장(빈 상태도 "쌓여요"처럼 앞을 보게).
 - 다크·라이트 모드 모두 대응(prefers-color-scheme), 브랜드 컬러 #3182F6.
 - 장식 최소화, 정확한 상태 표현(오류가 아닌 곳에 경고 아이콘 안 씀).
 - 흉내(mock)↔실제 모드 토글: 사이드바 스위치가 POST /mode 로 전환(프로세스 한정).
회의록은 마크다운, 녹취는 화자 말풍선으로 렌더한다.
"""

# 원시 문자열(r""")로 두어 JS 정규식의 백슬래시가 파이썬에 먹히지 않게 한다.
INDEX_HTML = r"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>회의록 봇 대시보드</title>
<style>
 :root{
  --bg:#f2f4f6; --card:#fff; --text:#191f28; --sub:#8b95a1; --line:#e9ecef;
  --fill:#f4f6f8; --fill-2:#eef1f4; --fill-2h:#e5e9ee; --input:#fbfcfd;
  --pri:#3182f6; --pri-d:#1b64da; --pri-soft:#e8f3ff; --pri-line:#cfe1ff; --pri-tint:#f6fbff;
  --ok:#12b886; --ok-soft:#e9fbf3; --danger:#f04452; --danger-soft:#fff5f5; --danger-line:#ffd6d9;
  --warn:#d9860b; --warn-soft:#fff4e2; --warn-line:#ffe0ad; --track:#ccd1d8;
  --gray-t:#4e5968; --toast-bg:#191f28; --toast-t:#fff; --skel1:#eef1f4; --skel2:#f7f9fb;
  --r:18px; --sh:0 1px 2px rgba(0,0,0,.04),0 6px 20px rgba(0,0,0,.05);
 }
 @media (prefers-color-scheme:dark){:root{
  --bg:#161719; --card:#1f2125; --text:#e9ecef; --sub:#8d949e; --line:#2c2f35;
  --fill:#26282e; --fill-2:#2b2e35; --fill-2h:#343841; --input:#25272c;
  --pri:#4d94ff; --pri-d:#3f88f5; --pri-soft:#1b2b45; --pri-line:#33507e; --pri-tint:#1b222e;
  --ok:#2fce9b; --ok-soft:#173a30; --danger:#ff6b74; --danger-soft:#381e21; --danger-line:#5a2b30;
  --warn:#f5a623; --warn-soft:#3a2e14; --warn-line:#5c4820; --track:#41454d;
  --gray-t:#c4ccd4; --toast-bg:#f1f3f5; --toast-t:#191f28; --skel1:#26282e; --skel2:#2e3137;
  --sh:0 1px 2px rgba(0,0,0,.3),0 6px 22px rgba(0,0,0,.38);
 }}
 *{box-sizing:border-box} html,body{margin:0}
 body{font-family:"Pretendard",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;
  background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;letter-spacing:-.01em}
 .layout{display:flex;min-height:100vh}
 /* sidebar */
 .side{width:250px;flex-shrink:0;background:var(--card);border-right:1px solid var(--line);
  padding:22px 16px;display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
 .brand{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;padding:6px 10px 18px}
 .brand .logo{width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#3182f6,#1b64da);
  display:grid;place-items:center;color:#fff;font-size:16px}
 .moderow{display:flex;align-items:center;justify-content:space-between;margin:2px 8px 10px;
  padding:9px 11px;border-radius:11px;background:var(--fill);font-size:13px;font-weight:700;color:var(--text)}
 .moderow .sub{font-size:11px;font-weight:500;color:var(--sub)}
 .sw{position:relative;display:inline-block;width:40px;height:23px;flex-shrink:0}
 .sw input{opacity:0;width:0;height:0}
 .sw .sl{position:absolute;inset:0;background:var(--track);border-radius:99px;transition:.2s;cursor:pointer}
 .sw .sl::before{content:"";position:absolute;height:17px;width:17px;left:3px;top:3px;background:#fff;
  border-radius:50%;transition:.2s;box-shadow:0 1px 3px rgba(0,0,0,.25)}
 .sw input:checked+.sl{background:var(--warn)}
 .sw input:checked+.sl::before{transform:translateX(17px)}
 .modebadge{display:none;margin:0 8px 14px;padding:9px 11px;border-radius:11px;font-size:12px;font-weight:700;
  background:var(--warn-soft);color:var(--warn);border:1px solid var(--warn-line);line-height:1.4;cursor:help}
 .modebadge.on{display:block}
 .nav{display:flex;flex-direction:column;gap:4px}
 .nav button{display:flex;align-items:center;gap:11px;width:100%;border:0;background:transparent;
  color:var(--sub);font:inherit;font-weight:600;font-size:14.5px;padding:12px 12px;border-radius:12px;
  cursor:pointer;transition:.15s;text-align:left}
 .nav button:hover{background:var(--fill);color:var(--text)}
 .nav button.on{background:var(--pri-soft);color:var(--pri)}
 .nav button .ic{width:20px;text-align:center;font-size:16px}
 .nav .badge{margin-left:auto;background:var(--fill-2);color:var(--sub);font-size:11px;font-weight:700;
  padding:2px 8px;border-radius:99px;min-width:20px;text-align:center}
 .nav button.on .badge{background:var(--card);color:var(--pri)}
 .side .foot{margin-top:auto;display:flex;align-items:center;gap:8px;font-size:12.5px;color:var(--sub);padding:10px}
 .dot{width:8px;height:8px;border-radius:50%;background:#ced4da;transition:.2s}
 .dot.ok{background:var(--ok);box-shadow:0 0 0 4px rgba(18,184,134,.15)}
 .dot.bad{background:var(--danger);box-shadow:0 0 0 4px rgba(240,68,82,.12)}
 /* main */
 main{flex:1;min-width:0;padding:34px 44px;max-width:1040px}
 .head{margin-bottom:22px}
 .head h1{font-size:24px;font-weight:800;margin:0}
 .head p{margin:6px 0 0;color:var(--sub);font-size:14px}
 .view{display:none;animation:fade .3s ease} .view.on{display:block}
 @keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
 .card{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);padding:24px;margin-bottom:16px}
 .card h3{margin:0 0 4px;font-size:16px} .card .desc{color:var(--sub);font-size:13.5px;margin:0 0 16px}
 .field{display:flex;gap:10px;flex-wrap:wrap}
 .input,.select{flex:1;min-width:180px;padding:14px 16px;border:1.5px solid var(--line);border-radius:13px;
  font:inherit;font-size:15px;background:var(--input);transition:.15s;color:var(--text)}
 .input:focus,.select:focus{outline:0;border-color:var(--pri);background:var(--card);box-shadow:0 0 0 4px var(--pri-soft)}
 .btn{padding:14px 20px;border:0;border-radius:13px;font:inherit;font-weight:700;font-size:15px;cursor:pointer;
  transition:.13s;display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
 .btn:active{transform:scale(.97)} .btn[disabled]{opacity:.6;cursor:default}
 .btn.pri{background:var(--pri);color:#fff} .btn.pri:hover{background:var(--pri-d)}
 .btn.gray{background:var(--fill-2);color:var(--gray-t)} .btn.gray:hover{background:var(--fill-2h)}
 .btn.sm{padding:9px 14px;font-size:13.5px;border-radius:10px}
 .spin{width:15px;height:15px;border:2.5px solid rgba(255,255,255,.45);border-top-color:#fff;border-radius:50%;
  animation:sp .7s linear infinite;display:inline-block}
 .btn.gray .spin{border-color:rgba(125,125,125,.3);border-top-color:var(--gray-t)}
 @keyframes sp{to{transform:rotate(360deg)}}
 .result{margin-top:16px;display:none;align-items:center;gap:12px;background:var(--pri-tint);
  border:1px solid var(--pri-line);border-radius:14px;padding:16px}
 .result.show{display:flex} .result.err{background:var(--danger-soft);border-color:var(--danger-line)}
 .chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:5px 11px;
  border-radius:99px;background:var(--pri-soft);color:var(--pri)}
 .chip.g{background:var(--ok-soft);color:var(--ok)} .chip.r{background:var(--danger-soft);color:var(--danger)}
 .chip.w{background:var(--warn-soft);color:var(--warn)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
 .stat{background:var(--card);border-radius:16px;box-shadow:var(--sh);padding:20px}
 .stat .k{color:var(--sub);font-size:13px;margin-bottom:8px} .stat .v{font-size:26px;font-weight:800}
 /* file list */
 .flist{display:flex;flex-direction:column;gap:8px}
 .fitem{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:14px 16px;cursor:pointer;transition:.13s}
 .fitem:hover{border-color:var(--pri-line);box-shadow:var(--sh);transform:translateY(-1px)}
 .fitem.sel{border-color:var(--pri);background:var(--pri-tint)}
 .fitem .fic{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;font-size:17px;flex-shrink:0}
 .fitem .fname{font-weight:700;font-size:14.5px} .fitem .fmeta{color:var(--sub);font-size:12px;margin-top:2px}
 .iconbtn{flex-shrink:0;border:0;background:transparent;color:var(--sub);cursor:pointer;font-size:15px;
  width:30px;height:30px;border-radius:8px;transition:.12s;opacity:.55}
 .fitem:hover .iconbtn{opacity:1} .iconbtn:hover{background:var(--fill-2);color:var(--text)}
 .iconbtn.del:hover{background:var(--danger-soft);color:var(--danger)}
 .split{display:grid;grid-template-columns:340px 1fr;gap:18px}
 @media(max-width:820px){.split{grid-template-columns:1fr}}
 .viewer{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);padding:26px 28px;min-height:300px}
 .empty{color:var(--sub);text-align:center;padding:60px 20px;font-size:14px;line-height:1.6}
 .empty .big{font-size:38px;margin-bottom:10px;opacity:.55}
 .skel{height:16px;border-radius:8px;background:linear-gradient(90deg,var(--skel1),var(--skel2),var(--skel1));
  background-size:200% 100%;animation:sh 1.2s infinite;margin:10px 0}
 @keyframes sh{to{background-position:-200% 0}}
 /* markdown */
 .md h1{font-size:22px;margin:.2em 0 .6em} .md h2{font-size:17px;margin:1.4em 0 .5em;padding-bottom:6px;border-bottom:1px solid var(--line)}
 .md h3{font-size:15px;margin:1.1em 0 .3em;color:var(--sub)}
 .md p{margin:.4em 0;line-height:1.7} .md ul,.md ol{margin:.4em 0;padding-left:22px;line-height:1.8}
 .md li::marker{color:var(--pri)} .md em{color:var(--sub);font-style:normal;font-size:13px}
 .md hr{border:0;border-top:1px solid var(--line);margin:1.2em 0}
 .md code{background:var(--fill);padding:2px 6px;border-radius:6px;font-size:13px}
 .md table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:14px}
 .md th{background:var(--fill);text-align:left} .md th,.md td{border:1px solid var(--line);padding:9px 12px}
 /* transcript chat */
 .chat{display:flex;flex-direction:column;gap:14px}
 .bubble{display:flex;gap:11px}
 .avatar{width:34px;height:34px;border-radius:11px;flex-shrink:0;display:grid;place-items:center;color:#fff;font-size:12px;font-weight:800}
 .bmeta{font-size:12.5px;margin-bottom:3px} .bmeta .muted{color:var(--sub);margin-left:6px}
 .btext{background:var(--fill);border-radius:4px 14px 14px 14px;padding:11px 14px;font-size:14.5px;line-height:1.6;display:inline-block}
 .toasts{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);display:flex;flex-direction:column;gap:10px;z-index:99;align-items:center}
 .toast{background:var(--toast-bg);color:var(--toast-t);padding:13px 18px;border-radius:13px;font-size:14px;font-weight:600;
  box-shadow:0 8px 30px rgba(0,0,0,.25);display:flex;align-items:center;gap:9px;animation:tin .28s cubic-bezier(.2,.8,.2,1)}
 .toast.out{animation:tout .3s forwards} .toast .td{width:8px;height:8px;border-radius:50%;background:var(--pri)}
 .toast.ok .td{background:var(--ok)} .toast.err .td{background:var(--danger)} .toast.warn .td{background:var(--warn)}
 @keyframes tin{from{opacity:0;transform:translateY(16px) scale(.96)}to{opacity:1;transform:none}}
 @keyframes tout{to{opacity:0;transform:translateY(10px)}}
</style></head><body>
<div class="layout">
 <aside class="side">
  <div class="brand"><span class="logo">🤖</span><span>회의록 봇</span></div>
  <div class="moderow" title="이 서버가 켜져 있는 동안에만 적용돼요 (.env 파일은 그대로).">
   <div>흉내 모드<div class="sub">켜면 실제로 동작 안 함</div></div>
   <label class="sw"><input type="checkbox" id="mockSw" onchange="setMode(this.checked)"><span class="sl"></span></label>
  </div>
  <div class="modebadge" id="modeBadge"></div>
  <div class="nav">
   <button class="on" data-v="join" onclick="go('join')"><span class="ic">▶</span>회의 참석</button>
   <button data-v="status" onclick="go('status')"><span class="ic">📡</span>상태 모니터링</button>
   <button data-v="transcript" onclick="go('transcript')"><span class="ic">🎙</span>녹취파일<span class="badge" id="bTr">0</span></button>
   <button data-v="minutes" onclick="go('minutes')"><span class="ic">📄</span>회의록<span class="badge" id="bMn">0</span></button>
  </div>
  <div class="foot"><span class="dot" id="svcDot"></span><span id="svcTxt">서비스 확인 중…</span></div>
 </aside>
 <main>
  <div class="head"><h1 id="vTitle">회의 참석</h1><p id="vDesc">회의 링크를 붙여넣으면 봇이 회의에 참석해요.</p></div>

  <section id="join" class="view on">
   <div class="card">
    <h3>봇 참석</h3><p class="desc">Google Meet · Zoom · Teams · Jitsi 링크를 넣을 수 있어요.</p>
    <div class="field">
     <input class="input" id="url" placeholder="https://meet.google.com/abc-defg-hij" onkeydown="if(event.key==='Enter')joinBot()">
     <select class="select" id="joinProfile" style="flex:0 0 140px"><option value="secure">secure · 로컬</option><option value="internal">internal</option></select>
     <button class="btn pri" id="joinBtn" onclick="joinBot()">참석시키기</button>
    </div>
    <div style="display:flex;align-items:center;gap:18px;margin-top:12px;flex-wrap:wrap">
     <label style="display:flex;align-items:center;gap:8px;font-size:13.5px;color:var(--sub)">
      🏷 봇 이름
      <input class="input" id="botName" placeholder="회의록봇" maxlength="60"
       style="padding:8px 12px;font-size:14px;width:200px;flex:0 0 auto" title="회의별로 바꿀 수 있어요 (한/영)">
     </label>
     <label style="display:flex;align-items:center;gap:7px;font-size:13.5px;color:var(--sub);cursor:pointer">
      <input type="checkbox" id="autoMin" checked> 회의가 끝나면 회의록을 <b style="color:var(--text);margin:0 2px">자동으로</b> 만들어요
     </label>
    </div>
    <div class="result" id="joinRes"></div>
   </div>
   <div class="card" id="trackCard" style="display:none">
    <h3>자동 회의록 진행 <span class="desc" style="font-weight:500">참석한 회의가 끝나면 자동 생성</span></h3>
    <div class="flist" id="trackList" style="margin-top:14px"></div>
   </div>
   <div class="card">
    <h3>회의록 작성 <span class="desc" style="font-weight:500">수동 · 자동이 안 됐을 때만</span></h3>
    <p class="desc">보통은 위 자동 생성으로 충분해요. 필요할 때만 링크로 직접 만듭니다.</p>
    <div class="field">
     <input class="input" id="mid" placeholder="회의 링크 붙여넣기 (참석 때와 동일) — 플랫폼 자동 인식">
     <select class="select" id="profile" style="flex:0 0 140px"><option value="secure">secure · 로컬</option><option value="internal">internal</option></select>
     <button class="btn pri" id="ingBtn" onclick="ingest()">회의록 만들기</button>
     <button class="btn gray" onclick="stopBot()">봇 종료</button>
    </div>
    <div class="result" id="ingRes"></div>
   </div>
  </section>

  <section id="status" class="view">
   <div style="display:flex;gap:10px;align-items:center;margin-bottom:14px">
    <button class="btn gray sm" onclick="loadStatus()">↻ 새로고침</button>
    <label style="font-size:13px;color:var(--sub);display:flex;gap:6px;align-items:center">
     <input type="checkbox" id="auto" onchange="toggleAuto()">자동 새로고침(5초)</label>
   </div>
   <div class="grid" id="statGrid"></div>
   <div class="card" style="margin-top:14px"><h3>원본 응답</h3><pre id="statRaw" style="white-space:pre-wrap;color:var(--sub);font-size:12.5px;margin:8px 0 0"></pre></div>
  </section>

  <section id="transcript" class="view">
   <div class="split">
    <div>
     <div style="margin-bottom:10px;display:flex;gap:8px">
      <button class="btn gray sm" onclick="loadFiles('transcript')">↻ 새로고침</button>
      <button class="btn gray sm" onclick="$('upTr').click()">⬆ 업로드</button>
      <input type="file" id="upTr" accept=".json" style="display:none" onchange="doUpload('transcript',this)">
     </div>
     <div class="flist" id="trList"></div></div>
    <div class="viewer" id="trView"><div class="empty"><div class="big">🎙</div>왼쪽에서 녹취파일을 골라 보세요.</div></div>
   </div>
  </section>

  <section id="minutes" class="view">
   <div class="split">
    <div>
     <div style="margin-bottom:10px;display:flex;gap:8px">
      <button class="btn gray sm" onclick="loadFiles('minutes')">↻ 새로고침</button>
      <button class="btn gray sm" onclick="$('upMn').click()">⬆ 업로드</button>
      <input type="file" id="upMn" accept=".md,.markdown,.txt" style="display:none" onchange="doUpload('minutes',this)">
     </div>
     <div class="flist" id="mnList"></div></div>
    <div class="viewer" id="mnView"><div class="empty"><div class="big">📄</div>왼쪽에서 회의록을 골라 보세요.</div></div>
   </div>
  </section>
 </main>
</div>
<div class="toasts" id="toasts"></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const TITLES={join:['회의 참석','회의 링크를 붙여넣으면 봇이 회의에 참석해요.'],
 status:['상태 모니터링','서비스와 Vexa 봇이 잘 도는지 확인해요.'],
 transcript:['녹취파일','봇이 모은 화자별 전사를 볼 수 있어요.'],
 minutes:['회의록','LLM이 정리한 회의록을 볼 수 있어요.']};
function toast(msg,type){const t=document.createElement('div');t.className='toast '+(type||'');
 t.innerHTML='<span class="td"></span>'+esc(msg);$('toasts').appendChild(t);
 setTimeout(()=>{t.classList.add('out');setTimeout(()=>t.remove(),300);},2600);}
function busy(id,on,label){const b=$(id);b.disabled=on;b.innerHTML=on?'<span class="spin"></span>처리 중':label;}

async function jpost(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return r.json();}
async function jget(path){const r=await fetch(path);return r.json();}

function go(v){document.querySelectorAll('.view').forEach(s=>s.classList.toggle('on',s.id===v));
 document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
 $('vTitle').textContent=TITLES[v][0];$('vDesc').textContent=TITLES[v][1];
 if(v==='status')loadStatus(); if(v==='transcript')loadFiles('transcript'); if(v==='minutes')loadFiles('minutes');}

/* 참석 */
async function joinBot(){const url=$('url').value.trim(); if(!url)return toast('회의 링크를 넣어 주세요','err');
 const profile=$('joinProfile').value, auto=$('autoMin').checked, bot_name=$('botName').value.trim();
 try{localStorage.setItem('botName',bot_name);}catch(e){}   // 회의마다 바꿔도 마지막 값 기억
 busy('joinBtn',true); let r; try{r=await jpost('/bot/dispatch',{url,profile,auto,bot_name});}catch(e){busy('joinBtn',false,'참석시키기');return toast('서버에 연결하지 못했어요','err');}
 busy('joinBtn',false,'참석시키기'); const res=$('joinRes');
 if(r.ok===false){res.className='result show err';res.innerHTML='<span class="chip r">실패</span>'+esc(r.error||'오류가 났어요');toast('참석하지 못했어요','err');return;}
 res.className='result show';res.innerHTML='<span class="chip g">참석 요청됨</span>'+
  '<b>'+esc(r.platform||'')+'</b><span style="color:var(--sub)">·</span><code style="background:var(--pri-soft);padding:3px 8px;border-radius:7px">'+esc(r.native_meeting_id||'')+'</code>'+
  (r.bot_name?'<span class="chip">🏷 '+esc(r.bot_name)+'</span>':'')+
  (auto&&!MOCK.vexa?'<span class="chip" style="margin-left:auto">회의 끝나면 자동 작성</span>':'')+
  (MOCK.vexa?'<span class="chip w" style="margin-left:auto">🧪 흉내 응답 · 실제 참석 아님</span>':'');
 toast(MOCK.vexa?'흉내 모드예요 — 실제 참석은 아니에요':'봇에게 참석을 요청했어요',MOCK.vexa?'warn':'ok');
 loadTracked();}
const TSTAT={waiting:['참석 대기 중…','var(--sub)'],live:['참석 중 · 녹화 중','var(--pri)'],
 done:['회의록 완료','var(--ok)'],failed:['실패','var(--danger)'],timeout:['시간초과(참석 확인 안 됨)','var(--warn)']};
async function loadTracked(){let d;try{d=await jget('/api/tracked');}catch(e){return;}
 const rows=d.tracked||[],card=$('trackCard'); if(!rows.length){card.style.display='none';return;} card.style.display='';
 $('trackList').innerHTML=rows.map(t=>{const s=TSTAT[t.status]||[t.status,'var(--sub)'];
  return '<div class="fitem" style="cursor:default"><div class="fic" style="background:var(--pri-soft)">🤖</div>'+
   '<div style="flex:1"><div class="fname">'+esc(t.platform)+' · '+esc(t.meeting)+'</div>'+
   '<div class="fmeta" style="color:'+s[1]+'">'+s[0]+(t.error?(' — '+esc(t.error)):'')+'</div></div>'+
   (t.status==='done'?'<button class="btn pri sm" onclick="go(\'minutes\')">회의록 보기</button>':'')+
   '</div>';}).join('');}
/* 회의 링크면 url로(플랫폼 자동 인식), 맨 ID면 meeting 으로(서버가 형태로 추정) */
function meetingArgs(){const v=$('mid').value.trim(); if(!v)return null;
 return v.includes('/') ? {url:v} : {meeting:v};}
async function stopBot(){const t=meetingArgs(); if(!t)return toast('회의 링크 또는 ID를 넣어 주세요','err');
 const r=await jpost('/bot/stop',t); toast(r.ok===false?('종료하지 못했어요: '+esc(r.error)):'봇을 종료했어요',r.ok===false?'err':'ok');}
async function ingest(){const t=meetingArgs(),p=$('profile').value; if(!t)return toast('회의 링크 또는 ID를 넣어 주세요','err');
 busy('ingBtn',true); let r; try{r=await jpost('/ingest',{...t,profile:p});}catch(e){busy('ingBtn',false,'회의록 만들기');return toast('서버에 연결하지 못했어요','err');}
 busy('ingBtn',false,'회의록 만들기'); const res=$('ingRes');
 if(r.ok===false){res.className='result show err';res.innerHTML='<span class="chip r">실패</span>'+esc(r.error||'오류가 났어요');toast('회의록을 만들지 못했어요','err');return;}
 res.className='result show';res.innerHTML='<span class="chip g">완료</span>세그먼트 '+r.segments+' · 결정 '+r.decisions+' · 액션 '+r.action_items+
  ((MOCK.vexa||MOCK.llm)?'<span class="chip w">🧪 흉내</span>':'')+
  ' <button class="btn pri sm" style="margin-left:auto" onclick="go(\'minutes\')">회의록 보기</button>';
 toast((MOCK.vexa||MOCK.llm)?'흉내 모드로 예시 회의록을 만들었어요':'회의록을 만들었어요',(MOCK.vexa||MOCK.llm)?'warn':'ok'); refreshBadges();}

/* 상태 */
let autoTimer=null;
function toggleAuto(){if($('auto').checked){autoTimer=setInterval(loadStatus,5000);}else{clearInterval(autoTimer);autoTimer=null;}}
async function loadStatus(){const g=$('statGrid');g.innerHTML='<div class="stat"><div class="skel" style="width:60%"></div><div class="skel" style="width:40%;height:24px"></div></div>'.repeat(3);
 let d; try{d=await jget('/api/status');}catch(e){g.innerHTML='<div class="stat"><div class="k">서비스</div><div class="v" style="color:var(--danger)">오프라인</div></div>';return;}
 const vx=d.vexa||{}; const err=vx.error; const bots=(vx.running_bots||vx.bots||[]);
 const mk=d.mock||{};
 g.innerHTML=
  card('모드',mk.any?'흉내(mock)':'실제',mk.any?'warn':'ok')+
  card('서비스','정상','ok')+
  card('Vexa 연결',err?'미연결':'정상',err?'bad':'ok')+
  card('실행 중 봇',String(Array.isArray(bots)?bots.length:0),'');
 $('statRaw').textContent=JSON.stringify(d,null,2);}
function card(k,v,tone){const c=tone==='ok'?'var(--ok)':tone==='bad'?'var(--danger)':tone==='warn'?'var(--warn)':'var(--text)';
 return '<div class="stat"><div class="k">'+esc(k)+'</div><div class="v" style="color:'+c+'">'+esc(v)+'</div></div>';}

/* 파일 목록/뷰어 */
async function loadFiles(kind){const listId=kind==='minutes'?'mnList':'trList';const box=$(listId);
 box.innerHTML='<div class="skel" style="height:66px"></div><div class="skel" style="height:66px"></div>';
 let d; try{d=await jget('/api/files');}catch(e){box.innerHTML='<div class="empty">목록을 불러오지 못했어요.</div>';return;}
 const rows=(d.files||[]).filter(f=>f.kind===kind);
 $('bTr').textContent=(d.files||[]).filter(f=>f.kind==='transcript').length;
 $('bMn').textContent=(d.files||[]).filter(f=>f.kind==='minutes').length;
 if(!rows.length){const label=kind==='minutes'?'회의록':'녹취파일';
  box.innerHTML='<div class="empty"><div class="big">🗂️</div>아직 '+label+'이 없어요.<br><span style="font-size:12px">회의가 끝나면 여기에 쌓여요.</span></div>';return;}
 const ic=kind==='minutes'?['📄','var(--pri-soft)']:['🎙','var(--ok-soft)'];
 box.innerHTML=rows.map(f=>'<div class="fitem" data-p="'+esc(f.path)+'" onclick="openFile(\''+kind+'\',this)">'+
  '<div class="fic" style="background:'+ic[1]+'">'+ic[0]+'</div>'+
  '<div style="flex:1;min-width:0"><div class="fname">'+esc(f.name)+'</div><div class="fmeta">'+new Date(f.mtime*1000).toLocaleString('ko-KR')+' · '+fmtSize(f.size)+'</div></div>'+
  '<button class="iconbtn" title="이름 변경" onclick="renFile(event,\''+kind+'\')">✎</button>'+
  '<button class="iconbtn del" title="삭제" onclick="delFile(event,\''+kind+'\')">🗑</button>'+
  '</div>').join('');}
async function doUpload(kind,el){const f=el.files&&el.files[0]; el.value=''; if(!f)return;
 let text; try{text=await f.text();}catch(e){return toast('파일을 읽지 못했어요','err');}
 const r=await jpost('/api/upload',{kind,name:f.name,content:text});
 if(r.ok===false)return toast('업로드 실패: '+esc(r.error),'err');
 toast('업로드했어요','ok'); loadFiles(kind);}
async function delFile(ev,kind){ev.stopPropagation();
 const el=ev.currentTarget.closest('.fitem'),path=el.dataset.p;
 if(!confirm('이 파일을 삭제할까요?\n'+path))return;
 const r=await jpost('/api/delete',{path}); if(r.ok===false)return toast('삭제 실패: '+esc(r.error),'err');
 toast('삭제했어요','ok'); $(kind==='minutes'?'mnView':'trView').innerHTML='<div class="empty">삭제했어요.</div>'; loadFiles(kind);}
async function renFile(ev,kind){ev.stopPropagation();
 const el=ev.currentTarget.closest('.fitem'),path=el.dataset.p;
 const cur=el.querySelector('.fname').textContent.replace(/\.(minutes\.md|transcript\.json)$/,'');
 const nn=prompt('새 이름 (확장자 빼고):',cur); if(nn===null||!nn.trim())return;
 const r=await jpost('/api/rename',{path,name:nn.trim()}); if(r.ok===false)return toast('이름 변경 실패: '+esc(r.error),'err');
 toast('이름을 바꿨어요','ok'); loadFiles(kind);}
function fmtSize(b){return b<1024?b+' B':(b/1024).toFixed(1)+' KB';}
async function openFile(kind,el){const listId=kind==='minutes'?'mnList':'trList',viewId=kind==='minutes'?'mnView':'trView';
 document.querySelectorAll('#'+listId+' .fitem').forEach(x=>x.classList.remove('sel'));el.classList.add('sel');
 const v=$(viewId);v.innerHTML='<div class="skel" style="width:50%"></div><div class="skel"></div><div class="skel" style="width:80%"></div>';
 let d; try{d=await jget('/api/file?path='+encodeURIComponent(el.dataset.p));}catch(e){v.innerHTML='<div class="empty">내용을 불러오지 못했어요.</div>';return;}
 if(d.ok===false){v.innerHTML='<div class="empty">'+esc(d.error||'내용을 불러오지 못했어요.')+'</div>';return;}
 v.innerHTML=kind==='minutes'?'<div class="md">'+mdToHtml(d.content)+'</div>':renderTranscript(d.content);}

/* 마크다운 렌더 */
function inlineMd(s){s=esc(s);s=s.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');
 s=s.replace(/`([^`]+)`/g,'<code>$1</code>');s=s.replace(/_\((.+?)\)_/g,'<em>($1)</em>');return s;}
function cells(r){return r.replace(/^\s*\|/,'').replace(/\|\s*$/,'').split('|').map(c=>c.trim());}
function mdToHtml(md){const L=String(md).replace(/\r/g,'').split('\n');let o=[],i=0,lt=null;
 const cl=()=>{if(lt){o.push('</'+lt+'>');lt=null;}};
 while(i<L.length){let ln=L[i],m;
  if(/^\s*\|/.test(ln)){cl();let t=[];while(i<L.length&&/^\s*\|/.test(L[i])){t.push(L[i]);i++;}
   let h=cells(t[0]),b=t.slice(2).map(cells);
   o.push('<table><thead><tr>'+h.map(c=>'<th>'+inlineMd(c)+'</th>').join('')+'</tr></thead><tbody>'+
    b.map(r=>'<tr>'+r.map(c=>'<td>'+inlineMd(c)+'</td>').join('')+'</tr>').join('')+'</tbody></table>');continue;}
  if(m=ln.match(/^###\s+(.*)/)){cl();o.push('<h3>'+inlineMd(m[1])+'</h3>');i++;continue;}
  if(m=ln.match(/^##\s+(.*)/)){cl();o.push('<h2>'+inlineMd(m[1])+'</h2>');i++;continue;}
  if(m=ln.match(/^#\s+(.*)/)){cl();o.push('<h1>'+inlineMd(m[1])+'</h1>');i++;continue;}
  if(/^\s*---+\s*$/.test(ln)){cl();o.push('<hr>');i++;continue;}
  if(m=ln.match(/^\s*[-*]\s+(.*)/)){if(lt!=='ul'){cl();o.push('<ul>');lt='ul';}o.push('<li>'+inlineMd(m[1])+'</li>');i++;continue;}
  if(m=ln.match(/^\s*\d+\.\s+(.*)/)){if(lt!=='ol'){cl();o.push('<ol>');lt='ol';}o.push('<li>'+inlineMd(m[1])+'</li>');i++;continue;}
  if(/^\s*$/.test(ln)){cl();i++;continue;}
  cl();o.push('<p>'+inlineMd(ln)+'</p>');i++;}
 cl();return o.join('');}

/* 녹취 화자 말풍선 */
function fmtTime(x){x=Math.floor(x||0);const m=Math.floor(x/60),s=x%60;return (m<10?'0':'')+m+':'+(s<10?'0':'')+s;}
function renderTranscript(txt){let d;try{d=JSON.parse(txt);}catch(e){return '<pre>'+esc(txt)+'</pre>';}
 const segs=d.segments||[];if(!segs.length)return '<div class="empty">아직 전사 내용이 없어요.</div>';
 const cols=['#3182f6','#12b886','#f7931e','#8e5cf7','#f04452','#00b8d4','#e64980'];const map={};let ci=0;
 let meta=d.meta&&d.meta.meeting_title?'<h1 class="md" style="margin-top:0">'+esc(d.meta.meeting_title)+'</h1>':'';
 return meta+'<div class="chat">'+segs.map(s=>{const n=s.speaker||'화자';if(!(n in map)){map[n]=cols[ci%cols.length];ci++;}
  return '<div class="bubble"><div class="avatar" style="background:'+map[n]+'">'+esc(n).slice(-2)+'</div>'+
   '<div><div class="bmeta"><b>'+esc(n)+'</b><span class="muted">'+fmtTime(s.start)+'</span></div>'+
   '<div class="btext">'+esc(s.text)+'</div></div></div>';}).join('')+'</div>';}

/* 부트스트랩 */
let MOCK={};
const MOCK_LABEL={vexa:'봇 참석',llm:'회의록 작성',asr:'전사',diarizer:'화자분리'};
function applyMock(m){MOCK=m||{};const b=$('modeBadge');const sw=$('mockSw');if(sw)sw.checked=!!(m&&m.any);
 if(m&&m.any){const parts=Object.keys(MOCK_LABEL).filter(k=>m[k]).map(k=>MOCK_LABEL[k]);
  b.className='modebadge on';
  b.innerHTML='🧪 흉내 모드(mock)<br><span style="font-weight:500;font-size:11px">'+parts.join(' · ')+' — 실제 동작 안 함</span>';
  b.title='흉내(mock) 대상: '+parts.join(', ')+'\n실제로 회의에 참석하거나 전사·회의록을 만들지 않고, 예시 응답만 줘요.\n실전은 .env 의 *_=mock 을 지우고 Vexa/모델을 켜세요.';}
 else b.className='modebadge';}
async function setMode(on){let r;try{r=await jpost('/mode',{mock:on});}catch(e){return toast('모드를 바꾸지 못했어요','err');}
 applyMock(r.mock);
 if(on)toast('흉내 모드로 바꿨어요 — 실제로 동작하지 않아요','warn');
 else toast('실제 모드로 바꿨어요 — Vexa·모델이 켜져 있어야 동작해요','ok');}
async function svcCheck(){try{const h=await jget('/health');$('svcDot').className='dot ok';$('svcTxt').textContent='서비스 온라인';applyMock(h.mock);}
 catch(e){$('svcDot').className='dot bad';$('svcTxt').textContent='서비스 오프라인';}}
async function refreshBadges(){try{const d=await jget('/api/files');const f=d.files||[];
 $('bTr').textContent=f.filter(x=>x.kind==='transcript').length;$('bMn').textContent=f.filter(x=>x.kind==='minutes').length;}catch(e){}}
try{const sn=localStorage.getItem('botName'); if(sn)$('botName').value=sn;}catch(e){}
svcCheck();refreshBadges();loadTracked();setInterval(loadTracked,8000);
</script></body></html>"""
