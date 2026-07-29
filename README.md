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
| 오케스트레이션 | **n8n** — HTTP Request로 `minutes.server` 호출 (n8n 버전 무관) |
| 런타임 | Python 3.11 / uv |

## 보안등급 분기 (B2G)

- **`secure`** = 로컬 Ollama + 로컬 전사 → **외부 유출 0** (민감 회의)
- **`internal`** = Gemini 등 클라우드 (내부 회의)

## 진행 상태

Phase 1–4 코드 + **n8n HTTP 오케스트레이션 mock e2e 검증 완료** (pytest 51개).
🔜 집 GPU PC에서 실제 Vexa 봇 참가로 전환 → 이후 Vultr 이관.

---

## 1. 설치 (Git Bash 기준)

```bash
# ── 코드 받기 (브랜치: claude/meeting-minutes-automation-07augh) ──
git clone -b claude/meeting-minutes-automation-07augh https://github.com/Ziso-o/Meeting-Recorder.git
cd Meeting-Recorder
git pull origin claude/meeting-minutes-automation-07augh      # 이후 최신화는 이 줄

# ── 셋업 (택1) ──
bash scripts/home_pc_setup.sh           # 집 GPU PC: venv·설치·ollama·.env·pytest 자동
bash scripts/run_local.sh --setup-only  # 또는 원커맨드 셋업(uv 없어도 python -m venv 폴백)

# ── 수동 설치 ──
uv venv && uv pip install -e ".[transcribe]"     # uv 없으면: python -m venv .venv && \
#   .venv/Scripts/python -m pip install -e ".[transcribe]"   # (Windows / Linux는 .venv/bin/python)
.venv/Scripts/python -m pytest -q                # 51 passed 확인
```

> - **⚠️ 실행 전 venv 활성화** (안 하면 시스템 python이라 `No module named 'minutes'`):
>   ```bash
>   source .venv/Scripts/activate     # Windows Git-Bash   (Linux·mac: source .venv/bin/activate)
>   ```
>   활성화하면 프롬프트에 `(.venv)` 표시되고, 이후 아래 예시의 `python` 이 그대로 동작한다.
>   (활성화 대신 매번 `.venv/Scripts/python -m ...` 로 명시해도 됨. 새 터미널마다 다시 활성화)
> - Git Bash는 경로에 **슬래시 `/`**. `[transcribe]` = torch/faster-whisper/pyannote(무거움, **파일 전사**용).
>   Vexa 봇 경로만이면 `[dev]`로 충분. 파일 전사엔 **ffmpeg** 필요(`winget install Gyan.FFmpeg`/`apt install ffmpeg`).

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

## 3. CLI 한눈에

`python` = venv 파이썬(`.venv/Scripts/python` 또는 `.venv/bin/python`).
**오프라인 확인**은 명령 앞에 `ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock VEXA_CLIENT=mock` 를 붙인다.

```bash
# ── 오디오 → 회의록 한 번에 (파일 경로) ──────────────────────────────
#   profile: secure=로컬 Ollama / internal=Gemini. 산출물: <stem>.transcript.json + .minutes.json/.md
python -m minutes.pipeline   --audio meeting.m4a --profile secure

#   낱개로도 가능:
python -m minutes.transcribe --audio meeting.m4a                      # 오디오 → 전사 JSON
python -m minutes.generate   --input meeting.transcript.json --profile secure   # 전사 → 회의록

# ── 폴더 감시 무인 자동화 (n8n 불필요) ───────────────────────────────
#   data/incoming 에 오디오 넣으면 자동 처리 → data/out, 처리분 data/done
python -m minutes.watch --profile secure          # 상시(Ctrl+C 종료)
python -m minutes.watch --once --profile secure   # 1회 스캔(작업 스케줄러/크론)

# ── Vexa 봇 (실시간 회의) ────────────────────────────────────────────
python -m minutes.bot request  --url "https://meet.google.com/abc-defg-hij"   # 링크만 → 자동 참석
python -m minutes.bot ingest   --platform google_meet --meeting abc-defg-hij --profile secure --out mtg  # 전사→회의록
python -m minutes.bot stop     --platform google_meet --meeting abc-defg-hij  # 봇 종료

# ── n8n용 HTTP 서비스 (켜두면 n8n이 호출) ────────────────────────────
python -m minutes.server        # 127.0.0.1:8900  (GET /health, POST /bot/dispatch|/ingest|/pipeline …)

# ── 품질 측정 ────────────────────────────────────────────────────────
python scripts/cer.py --ref reference.txt --hyp meeting.transcript.json           # 전사 CER
python scripts/ab_transcribe.py --vexa v.json --ours meeting.transcript.json      # Vexa vs 우리 전사 A/B
```

---

## 4. n8n 자동화 (HTTP 방식 — ✅ 검증된 정본)

n8n 최신 버전은 Execute Command 노드를 미지원(2.8.4 확인) → **HTTP 서비스**를 띄우고
n8n은 **HTTP Request 노드**로 호출한다. (Docker·네이티브·클라우드 공용)

```bash
# 1) 서비스 기동 (터미널 A, 켜둠). 개발이면 mock, 실구동이면 mock 제거
VEXA_CLIENT=mock LLM_PROVIDER=mock python -m minutes.server        # 127.0.0.1:8900

# 2) n8n 기동 (터미널 B, 켜둠) 후 workflows/vexa_meeting_http.json import → Active
export MINUTES_SERVER_URL="http://127.0.0.1:8900" && n8n start     # http://localhost:5678

# 3) 웹훅 (터미널 C, 한 줄씩)
curl -X POST http://localhost:5678/webhook/bot-dispatch -H "Content-Type: application/json" -d '{"url":"https://meet.google.com/abc-defg-hij"}'   # 봇 참석
curl -X POST http://localhost:5678/webhook/meeting-end  -H "Content-Type: application/json" -d '{"meetingId":"abc-defg-hij","profile":"secure"}'  # 종료→회의록
```

> 흐름: **웹훅(트리거) → HTTP Request → `minutes.server` → Vexa REST → 봇 참가/전사 → LLM 회의록**.
> 서비스 단독 테스트: `curl -X POST http://127.0.0.1:8900/ingest -H "Content-Type: application/json" -d '{"meetingId":"testid","profile":"secure"}'`
> 참고: Docker+Execute Command 방식(`workflows/vexa_meeting.json`, `docker-compose.yml`)은 보존만 — 정본은 HTTP.

## 5. Vexa 봇 셀프호스팅 (외부 API 발급 불필요)

`make all`이 로컬에서 API 키(`vxa_...`)를 자동 생성한다. Vexa Cloud 계정/토큰 불필요.

```bash
git clone https://github.com/Vexa-ai/vexa.git && cd vexa
make all      # 전체 스택(게이트웨이 :18056, UI :13000). 출력의 vxa_ 키를 우리 .env 에
make bot      # 회의 봇
```

- 요구사양: **Docker ≥ v26, 8 vCPU / 16 GB RAM**. 전사 GPU 유닛까지 셀프호스팅 시 **완전 air-gapped**(B2G).
- 지원 플랫폼: `google_meet` · `zoom` · `teams` · `jitsi`. 상세 [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md).

---

## 6. 개발 / 구조 / 문서

```bash
python -m pytest -q                     # 51개 (mock으로 네트워크·GPU·오디오 없이 e2e)
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
├── server.py                            # n8n용 HTTP 서비스
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
