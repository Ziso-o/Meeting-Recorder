# Meeting-Recorder — AI 회의록 자동화 시스템

온라인 회의 → **봇 참석 / 전사·화자분리 → LLM 회의록(JSON + Markdown)** 자동 생성.
웹 대시보드에 **회의 링크만 붙여넣으면** 봇이 참석하고, **회의가 끝나면 회의록이 자동으로** 만들어진다.

> 설계·규칙 [`CLAUDE.md`](./CLAUDE.md) · **Vexa 자동설치(CPU)** [`docs/VEXA_CPU_INSTALL.md`](./docs/VEXA_CPU_INSTALL.md)
> · 집 GPU PC 셋업 [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) · 로드맵 [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md)

## 스택 (전부 무료 / 오픈소스)

| 역할 | 도구 |
|---|---|
| 봇 참석 | **Vexa 셀프호스팅** (게이트웨이 :18056, Cloud 계정 불필요) |
| 전사·화자분리 | 실시간 = Vexa 내장 STT(GPU/CPU) / 파일 = faster-whisper + pyannote |
| LLM 회의록 | **Ollama**(로컬, secure) / Gemini(선택, internal) |
| 웹 대시보드 | **`minutes.server`** — 참석·자동회의록·상태·녹취·회의록·파일관리 (추가 의존성 0) |
| 원클릭 실행 | **`scripts/start_windows*.bat`** (Docker→STT→Vexa→대시보드 한 번에) |
| 오케스트레이션 | (선택) **n8n** — HTTP Request로 `minutes.server` 호출 |
| 런타임 | Python 3.11 / uv |

## 보안등급 분기 (B2G)

- **`secure`** = 로컬 Ollama + 로컬 전사 → **외부 유출 0** (민감 회의)
- **`internal`** = Gemini 등 클라우드 (내부 회의)

## 진행 상태

Phase 1–4 + **웹 대시보드**(자동 회의록 · 봇 이름 지정 · 파일 업로드/삭제/이름변경 · 흉내↔실제 토글)
+ **원클릭 배치 실행** + **Vexa 자동설치 스크립트**. pytest 73개.
✅ 실제 Vexa 셀프호스팅에서 **봇 참석·녹음까지 검증**. 회의 종료 → 자동 회의록 파이프라인 동작.
🔜 실사용 회의로 전사 품질·`glossary`/`prompts` 튜닝 → 이후 클라우드 이관.

---

## 1. 설치 (Git Bash 기준)

```bash
# ── 코드 받기(최초) ─────────────────────────────────────────
git clone https://github.com/Ziso-o/Meeting-Recorder.git    # 기본 브랜치 = main
cd Meeting-Recorder

# ── 셋업 (택1, 자동) ────────────────────────────────────────
bash scripts/home_pc_setup.sh            # 집 GPU PC: venv·설치·ollama·.env·pytest 자동
bash scripts/run_local.sh --setup-only   # uv 없어도 python -m venv 폴백

# ── 수동 설치 ───────────────────────────────────────────────
uv venv && uv pip install -e ".[transcribe]"    # uv 없으면 python -m venv .venv 후
#   .venv/Scripts/python -m pip install -e ".[transcribe]"   (Windows / Linux는 .venv/bin/python)
.venv/Scripts/python -m pytest -q               # 172 passed 확인
```

> `[transcribe]` = torch/faster-whisper/pyannote(**파일 전사**용, 무거움). Vexa 봇만이면 `[dev]`로 충분.
> 파일 전사엔 **ffmpeg** 필요(`winget install Gyan.FFmpeg` / `apt install ffmpeg`).

> **이미 `claude/…` 브랜치로 클론해 둔 PC라면** 브랜치가 `main` 하나로 통합·정리됐으니 한 번만 옮겨 두세요.
> 작업 계보는 그대로라 커밋 손실은 없습니다.
> ```bash
> git fetch origin --prune && git checkout main && git reset --hard origin/main
> ```

## 2. 설정 (`.env`)

```bash
cp .env.example .env      # 아래 [필수] 키만 채우면 됨 (나머지는 기본값 그대로)
```

| 키 | 용도 |
|---|---|
| `VEXA_API_URL` | Vexa 게이트웨이. 셀프호스팅 `http://localhost:18056` (4절 자동설치가 기입) |
| `VEXA_API_KEY` | Vexa 로컬 발급 `vxa_...` (4절 자동설치 스크립트가 admin으로 발급→자동 기입) |
| `VEXA_BOT_NAME` | 봇 기본 표시명(대시보드에서 회의별로 덮어쓸 수 있음) |
| `GEMINI_API_KEY` | (선택) internal 클라우드 LLM. 없으면 로컬 Ollama로 폴백 |
| `HF_TOKEN` | (파일 전사 시) pyannote 화자분리. Vexa 봇 경로엔 불필요 |

> **개발용 mock**: `VEXA_CLIENT`·`LLM_PROVIDER`·`ASR_ENGINE`·`DIARIZER` 를 `mock` 으로 두면
> 키·GPU·오디오 없이 전 구간 배관 확인 가능(대시보드 좌측 스위치로도 전환). 전체 키/토글은 `.env.example` 참고.

---

## 3. 실행

### A. 원클릭 (권장) — 배치 더블클릭
Vexa 설치가 끝난 PC라면 배치 하나로 **Docker → STT → Vexa → 대시보드**까지 한 번에 켜진다.

| PC | 파일 (더블클릭) |
|---|---|
| **GPU PC** | `scripts/start_windows.bat` |
| **GPU 없는 PC (CPU)** | `scripts/start_windows_cpu.bat` |

**배치 실행 순서:** ① Docker 엔진 확인/기동 → ② STT 유닛(8083) → ③ Vexa 스택(18056) → ④ 대시보드(8900)+브라우저 자동
> - **배치는 `git pull`을 안 한다.** 코드를 새로 받았으면 → `git pull` + **기존 대시보드 창 닫기** 후 배치 실행.
> - 이미 대시보드가 떠 있으면 포트 8900 충돌 → 기존 창 닫고 실행.

### B. 수동 — 대시보드만 (Vexa는 이미 떠 있을 때)
```bash
git pull origin main
.venv/Scripts/python -m minutes.server        # → http://127.0.0.1:8900/   (Linux·mac: .venv/bin/python)
```
> - venv 활성화 안 하면 `No module named 'minutes'` → `.venv/Scripts/python` 로 명시.
> - **`.env`·코드 변경 후엔 서버 재시작 필수**(시작 시 1회 로드 — 대시보드 HTML도 재시작해야 갱신).
> - 외부(다른 PC/폰) 접속은 `MINUTES_SERVER_HOST=0.0.0.0` (신뢰 네트워크·B2G 정책 확인 후).
> - 스크립트 자동화가 필요하면 CLI(`minutes.pipeline` · `bot` · `watch`)도 그대로 있음.

### 웹 대시보드

| 좌측 네비 | 하는 일 |
|---|---|
| ▶ 회의 참석 | 링크 붙여넣기 → 봇 참석(Meet/Zoom/Teams/Jitsi 자동 인식) · **봇 이름 지정(한/영)** · **회의 끝나면 자동 회의록** · 봇 종료 |
| 🎧 녹음본 올리기 | **클로바 노트 등 녹음 파일(m4a·aac·mp3·wav…) 업로드 → 전사→회의록 자동 생성** · 진행상황 표시 |
| 📡 상태 모니터링 | 서비스 / Vexa / 실행 봇 + 흉내·실제 모드 |
| 🎙 녹취파일 | 전사 → **화자별 말풍선** · **업로드/삭제/이름변경** |
| 📄 회의록 | 회의록 **마크다운 렌더** · **업로드/삭제/이름변경** |

- 좌측 **흉내↔실제 스위치**로 mock/실제 전환(재시작 불필요). 실제 모드는 `.env`에 Vexa 주소·키 필요.
- **자동 회의록**: "참석시키기" 한 번 → 회의가 끝나 봇이 나가면 워처가 **전사→회의록을 자동 생성**(수동 개입 불필요).

#### 🎧 녹음본 올리기 (봇을 못 넣은 회의 · 클로바 노트 녹음본)

봇이 참석하지 못한 회의는 **녹음 파일만 올리면** 같은 결과를 얻는다.
드래그&드롭(또는 클릭)으로 올리면 **전사(화자분리) → 회의록**까지 백그라운드로 진행되고,
"진행 상황" 카드가 단계를 보여준다. 끝나면 `📄 회의록`에 쌓인다.

- **지원 형식**: `.m4a` `.aac` `.mp3` `.wav` `.flac` `.ogg` `.opus` `.webm` `.mp4` 등
  (실제 디코딩은 ffmpeg가 하므로 ffmpeg가 읽는 건 대부분 된다). **클로바 노트 기본 내보내기 = `.m4a`**.
- **크기 상한**: 기본 500MB(`MINUTES_MAX_UPLOAD_MB`). 1시간짜리 m4a가 보통 30MB 안팎이라 넉넉하다.
  업로드는 **디스크로 스트리밍 저장**하므로 큰 파일이어도 서버 메모리를 먹지 않는다.
- 저장 위치: `data/uploads/audio/` (원본 보관) → 회의록은 `data/out/<profile>/`.
  목록의 `▶` 버튼으로 **같은 녹음본을 다시 처리**할 수 있다(프로파일만 바꿔 재생성 등).
- CLI로도 동일: `python -m minutes.pipeline --audio "회의.m4a" --profile secure`

**처음 한 번은 오래 걸립니다.** 첫 전사 때 Whisper 모델을 내려받습니다(large-v3 약 3GB).
진행 상황 카드가 `모델 받는 중 · 1,240 / 약 3,090MB`처럼 실제 진행률을 보여주니 멈춘 게 아닙니다.
다운로드는 최초 1회뿐이고, 이후엔 바로 전사로 들어갑니다.

진행 상황에는 **어떤 엔진이 어디서 도는지와 예상 시간**도 같이 나옵니다
(`faster-whisper large-v3 · CPU · 녹음 19분 · 전사 예상 15분~49분`). GPU가 없으면 CPU로 도는데,
같은 녹음도 **CPU는 GPU보다 10배 이상 느립니다.** CPU 환경이면 `.env`에서 모델을 낮추세요:

| `WHISPER_MODEL` | 다운로드 | 20분 녹음 전사(CPU 기준) |
|---|---|---|
| `large-v3` (기본) | ~3.0GB | 15분 ~ 50분 |
| `medium` | ~1.5GB | 6분 ~ 20분 |
| `small` | ~0.5GB | 2분 ~ 8분 |

> `HF_TOKEN`을 채우면 다운로드 속도 제한이 풀리고 **화자분리도 켜집니다.**
> 토큰이 없으면 `diarizer=off`로 떨어져 **회의록의 화자가 전원 1명으로 나옵니다.**

**진행률은 실제 수치입니다.** 전사는 오디오 타임라인 기준(`42% · 8:16 / 19:40`),
모델 다운로드는 받은 용량 기준, 회의록은 청크 기준으로 표시되고,
**실측 처리 속도로 남은 시간**을 같이 보여줍니다.

#### 내 PC에서 뭘로 돌려야 하나 — `scripts/check_env.py`

**가장 쉬운 방법: `scripts/check_env.bat` 더블클릭.**

터미널에서 돌린다면 — **Git Bash 에서는 경로에 `/`(슬래시)를 쓰세요.**
`\`는 Git Bash 가 이스케이프 문자로 먹어서 `.venvScriptspython: command not found` 가 납니다.

```bash
# Git Bash (MINGW64)
.venv/Scripts/python scripts/check_env.py

# PowerShell / cmd
.venv\Scripts\python scripts\check_env.py

# Linux · mac
.venv/bin/python scripts/check_env.py
```
CPU·GPU·RAM, CTranslate2/torch가 실제로 보는 것, 이미 받아 둔 모델, Ollama 상태를 찍고
**이 PC에 맞는 `.env` 값을 그대로 출력**합니다. 추측 대신 이걸 먼저 돌리세요.

전사 속도 손잡이(전부 `.env`, `0`이면 자동):

| 값 | 효과 |
|---|---|
| `WHISPER_MODEL` | **가장 큰 손잡이.** CPU면 `deepdml/faster-whisper-large-v3-turbo-ct2` 또는 `medium` |
| `WHISPER_BEAM_SIZE` | 비우면 CPU는 greedy(1). CPU에서 빔 5는 1.5~2배 느립니다 |
| `WHISPER_BATCH_SIZE` | `8` 권장. VAD로 자른 구간을 묶어 처리(faster-whisper 1.1+) |
| `WHISPER_CPU_THREADS` | 물리 코어 수를 넣으면 대개 가장 빠릅니다 |

#### 로컬 LLM이 느릴 때 — `scripts/bench_llm.py`

```bash
python scripts/bench_llm.py --threads 0,4,8,12
```
회의록 한 건은 15분 넘게 걸려 설정을 바꿔가며 시험할 수가 없습니다. 이 스크립트는
**짧은 생성 한 번(수십 초)**으로 `tok/s`를 재고 스레드 수를 비교합니다.

기준: qwen2.5:3b 가 요즘 노트북 CPU에서 **8~15 tok/s**면 정상입니다.
**2~3 tok/s면 뭔가 잘못된 것**이고, 모델을 더 줄여도 해결되지 않습니다. 이 순서로 보세요:

1. **전원 모드** — 설정 → 시스템 → 전원 → *최고의 성능*. 절전이면 노트북 CPU 클럭이 반토막 납니다
2. **여유 RAM** — 80%를 넘으면 모델이 스왑됩니다. `wsl --shutdown` 으로 Docker/Vexa를 내리세요
   (녹음본 처리에는 필요 없습니다)
3. **Ollama 설치 위치** — `where ollama`. WSL 안에만 있으면 Windows 네이티브로 다시 설치하는 편이 빠릅니다
4. **스레드** — 위 표에서 가장 빠른 값을 `.env` 의 `OLLAMA_NUM_THREAD` 에

#### GPU인데 `cublas64_12.dll is not found` 로 죽을 때

CTranslate2(faster-whisper)가 CUDA 12용 cuBLAS·cuDNN 을 못 찾는 경우입니다.
**가상환경에 설치만 하면 됩니다 — PATH 는 건드리지 마세요.** 코드가 알아서 찾아 등록합니다.

```bash
uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

`scripts/check_env.py` 가 이 DLL 을 찾았는지 알려줍니다. GPU를 잠시 포기하려면 `.env` 에
`WHISPER_DEVICE=cpu`.

> **NVIDIA GPU가 있는데 `CUDA 장치 0개`로 나오면** 그게 최대 병목입니다.
> CPU→GPU는 10배 이상이라 다른 튜닝을 전부 합친 것보다 큽니다. 진단 스크립트가 설치 명령을 알려줍니다.

회의록(LLM) 단계도 CPU에서는 느립니다. `.env`에서:

```bash
OLLAMA_MODEL=qwen2.5:7b     # CPU면 14b는 비현실적 (3b도 고려)
LLM_TERM_CORRECTION=0       # 용어 교정 단계를 꺼서 LLM 작업량을 절반으로
OLLAMA_TIMEOUT=1800         # 기다릴 수 있으면 늘리기
```

> **전사는 회의록보다 먼저 저장됩니다.** LLM이 실패해도 `.transcript.json`은 남으니
> 오래 걸린 전사를 다시 할 필요가 없습니다 — 목록의 `▶` 버튼으로 회의록만 다시 만드세요.

> **전사 JSON·회의록 MD 업로드(`🎙`/`📄` 탭)는 별개**다. 이쪽은 요청 본문을 통째로 메모리에
> 올리는 JSON 경로라 상한이 5MB(`MINUTES_MAX_TEXT_UPLOAD_MB`)로 따로 잡혀 있다.

---

## 4. Vexa 봇 셀프호스팅 (외부 API 발급 불필요)

봇 참석·전사는 **Vexa 셀프호스팅**이 담당. Vexa clone·STT·키 발급까지 **자동 스크립트**로 처리한다.

> ⚠️ **사전(1회 수동, 자동화 불가):** Windows는 **WSL2 + Docker Desktop** 설치 후,
> Docker Desktop → **Settings → Resources → WSL Integration 에서 Ubuntu 토글 ON**(이거 안 켜면 `docker: not found`).
> Docker Desktop(WSL2)은 포트를 Windows `localhost`로 노출 → 대시보드는 Windows에서 `localhost:18056`에 붙는다.

### 자동 설치 (권장)
Docker Desktop 실행 + WSL Integration ON 상태에서:
- **`scripts/install_vexa_cpu.bat` 더블클릭** (GPU면 WSL에서 `bash scripts/install_vexa_cpu.sh --gpu`)
- 스크립트가 자동으로: **Vexa clone → STT 기동(CPU면 `docker-compose.cpu.yml`) → 전사연결(`deploy/compose/.env`)
  → 봇 이미지 pull → admin으로 영구 API 키 발급 → 우리 `.env`에 `VEXA_API_URL`/`VEXA_API_KEY` 자동 기입 + mock 해제**
- 끝나면 대시보드 재시작 → 실제 모드 → **Google Meet** 링크로 참석

상세·트러블슈팅: [`docs/VEXA_CPU_INSTALL.md`](./docs/VEXA_CPU_INSTALL.md) · GPU/WSL2 [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md)

### 실전 핵심 (실제로 겪은 함정)
- **API 키는 admin으로 발급(영구)**: `POST :18057/admin/users/{id}/tokens?scopes=bot,tx` → DB 저장.
  **`make down`/`make all` 재실행 금지**(키가 새로 발급돼 churn). 설정 반영은 `docker compose up -d`만.
- **전사설정은 `~/vexa/deploy/compose/.env`**(우리 대시보드 `.env` 아님):
  `TRANSCRIPTION_SERVICE_URL=http://host.docker.internal:8083` + `TRANSCRIPTION_SERVICE_TOKEN`(STT의 `API_TOKEN`과 동일).
- **봇 이미지** `vexaai/vexa-bot:v012` 없으면 502 → `docker pull vexaai/vexa-bot:v012`(또는 `make bot`).
- **플랫폼**: `google_meet` 가장 안정적. **`teams.live.com`(개인 Teams)은 봇을 조기 evict** → `segments_captured:0`. 첫 테스트는 Google Meet + 실제 발화로.
- 요구사양 **Docker ≥ v26, 8 vCPU / 16 GB**. GPU 없으면 전사 CPU 모드(느림) — 저사양이면 mock/파일 파이프라인 권장.
- 지원 플랫폼: `google_meet` · `zoom`(링크 필요) · `teams` · `jitsi`(링크 필요) — 대시보드가 링크에서 자동 인식.

## 5. n8n 자동화 (선택)

무인 오케스트레이션이 필요할 때만. `minutes.server`를 띄워두고 n8n은 **HTTP Request 노드**로 호출한다
(Execute Command 노드는 n8n 2.8.4 미지원 → HTTP가 정본. `workflows/vexa_meeting_http.json` import).

```bash
export MINUTES_SERVER_URL="http://127.0.0.1:8900" && n8n start   # minutes.server 는 3절대로 기동해 둔다
curl -X POST http://localhost:5678/webhook/bot-dispatch -H "Content-Type: application/json" \
  -d '{"url":"https://meet.google.com/abc-defg-hij"}'            # 봇 참석 웹훅
```

---

## 6. 개발 / 구조 / 문서

```bash
python -m pytest -q                     # 172개 (mock으로 네트워크·GPU·오디오 없이 e2e)
python -m ruff check src tests scripts  # 린트
```
> `prompts/*.md`와 `glossary.yaml`은 **실제 회의 결과를 보며 사람이 직접 튜닝**한다 — 이게 진짜 IP.

### 회의록 문체 — 개조식

회의록은 **개조식(명사형 종결 · 마침표 없음)**으로 나온다. 공공기관 보고서 문체다.

```
논의 내용
### AIOT 사업자료 작성
기현 수석·전략계획실 협업으로 진행함
TTA 협업을 위해 8월 초까지 준비 필요
실증 구역은 부산시 전체를 포함하여 작성함
```

- 어체는 `prompts/03_integrate_minutes.md`의 **문체 섹션**이 만든다 — 바꾸려면 여기를 고친다.
- 마침표 제거는 `style.py`가 **코드로 한 번 더 보장**한다(로컬 소형 LLM이 지시를 흘려도
  구두점만은 어긋나지 않게). 소수점·버전·날짜의 점(`1.5억`, `v3.1`, `2026-08-20`)은 건드리지 않는다.
- 서술체로 되돌리려면 프롬프트를 고치고 `MINUTES_STRIP_PERIODS=0`.

```
src/minutes/
├── generate·chain·schema·render.py     # Phase 1 회의록 생성
├── providers/ (ollama·gemini·mock)     # LLM 어댑터
├── transcribe.py · asr/                # Phase 2 전사(audio·whisper·groq·diarize·merge)
├── pipeline.py · watch.py              # Phase 3 결합 + 폴더 무인
├── bot.py · vexa/                       # Phase 4 봇(client·convert·meeting_url·mock)
├── server.py · _webui.py                # HTTP 서비스 + 웹 대시보드(자동회의록·녹음본업로드·파일관리)
├── audio_formats.py                     # 지원 오디오 확장자(업로드 검증·watch 공용)
└── config.py · glossary.py             # 설정·용어집
scripts/  check_env.py · check_env.bat              # 환경 진단 + 권장 .env 출력
          bench_llm.py                              # 로컬 LLM tok/s 측정(스레드 비교)
          start_windows.bat · start_windows_cpu.bat   # 원클릭 실행(GPU/CPU)
          install_vexa_cpu.bat · install_vexa_cpu.sh  # Vexa 자동 설치(키까지 .env 기입)
prompts/ · glossary.yaml · workflows/ · docs/ · docker/
```

| 문서 | 내용 |
|---|---|
| [`docs/VEXA_CPU_INSTALL.md`](./docs/VEXA_CPU_INSTALL.md) | **회사 PC(무 GPU) Vexa 자동설치·CPU 모드·트러블슈팅** |
| [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) | 집 GPU PC 셋업 + Vexa 참석 원리 + 필수 모델 |
| [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md) | Vexa 셀프호스팅(Docker/WSL2/GPU) |
| [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md) | 최종 클라우드/Vexa 아키텍처 + 육하원칙 TDL |
| [`docs/RUN_24_7.md`](./docs/RUN_24_7.md) · [`docs/MANUAL_SETUP.md`](./docs/MANUAL_SETUP.md) | 24/7 무인 운영 · 수동 준비 |
