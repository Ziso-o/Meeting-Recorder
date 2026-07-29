# Meeting-Recorder — AI 회의록 자동화 시스템

온라인 회의 오디오 → **전사 / 화자분리** → **LLM 회의록(JSON + Markdown)** 자동 생성.
**n8n**이 오케스트레이션하고 **Vexa 봇**이 회의에 자동 참석한다.

> 상세 설계·규칙은 [`CLAUDE.md`](./CLAUDE.md) · 최종 클라우드 로드맵은
> [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md) · 집 GPU PC 셋업은
> [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) 참고.

## 스택 (전부 무료 / 오픈소스)

- **오케스트레이션**: n8n Community Edition — **HTTP Request 노드**로 우리 서비스 호출
  (Execute Command 미의존 → n8n 버전 무관, Docker/네이티브/클라우드 공용)
- **전사**: faster-whisper large-v3 (로컬 GPU) / 실시간은 Vexa 내장 STT
- **화자분리**: pyannote.audio 3.1 (파일) / Vexa 내장(실시간)
- **LLM**: Ollama(로컬) — 회의록 작성 필수 / Gemini(선택, internal)
- **봇 참석**: **Vexa 셀프호스팅**(`make all`, 게이트웨이 :18056) — Cloud 발급 불필요
- **언어 / 의존성**: Python 3.11 / uv

## 보안등급 분기 (B2G 공공사업)

| 프로파일 | LLM | 전사 | 용도 |
|---|---|---|---|
| `secure` | Ollama (로컬) | faster-whisper (로컬 GPU) | **민감 회의** — 외부 유출 없음 |
| `internal` | Gemini (클라우드) | Groq (클라우드) | 내부 회의 |

## 진행 상태

**Phase 1–4 코드 완료 + 오케스트레이션 검증(mock).** pytest 51개 통과.

- ✅ **Phase 1** — 회의록 생성기: 3단 LLM 체인(용어교정→청크요약→통합) + pydantic 검증 + Ollama/Gemini 어댑터
- ✅ **Phase 2** — 전사 엔진: ffmpeg→faster-whisper→pyannote 화자분리→병합 + CER 스크립트 (실오디오 검증)
- ✅ **Phase 3** — 결합 파이프라인 + `minutes.watch`(폴더 무인) + n8n 워크플로우
- ✅ **Phase 4** — Vexa 봇 연동 + **회의 링크 자동 파싱**("링크만 보내면 참가") + A/B 비교
- ✅ **n8n 오케스트레이션(HTTP)** — 웹훅→`minutes.server`→회의록 생성까지 **mock e2e 검증 완료**
- 🔜 **실물 전환** — 집 GPU PC에 Vexa 셀프호스팅 + Ollama(실제 봇 참가) → 이후 Vultr 이관

> 상세 TDL: [`TODO.md`](./TODO.md)

---

# 0. 시작하기 (Git Bash)

## 0-1. 코드 받기 — clone(최초) / pull(업데이트)

Windows는 **Git Bash(MINGW64)** 기준. 브랜치: `claude/meeting-minutes-automation-07augh`.

```bash
# ── 최초 1회: 클론 ──
cd ~
git clone -b claude/meeting-minutes-automation-07augh https://github.com/Ziso-o/Meeting-Recorder.git
cd Meeting-Recorder

# ── 이후: 최신화(pull) ──
cd ~/Meeting-Recorder
git pull origin claude/meeting-minutes-automation-07augh
```

> - 명령·경로는 **슬래시 `/`** 로 쓴다(Git Bash). venv 파이썬은 `.venv/Scripts/python`(Windows).
> - **집 GPU PC 최초 셋업**은 clone 후 한 줄이면 된다:
>   ```bash
>   bash scripts/home_pc_setup.sh   # venv·설치·ollama·.env·pytest 자동
>   ```
> - 다른 PC에 로컬 `.env`(untracked)가 이미 있어 pull이 거부되면: `mv .env .env.bak` 후 다시 pull.

## 0-2. 원커맨드 로컬 실행 (권장 — `uv` 없어도 됨)

`scripts/run_local.sh`(Linux/macOS/**Windows Git-Bash**) 또는 `scripts/run_local.ps1`(PowerShell)이
가상환경 생성 → 의존성 설치(`uv` 없으면 `python -m venv`로 폴백) → `.env` 준비 → 실행까지 처리한다.

```bash
# 오프라인 데모 (엔진/키/GPU 불필요 — 배관만 확인, 가볍게)
bash scripts/run_local.sh --minimal --mock

# 완전 로컬 파이프라인 (Ollama + faster-whisper, 클라우드 0)
bash scripts/run_local.sh --audio 회의.m4a --profile secure

# 설치/셋업만 (사전점검: ffmpeg·Ollama 모델 확인)
bash scripts/run_local.sh --setup-only
```
```powershell
# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Audio 회의.m4a -Profile secure
```
> Windows Git-Bash에서 `uv: command not found` / `No module named 'minutes'` 가 났다면,
> **패키지가 venv에 설치되지 않은 것**이다. 위 스크립트가 이를 해결한다(직접 하려면 아래 수동 절차).

---

# 1. 빠른 시작 (수동, 키·GPU 없이 배관 확인)

스크립트 없이 직접 하려면 — **네트워크·GPU·오디오 없이** mock으로 전체 파이프라인을 확인:

```bash
# uv가 있으면:
uv venv && uv pip install -e ".[dev]"
# uv가 없으면 (Windows Git-Bash 포함):
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"    # Windows (.venv/Scripts)
# .venv/bin/python -m pip install -e ".[dev]"       # Linux/macOS (.venv/bin)

.venv/Scripts/python -m pytest -q                   # 51 passed 여야 정상 (Windows)

# 오프라인 전체 체인 (transcribe → generate) — 실제 모델/키 불필요
touch demo.m4a
ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock \
  .venv/Scripts/python -m minutes.pipeline --audio demo.m4a --profile secure
```

> ⚠️ 핵심: `python -m minutes.*` 는 **패키지를 venv에 `-e` 설치한 뒤**, 그 **venv의 python**으로 실행해야 한다.
> 시스템 python으로 실행하면 `No module named 'minutes'` 가 난다.
> 이후 예시의 `python`은 venv python(`.venv/Scripts/python` 또는 `.venv/bin/python`)을 뜻한다.

---

# 2. 실제 구동 준비

## 2-1. 환경 변수

```bash
cp .env.example .env      # 편집기로 값 채우기
mkdir -p data/inbox data/out
```

| 키 | 언제 필요 | 발급처 |
|---|---|---|
| `GEMINI_API_KEY` | `internal` 회의록 생성 | https://aistudio.google.com/apikey |
| `GROQ_API_KEY` | GPU 없이 전사(폴백) | https://console.groq.com/keys |
| `HF_TOKEN` | 화자분리(pyannote) | https://huggingface.co/settings/tokens (+게이트 모델 동의) |
| `VEXA_API_URL` / `VEXA_API_KEY` | Vexa 봇(Phase 4) | Vexa 스택 배포 후 |
| `VEXA_BOT_NAME` | 봇 표시명 | (기본 `회의록봇`) |

> 전체 발급/동의 절차는 [`docs/MANUAL_SETUP.md`](./docs/MANUAL_SETUP.md) 참고.

## 2-2. 엔진 선택 환경변수

| 변수 | 값 | 의미 |
|---|---|---|
| `ASR_ENGINE` | `auto`(기본)·`faster-whisper`·`groq`·`mock` | 전사 엔진. auto=GPU 있으면 로컬, 없으면 Groq |
| `DIARIZER` | `auto`(기본)·`mock`·`off` | 화자분리. off=단일 화자 처리(HF 토큰 불필요) |
| `LLM_PROVIDER` | (미설정=프로파일 따름)·`mock` | 프로파일 기본값 override |
| `VEXA_CLIENT` | (미설정=실제)·`mock` | Vexa 오프라인 테스트 |

## 2-3. 전사 실사용 시 추가 설치 (로컬 faster-whisper/pyannote)

```bash
uv pip install -e ".[transcribe]"   # torch + faster-whisper + pyannote (무겁고 GPU 권장)
sudo apt install ffmpeg             # 또는 brew install ffmpeg (로컬 실행 시)
```

---

# 3. CLI 사용법 (실제 구동)

각 단계는 CLI로 독립 실행 가능하다. n8n은 이 CLI(또는 `minutes.server`)를 **호출만** 한다.
`python`은 venv 파이썬(`.venv/Scripts/python` 또는 `.venv/bin/python`)을 뜻한다.

```bash
# ── 회의록 생성: 전사 텍스트 → 회의록 (minutes.generate) ──
#   profile: internal=Gemini(클라우드) / secure=로컬 Ollama
#   입력 JSON: [{speaker,start,end,text}] 또는 {"meta":{...},"segments":[...]}
#   산출물: <stem>.minutes.json + <stem>.minutes.md
python -m minutes.generate --input meeting.transcript.json --profile secure

# ── 전사: 오디오 → 화자라벨 전사 JSON (minutes.transcribe) ──
#   GPU 있으면 faster-whisper, 없으면 GROQ_API_KEY로 폴백. 산출물: <stem>.transcript.json
python -m minutes.transcribe --audio meeting.m4a --title "착수회의" --date 2026-07-14

# ── 결합 파이프라인: 오디오 → 회의록 한 번에 (minutes.pipeline) ──
#   위 transcribe + generate 를 한 번에. 산출물: transcript.json + minutes.json/.md
python -m minutes.pipeline --audio meeting.m4a --profile secure

# ── 무인 자동화: 폴더 감시 (minutes.watch) ──
#   data/incoming 에 오디오 넣으면 자동 처리 → data/out, 처리분 data/done. n8n 불필요.
python -m minutes.watch --profile secure          # 상시 감시(Ctrl+C 종료)
python -m minutes.watch --once --profile secure   # 1회 스캔(작업 스케줄러/크론용)

# ── Vexa 봇 제어 (minutes.bot) ──
#   request: 링크만 주면 platform/ID 자동 파싱 후 봇 참석 (Meet/Zoom/Teams/Jitsi)
python -m minutes.bot request    --url "https://meet.google.com/abc-defg-hij"
python -m minutes.bot request    --platform google_meet --meeting abc-defg-hij   # 직접 지정도 가능
python -m minutes.bot transcript --platform google_meet --meeting abc-defg-hij --out mtg   # 전사만 저장
python -m minutes.bot ingest     --platform google_meet --meeting abc-defg-hij --profile secure --out mtg  # 전사→회의록
python -m minutes.bot stop       --platform google_meet --meeting abc-defg-hij   # 봇 종료

# ── 품질 측정 스크립트 ──
python scripts/cer.py --ref reference.txt --hyp meeting.transcript.json                 # 전사 CER
python scripts/ab_transcribe.py --vexa mtg.vexa.json --ours mtg.transcript.json --ref ref.txt  # Vexa vs Phase2 A/B

# ── n8n용 HTTP 서비스 (minutes.server) — 계속 켜둠 ──
#   엔드포인트: GET /health, POST /bot/dispatch|/bot/stop|/ingest|/pipeline
python -m minutes.server                          # 127.0.0.1:8900 (MINUTES_SERVER_PORT로 변경)
```

> 오프라인(키·GPU 없이 배관 확인): 위 명령 앞에
> `ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock VEXA_CLIENT=mock` 를 붙인다.

---

# 3.5. n8n 연동 (HTTP 서비스 — ✅ 검증된 정본, n8n 버전 무관)

n8n의 Execute Command 노드는 최신 버전에서 미지원(2.8.4 확인)이라, **HTTP 서비스**를
띄우고 n8n은 **HTTP Request 노드**로 호출한다. (Docker·네이티브·클라우드 공용)

```bash
# 1) HTTP 서비스 기동 (mock 개발: 회사 노트북 / 실구동: 집 GPU PC는 mock 제거)
VEXA_CLIENT=mock LLM_PROVIDER=mock python -m minutes.server     # 127.0.0.1:8900
#   GET /health, POST /bot/dispatch|/bot/stop|/ingest|/pipeline

# 2) n8n에 workflows/vexa_meeting_http.json import → Active
#    n8n 실행 전: export MINUTES_SERVER_URL="http://127.0.0.1:8900"

# 3-a) 봇 참석 — 회의 링크만 웹훅으로 (자동 파싱 → Vexa 참가)
curl -X POST http://localhost:5678/webhook/bot-dispatch \
  -H "Content-Type: application/json" -d '{"url":"https://meet.google.com/abc-defg-hij"}'

# 3-b) 회의 종료 → 전사 인제스트 → 회의록
curl -X POST http://localhost:5678/webhook/meeting-end \
  -H "Content-Type: application/json" -d '{"meetingId":"abc-defg-hij","profile":"secure"}'
# → 서비스가 Vexa 전사 → 회의록을 data/out/secure/ 에 생성
```
> 서비스 단독 확인: `curl -X POST http://127.0.0.1:8900/ingest -H "Content-Type: application/json" -d '{"meetingId":"testid","profile":"secure"}'`
> 흐름: **웹훅(트리거) → HTTP Request → `minutes.server` → Vexa REST → 봇 참가/전사 → LLM 회의록**.

---

# 4. n8n 로컬 실행 (Docker Execute Command 방식 — 참고용 보존)

CLI를 손으로 돌리는 대신, n8n이 **폴더 감시/웹훅 → 전사 → 생성 → 보안분기 → 배포**를 자동화한다.

## 4-1. 스택 기동

```bash
cp .env.example .env && mkdir -p data/inbox data/out   # (아직 안 했다면)
docker compose up -d --build
# 서비스: n8n → http://localhost:5678 , ollama → http://localhost:11434
```
- `docker/Dockerfile.n8n`이 n8n 이미지에 **python3 + ffmpeg + minutes 패키지**를 통합한다
  (n8n의 Execute Command 노드가 `$MINUTES_PY -m minutes.*` 를 직접 호출).
- 기본 이미지는 경량(전사는 Groq 사용). **민감회의 로컬 전사**가 필요하면:
  ```bash
  docker compose build --build-arg INSTALL_TRANSCRIBE=1 n8n   # + NVIDIA 런타임 설정
  # .env: ASR_ENGINE=faster-whisper
  ```

## 4-2. Ollama 모델 내려받기 (secure 프로파일에서 회의록 생성용)

```bash
docker exec -it mr_ollama ollama pull qwen2.5:14b     # .env의 OLLAMA_MODEL과 일치
```

## 4-3. 워크플로우 import (n8n UI — 최초 1회)

1. http://localhost:5678 접속 → 최초 관리자 계정 생성
2. **Workflows → Import from File**
   - `workflows/meeting_minutes.json` (오디오 파일 기반)
   - `workflows/vexa_meeting.json` (Vexa 봇 기반, Phase 4)
3. **Settings → Error Workflow** 를 해당 워크플로우로 지정 (실패 알림 노드 동작 조건)
4. 워크플로우 우측 상단 **Active** 토글 ON
5. (선택) `.env`에 `ALERT_WEBHOOK_URL`(Slack/Teams incoming webhook) 지정 → 완료/실패 알림

## 4-4. 실행 방법 2가지

**(a) 폴더 감시** — `data/inbox`에 오디오를 넣으면 자동 처리
```bash
cp 회의녹음.m4a          data/inbox/    # → internal 로 처리
cp secure_민감회의.m4a   data/inbox/    # 파일명에 'secure' 포함 → secure(로컬 LLM)
# 결과: data/out/internal/*.minutes.md  또는  data/out/secure/*.minutes.md
```

**(b) 웹훅** — 외부 트리거로 시작
```bash
curl -X POST http://localhost:5678/webhook/meeting-audio \
  -H "Content-Type: application/json" \
  -d '{"audioPath":"/data/inbox/회의녹음.m4a"}'
```

## 4-5. 워크플로우 흐름

```
폴더감시(/data/inbox) / 웹훅
  → Config(경로 파싱 + 보안 프로파일 결정)
  → 전사(minutes.transcribe)   ┐ 각 노드 실패 시 3회 재시도
  → 회의록 생성(minutes.generate)┘
  → 보안등급 IF 분기
       ├ secure   → /data/out/secure   배포
       └ internal → /data/out/internal 배포 → 완료 알림
  (실패 시) 에러 트리거 → 실패 알림
```
- **보안분기 규칙**: 경로/파일명에 `secure` 포함 → 로컬 LLM(Ollama) / 그 외 → 클라우드(Gemini)
- 자세한 노드 설명은 [`workflows/README.md`](./workflows/README.md).

---

# 5. Vexa 봇 자동 참석 (셀프호스팅 — 외부 API 발급 불필요)

Vexa는 **공식 레포를 셀프호스팅**한다. Vexa Cloud 계정/토큰 불필요 —
`make all`이 로컬에서 API 키(`vxa_...`)를 자동 생성한다.

```bash
git clone https://github.com/Vexa-ai/vexa.git && cd vexa
make all      # 전체 스택(게이트웨이 :18056, UI :13000). 출력의 vxa_ 키를 .env 에
make bot      # 회의 봇
```
- 요구사양: Docker ≥ v26, 8 vCPU / 16 GB RAM. 전사 GPU 유닛까지 셀프호스팅하면 **완전 air-gapped**(B2G).
- 지원 플랫폼: `google_meet` · `zoom` · `teams` · `jitsi`.
- 상세: [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md).

```bash
# 봇 참석 — 링크만 (CLI). n8n 없이도 가능
python -m minutes.bot request --url "https://meet.google.com/abc-defg-hij"
```

---

# 6. 개발 / 테스트

```bash
.venv/bin/python -m pytest -q                    # 51개 (mock으로 네트워크·GPU·오디오 없이 e2e)
.venv/bin/python -m ruff check src tests scripts # 린트
```
- 오프라인 데모: `ASR_ENGINE=mock DIARIZER=mock`, `LLM_PROVIDER=mock`, `VEXA_CLIENT=mock`
- 프롬프트 파일(`prompts/*.md`)과 `glossary.yaml`은 **실제 회의 결과를 보며 사람이 직접 튜닝**한다
  — 이게 이 시스템의 진짜 IP다.

## 디렉토리 구조

```
src/minutes/
├── generate.py / chain.py / schema.py / render.py   # Phase 1 회의록 생성
├── providers/ (ollama·gemini·mock)                  # LLM 어댑터
├── transcribe.py / asr/ (audio·whisper·groq·diarize·merge)  # Phase 2 전사
├── pipeline.py / watch.py                           # Phase 3 결합 + 폴더 무인
├── bot.py / vexa/ (client·convert·meeting_url·mock) # Phase 4 봇 + 링크 파서
├── server.py                                        # n8n용 HTTP 서비스
├── config.py / glossary.py                          # 설정·용어집
prompts/ (01·02·03.md)   glossary.yaml
scripts/ (cer·ab_transcribe·run_local·run_watch·home_pc_setup)
workflows/ (meeting_minutes·vexa_meeting·vexa_meeting_http·_local.json)
docs/ (TARGET_CLOUD_TDL·HOME_PC_RUNBOOK·VEXA_SELFHOST_WINDOWS·RUN_24_7·MANUAL_SETUP·STACK_MANUAL_TDL)
docker-compose.yml   docker/ (Dockerfile.n8n)
```

## 문서 가이드

| 문서 | 내용 |
|---|---|
| [`docs/TARGET_CLOUD_TDL.md`](./docs/TARGET_CLOUD_TDL.md) | 최종 클라우드/Vexa 아키텍처 + 육하원칙 TDL |
| [`docs/HOME_PC_RUNBOOK.md`](./docs/HOME_PC_RUNBOOK.md) | 집 GPU PC 셋업→n8n + Vexa 참석 원리 + 필수 모델 |
| [`docs/VEXA_SELFHOST_WINDOWS.md`](./docs/VEXA_SELFHOST_WINDOWS.md) | Vexa 셀프호스팅(Docker/WSL2/GPU) |
| [`docs/RUN_24_7.md`](./docs/RUN_24_7.md) | 24/7 무인 운영(작업 스케줄러) |
| [`docs/MANUAL_SETUP.md`](./docs/MANUAL_SETUP.md) · [`docs/STACK_MANUAL_TDL.md`](./docs/STACK_MANUAL_TDL.md) | 수동 준비 작업 · 스택별 TDL |
