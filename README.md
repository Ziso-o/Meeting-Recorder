# Meeting-Recorder — AI 회의록 자동화 시스템

온라인 회의 → **봇 참석 / 전사·화자분리 → LLM 회의록(JSON + Markdown)** 자동 생성.
**Vexa 봇**이 회의에 참석하고 **n8n**이 오케스트레이션한다.

> 설계·규칙 [`CLAUDE.md`](./CLAUDE.md) · 최종 로드맵 [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md)
> · 집 GPU PC 셋업 [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) · TDL [`TODO.md`](./TODO.md)

## 스택 (전부 무료 / 오픈소스)

| 역할 | 도구 |
|---|---|
| 봇 참석 | **Vexa 셀프호스팅** (게이트웨이 :18056, Cloud 발급 불필요) |
| 전사·화자분리 | 실시간 = Vexa 내장 / 파일 = faster-whisper large-v3 + pyannote 3.1 |
| LLM 회의록 | **Ollama**(로컬, 필수) / Gemini(선택, internal) |
| 웹 대시보드 | **`minutes.server`** — 링크 붙여넣기로 봇 참석·상태·녹취·회의록 (추가 의존성 0) |
| 오케스트레이션 | **n8n** — HTTP Request로 `minutes.server` 호출 (n8n 버전 무관) |
| 런타임 | Python 3.11 / uv |

## 보안등급 분기 (B2G)

- **`secure`** = 로컬 Ollama + 로컬 전사 → **외부 유출 0** (민감 회의)
- **`internal`** = Gemini 등 클라우드 (내부 회의)

## 진행 상태

Phase 1–4 코드 + **웹 대시보드(흉내↔실제 토글)** + **n8n HTTP 오케스트레이션 mock e2e 검증 완료** (pytest 62개).
🔜 집 GPU PC에서 실제 Vexa 봇 참가로 전환 → 이후 Vultr 이관.

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
.venv/Scripts/python -m pytest -q               # 62 passed 확인
```

> `[transcribe]` = torch/faster-whisper/pyannote(**파일 전사**용, 무거움). Vexa 봇만이면 `[dev]`로 충분.
> 파일 전사엔 **ffmpeg** 필요(`winget install Gyan.FFmpeg` / `apt install ffmpeg`).

## 2. 설정 (`.env`)

```bash
cp .env.example .env      # 아래 [필수] 키만 채우면 됨 (나머지는 기본값 그대로)
```

| 키 | 용도 |
|---|---|
| `HF_TOKEN` | pyannote 화자분리(파일). huggingface.co/settings/tokens + 게이트 모델 동의 |
| `VEXA_API_KEY` | Vexa `make all`이 출력하는 `vxa_...` (로컬 자동생성, 외부 발급 아님) |
| `GEMINI_API_KEY` | (선택) internal 클라우드 LLM. 없으면 로컬 Ollama로 폴백 |

> **개발용 mock**: `ASR_ENGINE`·`DIARIZER`·`LLM_PROVIDER`·`VEXA_CLIENT` 를 `mock` 으로 두면
> 키·GPU·오디오 없이 전 구간 배관 확인 가능. 전체 키/토글은 `.env.example` 참고.

---

## 3. 실행

```bash
# ── 코드 받기(최신화) ───────────────────────────────────────
git pull origin claude/meeting-minutes-automation-07augh

# ── 구동: 웹 대시보드 ───────────────────────────────────────
#   이후 참석·상태·녹취·회의록 + 흉내↔실제 전환까지 전부 브라우저에서 입력·실행
.venv/Scripts/python -m minutes.server        # → http://127.0.0.1:8900/   (Linux·mac: .venv/bin/python)
```

> - venv 활성화(`source .venv/Scripts/activate`) 안 하면 시스템 python이라 `No module named 'minutes'` — 위처럼 `.venv/Scripts/python` 로 명시하거나 활성화 후 `python` 사용.
> - 흉내↔실제 전환은 대시보드 **좌측 스위치**로. (실제 모드는 `.env`에 Vexa 주소·키 필요)
> - 종료는 `Ctrl+C`. 외부(다른 PC/폰) 접속은 `MINUTES_SERVER_HOST=0.0.0.0` (신뢰 네트워크·B2G 정책 확인 후).
> - 스크립트 자동화가 필요하면 CLI(`minutes.pipeline` · `bot` · `watch`)도 그대로 있음.
> - **재부팅 후 원클릭**: 집 PC(Vexa 셀프호스팅)라면 `scripts/start_windows.bat` 더블클릭 →
>   Docker·Vexa·STT·대시보드까지 한 번에 켜짐(설치·키는 그대로 유지되므로 재설정 불필요).

**웹 대시보드 4개 뷰**

| 좌측 네비 | 하는 일 |
|---|---|
| ▶ 회의 참석 | 링크 붙여넣기 → 봇 참석 (Meet/Zoom/Teams/Jitsi 자동 인식) · 봇 종료 |
| 📡 상태 모니터링 | 서비스 / Vexa / 실행 봇 + **흉내·실제 모드** 표시 |
| 🎙 녹취파일 | 전사 목록 → **화자별 말풍선** |
| 📄 회의록 | 생성된 회의록 **마크다운 렌더** |

---

## 4. Vexa 봇 셀프호스팅 (외부 API 발급 불필요)

`make all`이 로컬에서 API 키(`vxa_...`)를 자동 생성한다. Vexa Cloud 계정/토큰 불필요.

> ⚠️ **Windows는 Git Bash가 아니라 WSL2(우분투) 터미널에서.** Vexa는 Docker 다중 컨테이너
> 스택이라 Git Bash엔 `make`도 없고 실행도 안 된다. **Docker Desktop(WSL2 엔진) + make 필요.**
> **GPU 없는 저사양 PC면 Vexa를 켜지 말고 mock 유지**(내장 STT가 GPU 사용).

```bash
# WSL2(우분투) 터미널에서:
sudo apt update && sudo apt install -y make git   # WSL엔 make 설치
git clone https://github.com/Vexa-ai/vexa.git && cd vexa
make all      # 전체 스택(게이트웨이 :18056, UI :13000). 출력의 vxa_ 키를 우리 .env 에
make bot      # 회의 봇
```

- 요구사양: **Docker ≥ v26, 8 vCPU / 16 GB RAM**. 전사 GPU 유닛까지 셀프호스팅 시 **완전 air-gapped**(B2G).
- Docker Desktop(WSL2)은 포트를 Windows `localhost`로 노출 → 대시보드는 Windows에서 그대로 `localhost:18056`에 붙는다.
- 지원 플랫폼: `google_meet` · `zoom` · `teams` · `jitsi`. 상세(사전준비·GPU·트러블슈팅) [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md).

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
python -m pytest -q                     # 62개 (mock으로 네트워크·GPU·오디오 없이 e2e)
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
├── server.py · _webui.py                # HTTP 서비스 + 웹 대시보드(토스풍 UI)
└── config.py · glossary.py             # 설정·용어집
prompts/ · glossary.yaml · scripts/ · workflows/ · docs/ · docker/
```

| 문서 | 내용 |
|---|---|
| [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) | 집 GPU PC 셋업→n8n + Vexa 참석 원리 + 필수 모델 |
| [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md) | Vexa 셀프호스팅(Docker/WSL2/GPU) |
| [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md) | 최종 클라우드/Vexa 아키텍처 + 육하원칙 TDL |
| [`docs/RUN_24_7.md`](./docs/RUN_24_7.md) | 24/7 무인 운영(작업 스케줄러) |
| [`docs/MANUAL_SETUP.md`](./docs/MANUAL_SETUP.md) · [`docs/STACK_MANUAL_TDL.md`](./docs/STACK_MANUAL_TDL.md) | 수동 준비 · 스택별 TDL |
