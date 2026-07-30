"""웹 대시보드 HTML (minutes.server 가 GET / 에 서빙).

단일 파일(인라인 CSS/JS, 외부 CDN 없음 → 오프라인/air-gapped 동작).
토스(Toss) 스타일 참고: 카드·부드러운 그림자·라운드·토스트·스켈레톤·전환.
회의록은 마크다운 렌더링, 녹취는 화자 말풍선으로 표시.
"""

# 원시 문자열(r""")로 두어 JS 정규식의 백슬래시가 파이썬에 먹히지 않게 한다.
INDEX_HTML = r"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>회의록 봇 대시보드</title>
<style>
 :root{
  --bg:#f2f4f6; --card:#fff; --text:#191f28; --sub:#8b95a1; --line:#e9ecef;
  --pri:#3182f6; --pri-d:#1b64da; --pri-soft:#e8f3ff; --ok:#12b886; --danger:#f04452;
  --r:18px; --sh:0 1px 2px rgba(0,0,0,.04),0 6px 20px rgba(0,0,0,.05);
 }
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
 .nav{display:flex;flex-direction:column;gap:4px}
 .nav button{display:flex;align-items:center;gap:11px;width:100%;border:0;background:transparent;
  color:var(--sub);font:inherit;font-weight:600;font-size:14.5px;padding:12px 12px;border-radius:12px;
  cursor:pointer;transition:.15s;text-align:left}
 .nav button:hover{background:#f5f6f8;color:var(--text)}
 .nav button.on{background:var(--pri-soft);color:var(--pri)}
 .nav button .ic{width:20px;text-align:center;font-size:16px}
 .nav .badge{margin-left:auto;background:#eef1f4;color:var(--sub);font-size:11px;font-weight:700;
  padding:2px 8px;border-radius:99px;min-width:20px;text-align:center}
 .nav button.on .badge{background:#fff;color:var(--pri)}
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
  font:inherit;font-size:15px;background:#fbfcfd;transition:.15s;color:var(--text)}
 .input:focus,.select:focus{outline:0;border-color:var(--pri);background:#fff;box-shadow:0 0 0 4px var(--pri-soft)}
 .btn{padding:14px 20px;border:0;border-radius:13px;font:inherit;font-weight:700;font-size:15px;cursor:pointer;
  transition:.13s;display:inline-flex;align-items:center;gap:7px;white-space:nowrap}
 .btn:active{transform:scale(.97)} .btn[disabled]{opacity:.6;cursor:default}
 .btn.pri{background:var(--pri);color:#fff} .btn.pri:hover{background:var(--pri-d)}
 .btn.gray{background:#eef1f4;color:#4e5968} .btn.gray:hover{background:#e5e9ee}
 .btn.sm{padding:9px 14px;font-size:13.5px;border-radius:10px}
 .spin{width:15px;height:15px;border:2.5px solid rgba(255,255,255,.45);border-top-color:#fff;border-radius:50%;
  animation:sp .7s linear infinite;display:inline-block}
 .btn.gray .spin{border-color:rgba(0,0,0,.15);border-top-color:#4e5968}
 @keyframes sp{to{transform:rotate(360deg)}}
 .result{margin-top:16px;display:none;align-items:center;gap:12px;background:#f6fbff;border:1px solid #d6e9ff;
  border-radius:14px;padding:16px}
 .result.show{display:flex} .result.err{background:#fff5f5;border-color:#ffd6d9}
 .chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:700;padding:5px 11px;
  border-radius:99px;background:var(--pri-soft);color:var(--pri)}
 .chip.g{background:#e9fbf3;color:var(--ok)}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
 .stat{background:var(--card);border-radius:16px;box-shadow:var(--sh);padding:20px}
 .stat .k{color:var(--sub);font-size:13px;margin-bottom:8px} .stat .v{font-size:26px;font-weight:800}
 /* file list */
 .flist{display:flex;flex-direction:column;gap:8px}
 .fitem{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:14px 16px;cursor:pointer;transition:.13s}
 .fitem:hover{border-color:#cfe1ff;box-shadow:var(--sh);transform:translateY(-1px)}
 .fitem.sel{border-color:var(--pri);background:#f8fbff}
 .fitem .fic{width:38px;height:38px;border-radius:11px;display:grid;place-items:center;font-size:17px;flex-shrink:0}
 .fitem .fname{font-weight:700;font-size:14.5px} .fitem .fmeta{color:var(--sub);font-size:12px;margin-top:2px}
 .split{display:grid;grid-template-columns:340px 1fr;gap:18px}
 @media(max-width:820px){.split{grid-template-columns:1fr}}
 .viewer{background:var(--card);border-radius:var(--r);box-shadow:var(--sh);padding:26px 28px;min-height:300px}
 .empty{color:var(--sub);text-align:center;padding:60px 20px;font-size:14px}
 .empty .big{font-size:40px;margin-bottom:10px;opacity:.6}
 .skel{height:16px;border-radius:8px;background:linear-gradient(90deg,#eef1f4,#f6f8fa,#eef1f4);
  background-size:200% 100%;animation:sh 1.2s infinite;margin:10px 0}
 @keyframes sh{to{background-position:-200% 0}}
 /* markdown */
 .md h1{font-size:22px;margin:.2em 0 .6em} .md h2{font-size:17px;margin:1.4em 0 .5em;padding-bottom:6px;border-bottom:1px solid var(--line)}
 .md h3{font-size:15px;margin:1.1em 0 .3em;color:#495057}
 .md p{margin:.4em 0;line-height:1.7} .md ul,.md ol{margin:.4em 0;padding-left:22px;line-height:1.8}
 .md li::marker{color:var(--pri)} .md em{color:var(--sub);font-style:normal;font-size:13px}
 .md hr{border:0;border-top:1px solid var(--line);margin:1.2em 0}
 .md code{background:#f1f3f5;padding:2px 6px;border-radius:6px;font-size:13px}
 .md table{border-collapse:collapse;width:100%;margin:.6em 0;font-size:14px}
 .md th{background:#f6f8fa;text-align:left} .md th,.md td{border:1px solid var(--line);padding:9px 12px}
 /* transcript chat */
 .chat{display:flex;flex-direction:column;gap:14px}
 .bubble{display:flex;gap:11px}
 .avatar{width:34px;height:34px;border-radius:11px;flex-shrink:0;display:grid;place-items:center;color:#fff;font-size:12px;font-weight:800}
 .bmeta{font-size:12.5px;margin-bottom:3px} .bmeta .muted{color:var(--sub);margin-left:6px}
 .btext{background:#f5f6f8;border-radius:4px 14px 14px 14px;padding:11px 14px;font-size:14.5px;line-height:1.6;display:inline-block}
 .toasts{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);display:flex;flex-direction:column;gap:10px;z-index:99;align-items:center}
 .toast{background:#191f28;color:#fff;padding:13px 18px;border-radius:13px;font-size:14px;font-weight:600;
  box-shadow:0 8px 30px rgba(0,0,0,.25);display:flex;align-items:center;gap:9px;animation:tin .28s cubic-bezier(.2,.8,.2,1)}
 .toast.out{animation:tout .3s forwards} .toast .td{width:8px;height:8px;border-radius:50%;background:#5b9dff}
 .toast.ok .td{background:var(--ok)} .toast.err .td{background:var(--danger)}
 @keyframes tin{from{opacity:0;transform:translateY(16px) scale(.96)}to{opacity:1;transform:none}}
 @keyframes tout{to{opacity:0;transform:translateY(10px)}}
</style></head><body>
<div class="layout">
 <aside class="side">
  <div class="brand"><span class="logo">🤖</span><span>회의록 봇</span></div>
  <div class="nav">
   <button class="on" data-v="join" onclick="go('join')"><span class="ic">▶</span>회의 참석</button>
   <button data-v="status" onclick="go('status')"><span class="ic">📡</span>상태 모니터링</button>
   <button data-v="transcript" onclick="go('transcript')"><span class="ic">🎙</span>녹취파일<span class="badge" id="bTr">0</span></button>
   <button data-v="minutes" onclick="go('minutes')"><span class="ic">📄</span>회의록<span class="badge" id="bMn">0</span></button>
  </div>
  <div class="foot"><span class="dot" id="svcDot"></span><span id="svcTxt">서비스 확인 중…</span></div>
 </aside>
 <main>
  <div class="head"><h1 id="vTitle">회의 참석</h1><p id="vDesc">회의 링크를 붙여넣으면 봇이 참석합니다.</p></div>

  <section id="join" class="view on">
   <div class="card">
    <h3>봇 참석</h3><p class="desc">Google Meet · Zoom · Teams · Jitsi 링크를 지원합니다.</p>
    <div class="field">
     <input class="input" id="url" placeholder="https://meet.google.com/abc-defg-hij" onkeydown="if(event.key==='Enter')joinBot()">
     <button class="btn pri" id="joinBtn" onclick="joinBot()">봇 참석</button>
    </div>
    <div class="result" id="joinRes"></div>
   </div>
   <div class="card">
    <h3>회의록 생성 <span class="desc" style="font-weight:500">회의 종료 후</span></h3>
    <p class="desc">Vexa 전사를 가져와 LLM으로 회의록을 만듭니다.</p>
    <div class="field">
     <input class="input" id="mid" placeholder="회의 ID (예: abc-defg-hij)">
     <select class="select" id="profile" style="flex:0 0 150px"><option value="secure">secure · 로컬</option><option value="internal">internal</option></select>
     <button class="btn pri" id="ingBtn" onclick="ingest()">회의록 생성</button>
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
    <div><div style="margin-bottom:10px"><button class="btn gray sm" onclick="loadFiles('transcript')">↻ 새로고침</button></div>
     <div class="flist" id="trList"></div></div>
    <div class="viewer" id="trView"><div class="empty"><div class="big">🎙</div>왼쪽에서 녹취파일을 선택하세요.</div></div>
   </div>
  </section>

  <section id="minutes" class="view">
   <div class="split">
    <div><div style="margin-bottom:10px"><button class="btn gray sm" onclick="loadFiles('minutes')">↻ 새로고침</button></div>
     <div class="flist" id="mnList"></div></div>
    <div class="viewer" id="mnView"><div class="empty"><div class="big">📄</div>왼쪽에서 회의록을 선택하세요.</div></div>
   </div>
  </section>
 </main>
</div>
<div class="toasts" id="toasts"></div>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const TITLES={join:['회의 참석','회의 링크를 붙여넣으면 봇이 참석합니다.'],
 status:['상태 모니터링','서비스와 Vexa 봇 상태를 확인합니다.'],
 transcript:['녹취파일','봇이 수집한 화자별 전사입니다.'],
 minutes:['회의록','LLM이 작성한 구조화 회의록입니다.']};
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
async function joinBot(){const url=$('url').value.trim(); if(!url)return toast('회의 링크를 입력하세요','err');
 busy('joinBtn',true); let r; try{r=await jpost('/bot/dispatch',{url});}catch(e){busy('joinBtn',false,'봇 참석');return toast('연결 실패','err');}
 busy('joinBtn',false,'봇 참석'); const res=$('joinRes');
 if(r.ok===false){res.className='result show err';res.innerHTML='<span class="chip" style="background:#ffe3e6;color:#f04452">실패</span>'+esc(r.error||'오류');toast('참석 실패','err');return;}
 res.className='result show';res.innerHTML='<span class="chip g">참석 요청됨</span>'+
  '<b>'+esc(r.platform||'')+'</b><span class="muted" style="color:var(--sub)">·</span><code style="background:#eef4ff;padding:3px 8px;border-radius:7px">'+esc(r.native_meeting_id||'')+'</code>';
 toast('봇이 회의에 참석 요청되었습니다','ok');}
async function stopBot(){const m=$('mid').value.trim(); if(!m)return toast('회의 ID를 입력하세요','err');
 const r=await jpost('/bot/stop',{meeting:m}); toast(r.ok===false?('종료 실패: '+esc(r.error)):'봇을 종료했습니다',r.ok===false?'err':'ok');}
async function ingest(){const m=$('mid').value.trim(),p=$('profile').value; if(!m)return toast('회의 ID를 입력하세요','err');
 busy('ingBtn',true); let r; try{r=await jpost('/ingest',{meeting:m,profile:p});}catch(e){busy('ingBtn',false,'회의록 생성');return toast('연결 실패','err');}
 busy('ingBtn',false,'회의록 생성'); const res=$('ingRes');
 if(r.ok===false){res.className='result show err';res.innerHTML='<span class="chip" style="background:#ffe3e6;color:#f04452">실패</span>'+esc(r.error||'오류');toast('생성 실패','err');return;}
 res.className='result show';res.innerHTML='<span class="chip g">완료</span>세그먼트 '+r.segments+' · 결정 '+r.decisions+' · 액션 '+r.action_items+
  ' <button class="btn pri sm" style="margin-left:auto" onclick="go(\'minutes\')">회의록 보기</button>';
 toast('회의록이 생성되었습니다','ok'); refreshBadges();}

/* 상태 */
let autoTimer=null;
function toggleAuto(){if($('auto').checked){autoTimer=setInterval(loadStatus,5000);}else{clearInterval(autoTimer);autoTimer=null;}}
async function loadStatus(){const g=$('statGrid');g.innerHTML='<div class="stat"><div class="skel" style="width:60%"></div><div class="skel" style="width:40%;height:24px"></div></div>'.repeat(3);
 let d; try{d=await jget('/api/status');}catch(e){g.innerHTML='<div class="stat"><div class="k">서비스</div><div class="v" style="color:var(--danger)">오프라인</div></div>';return;}
 const vx=d.vexa||{}; const err=vx.error; const bots=(vx.running_bots||vx.bots||[]);
 g.innerHTML=
  card('서비스','정상','ok')+
  card('Vexa 연결',err?'미연결':'정상',err?'bad':'ok')+
  card('실행 중 봇',String(Array.isArray(bots)?bots.length:0),'');
 $('statRaw').textContent=JSON.stringify(d,null,2);}
function card(k,v,tone){const c=tone==='ok'?'var(--ok)':tone==='bad'?'var(--danger)':'var(--text)';
 return '<div class="stat"><div class="k">'+esc(k)+'</div><div class="v" style="color:'+c+'">'+esc(v)+'</div></div>';}

/* 파일 목록/뷰어 */
async function loadFiles(kind){const listId=kind==='minutes'?'mnList':'trList';const box=$(listId);
 box.innerHTML='<div class="skel" style="height:66px"></div><div class="skel" style="height:66px"></div>';
 let d; try{d=await jget('/api/files');}catch(e){box.innerHTML='<div class="empty">불러오기 실패</div>';return;}
 const rows=(d.files||[]).filter(f=>f.kind===kind);
 $('bTr').textContent=(d.files||[]).filter(f=>f.kind==='transcript').length;
 $('bMn').textContent=(d.files||[]).filter(f=>f.kind==='minutes').length;
 if(!rows.length){box.innerHTML='<div class="empty"><div class="big">📭</div>파일이 없습니다.<br><span style="font-size:12px">data/out 에 생성되면 표시됩니다.</span></div>';return;}
 const ic=kind==='minutes'?['📄','#e8f3ff']:['🎙','#e9fbf3'];
 box.innerHTML=rows.map(f=>'<div class="fitem" data-p="'+esc(f.path)+'" onclick="openFile(\''+kind+'\',this)">'+
  '<div class="fic" style="background:'+ic[1]+'">'+ic[0]+'</div>'+
  '<div><div class="fname">'+esc(f.name)+'</div><div class="fmeta">'+new Date(f.mtime*1000).toLocaleString('ko-KR')+' · '+fmtSize(f.size)+'</div></div></div>').join('');}
function fmtSize(b){return b<1024?b+' B':(b/1024).toFixed(1)+' KB';}
async function openFile(kind,el){const listId=kind==='minutes'?'mnList':'trList',viewId=kind==='minutes'?'mnView':'trView';
 document.querySelectorAll('#'+listId+' .fitem').forEach(x=>x.classList.remove('sel'));el.classList.add('sel');
 const v=$(viewId);v.innerHTML='<div class="skel" style="width:50%"></div><div class="skel"></div><div class="skel" style="width:80%"></div>';
 let d; try{d=await jget('/api/file?path='+encodeURIComponent(el.dataset.p));}catch(e){v.innerHTML='<div class="empty">불러오기 실패</div>';return;}
 if(d.ok===false){v.innerHTML='<div class="empty">'+esc(d.error||'오류')+'</div>';return;}
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
 const segs=d.segments||[];if(!segs.length)return '<div class="empty">세그먼트가 없습니다.</div>';
 const cols=['#3182f6','#12b886','#f7931e','#8e5cf7','#f04452','#00b8d4','#e64980'];const map={};let ci=0;
 let meta=d.meta&&d.meta.meeting_title?'<h1 class="md" style="margin-top:0">'+esc(d.meta.meeting_title)+'</h1>':'';
 return meta+'<div class="chat">'+segs.map(s=>{const n=s.speaker||'화자';if(!(n in map)){map[n]=cols[ci%cols.length];ci++;}
  return '<div class="bubble"><div class="avatar" style="background:'+map[n]+'">'+esc(n).slice(-2)+'</div>'+
   '<div><div class="bmeta"><b>'+esc(n)+'</b><span class="muted">'+fmtTime(s.start)+'</span></div>'+
   '<div class="btext">'+esc(s.text)+'</div></div></div>';}).join('')+'</div>';}

/* 부트스트랩 */
async function svcCheck(){try{await jget('/health');$('svcDot').className='dot ok';$('svcTxt').textContent='서비스 온라인';}
 catch(e){$('svcDot').className='dot bad';$('svcTxt').textContent='서비스 오프라인';}}
async function refreshBadges(){try{const d=await jget('/api/files');const f=d.files||[];
 $('bTr').textContent=f.filter(x=>x.kind==='transcript').length;$('bMn').textContent=f.filter(x=>x.kind==='minutes').length;}catch(e){}}
svcCheck();refreshBadges();
</script></body></html>"""
