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
git clone -b claude/meeting-minutes-automation-07augh https://github.com/Ziso-o/Meeting-Recorder.git
cd Meeting-Recorder

# ── 셋업 (택1, 자동) ────────────────────────────────────────
bash scripts/home_pc_setup.sh            # 집 GPU PC: venv·설치·ollama·.env·pytest 자동
bash scripts/run_local.sh --setup-only   # uv 없어도 python -m venv 폴백

# ── 수동 설치 ───────────────────────────────────────────────
uv venv && uv pip install -e ".[transcribe]"    # uv 없으면 python -m venv .venv 후
#   .venv/Scripts/python -m pip install -e ".[transcribe]"   (Windows / Linux는 .venv/bin/python)
.venv/Scripts/python -m pytest -q               # 73 passed 확인
```

> `[transcribe]` = torch/faster-whisper/pyannote(**파일 전사**용, 무거움). Vexa 봇만이면 `[dev]`로 충분.
> 파일 전사엔 **ffmpeg** 필요(`winget install Gyan.FFmpeg` / `apt install ffmpeg`).

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
git pull origin claude/meeting-minutes-automation-07augh
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
| 📡 상태 모니터링 | 서비스 / Vexa / 실행 봇 + 흉내·실제 모드 |
| 🎙 녹취파일 | 전사 → **화자별 말풍선** · **업로드/삭제/이름변경** |
| 📄 회의록 | 회의록 **마크다운 렌더** · **업로드/삭제/이름변경** |

- 좌측 **흉내↔실제 스위치**로 mock/실제 전환(재시작 불필요). 실제 모드는 `.env`에 Vexa 주소·키 필요.
- **자동 회의록**: "참석시키기" 한 번 → 회의가 끝나 봇이 나가면 워처가 **전사→회의록을 자동 생성**(수동 개입 불필요).

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
python -m pytest -q                     # 73개 (mock으로 네트워크·GPU·오디오 없이 e2e)
python -m ruff check src tests scripts  # 린트
```
> `prompts/*.md`와 `glossary.yaml`은 **실제 회의 결과를 보며 사람이 직접 튜닝**한다 — 이게 진짜 IP.

```
src/minutes/
├── generate·chain·schema·render.py     # Phase 1 회의록 생성
├── providers/ (ollama·gemini·mock)     # LLM 어댑터
├── transcribe.py · asr/                # Phase 2 전사(audio·whisper·groq·diarize·merge)
├── pipeline.py · watch.py              # Phase 3 결합 + 폴더 무인
├── bot.py · vexa/                       # Phase 4 봇(client·convert·meeting_url·mock)
├── server.py · _webui.py                # HTTP 서비스 + 웹 대시보드(자동회의록·봇이름·파일관리)
└── config.py · glossary.py             # 설정·용어집
scripts/  start_windows.bat · start_windows_cpu.bat   # 원클릭 실행(GPU/CPU)
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
