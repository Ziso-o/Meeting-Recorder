# 집 GPU PC 런북 — 세팅 확인부터 n8n까지 + Vexa 참석 원리 + 필수 모델

> 회사 노트북에서 **mock 오케스트레이션(웹훅→n8n→서비스→회의록)까지 검증 완료.**
> 이 문서는 그걸 **집 GPU PC에서 실물(Vexa 실참석 + 실 LLM)로 전환**하는 순서다.
> ⚠️ n8n 워크플로(`vexa_meeting_http.json`)는 **안 바꾼다.** 서비스가 보는 것만 실물로.

---

# A. 집 PC 해야 할 일 (순서대로)

### A-0. 세팅 확인 (하드웨어/드라이버)
- [ ] NVIDIA 최신 드라이버(지포스 50번대 = WSL2 CUDA 지원 버전)
- [ ] `nvidia-smi` 로 GPU 인식 확인 (Windows PowerShell)
- [ ] **WSL2** 설치: 관리자 PowerShell → `wsl --install` → 재부팅
- [ ] **Docker Desktop** 설치 → Settings ▸ "Use WSL2 based engine" ON
- [ ] WSL 터미널에서 `nvidia-smi` 로 **WSL2 GPU 패스스루** 확인

### A-1. 레포 + 파이썬
- [ ] `git clone`(또는 pull) → **한 폴더로 통일**(회사와 헷갈리지 않게)
- [ ] `uv venv` → `uv pip install -e ".[transcribe]"`
      (봇 경로만 쓸 거면 `.[dev]`만으로도 서비스는 돎 — C절 참고)
- [ ] `.venv/Scripts/python -m pytest -q` → 통과 확인

### A-2. LLM (Ollama) — **필수**
- [ ] Ollama 설치(https://ollama.com) → 자동실행 확인
- [ ] `ollama pull qwen2.5:14b` (GPU면 14b 권장, 여유되면 32b)
- [ ] `ollama list` 로 확인

### A-3. `.env` (실값 + GPU 프리셋)
```
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
# GPU 프리셋 (파일경로/전사 쓸 때)
ASR_ENGINE=faster-whisper
WHISPER_MODEL=large-v3
DIARIZER=pyannote
HF_TOKEN=hf_새토큰
# Vexa 실값 (A-4에서 확인한 값)
VEXA_API_URL=http://localhost:8056
VEXA_API_KEY=<발급키>
VEXA_BOT_NAME=회의록봇
```
> ⚠️ mock 3종(`VEXA_CLIENT`/`LLM_PROVIDER`/`ASR_ENGINE=mock`)은 **넣지 않는다.**

### A-4. Vexa 셀프호스팅 — **필수(봇 경로)**
- [ ] `git clone https://github.com/Vexa-ai/vexa` → 공식 README대로 기동(WSL2 GPU)
- [ ] **게이트웨이 주소/포트 확인** → `.env` `VEXA_API_URL`에 반영
- [ ] **API 키 발급**(Vexa 관리자 API로 사용자·토큰 생성) → `.env` `VEXA_API_KEY`
- 상세: `docs/VEXA_SELFHOST_WINDOWS.md`

### A-5. HTTP 서비스 (실값으로)
```bash
# mock 없이! .env의 실값을 읽는다
.venv/Scripts/python -m minutes.server        # 127.0.0.1:8900
```
- [ ] 다른 터미널에서 `curl :8900/health` → ok

### A-6. n8n
- [ ] `n8n start` 전에 `export MINUTES_SERVER_URL="http://127.0.0.1:8900"`
- [ ] `workflows/vexa_meeting_http.json` import → **Active**
- [ ] 실회의로 테스트(B절 흐름)

### A-7. 24/7 (선택)
- 전원 절전 끄기, `scripts/run_watch.bat`/서비스 상시화 → `docs/RUN_24_7.md`

---

# B. Vexa에게 "웹훅으로" 회의 참석시키는 원리 (이론)

## ⚠️ 오해 정리: 웹훅은 우리 트리거, Vexa 참석은 REST API
**웹훅 2개는 우리(n8n) 트리거지, Vexa가 웹훅으로 회의에 들어가는 게 아니다.**
Vexa는 **REST API 호출(`POST /bots`)** 을 받으면 **봇(헤드리스 브라우저)** 을 띄워 회의에 입장한다.

```
[누군가 회의 시작] → n8n 웹훅 /webhook/bot-dispatch {platform, meetingId}
      → 우리 서비스 /bot/dispatch
      → Vexa REST  POST /bots {platform, native_meeting_id, bot_name}
      → Vexa 봇(Chromium)이 그 회의 URL로 '참가자'로 입장 → 오디오 캡처 → 실시간 STT
[회의 종료]     → n8n 웹훅 /webhook/meeting-end {platform, meetingId, profile}
      → 우리 서비스 /ingest → Vexa GET /transcripts/{platform}/{id} → 회의록 생성
```
- 즉 우리는 **platform + 회의ID만** 올바르게 넘기면 되고, "회의에 어떻게 들어가는가"는 **Vexa 봇이 처리**한다.
- `bot-dispatch` 웹훅을 **누가 쏘나?** → 사람이 수동으로, 또는 **캘린더 연동**(n8n이 Google Calendar/Outlook 감시 → 회의 시작 시각에 자동 dispatch). 후자는 선택 자동화.

## 플랫폼별 차이 (Zoom / Teams / Meet)
`POST /bots`의 `platform`과 `native_meeting_id` 형식이 플랫폼마다 다르다. **우리는 변환 안 하고 그대로 전달** → 형식만 맞춰 웹훅 body에 넣으면 된다.

| 플랫폼 | platform 값(예) | native_meeting_id (예) | 난이도/주의 |
|---|---|---|---|
| Google Meet | `google_meet` | 회의코드 `abc-defg-hij` (meet.google.com/**abc-defg-hij**) | 상대적으로 쉬움(코드만) |
| Zoom | `zoom` | 회의번호 `12345678901` (+ passcode 필요할 수 있음) | 암호/대기실/봇차단 정책 주의 |
| Microsoft Teams | `teams` | Teams 회의 링크/ID(길고 복잡, threadId 포함) | 조직 게스트 정책·링크 파싱 주의 |

> ⚠️ **Vexa가 실제로 어떤 플랫폼을 지원하는지는 버전마다 다르다.** Google Meet은 안정적으로 지원하는 편이고, **Zoom/Teams 지원 여부·형식은 반드시 Vexa 배포본 문서에서 확인**할 것. (우리 코드는 어떤 platform 문자열이든 그대로 넘김)
> 공통 난점: 봇이 **대기실 승인**을 받아야 입장되는 경우가 많다. 회의 주최자가 봇 입장을 허용해야 한다.

## 웹훅 body 예시(플랫폼별)
```bash
# Google Meet
curl -X POST http://localhost:5678/webhook/bot-dispatch -H "Content-Type: application/json" -d "{\"platform\":\"google_meet\",\"meetingId\":\"abc-defg-hij\"}"
# Zoom
curl ... -d "{\"platform\":\"zoom\",\"meetingId\":\"12345678901\"}"
# Teams
curl ... -d "{\"platform\":\"teams\",\"meetingId\":\"<teams-meeting-id>\"}"
```

---

# C. 필수 구성 AI 모델 (무엇이 반드시 필요한가)

| 모델/역할 | 필수 여부 | 어디서 관리 | 비고 |
|---|---|---|---|
| **LLM (회의록 작성)** | **✅ 절대 필수** | 우리 Ollama (`qwen2.5:14b`) | Vexa/Whisper는 전사만. **회의록은 LLM이 만든다.** 없으면 회의록 불가 |
| **Vexa 내장 STT (Whisper)** | ✅ 필수(봇 경로) | **Vexa 스택이 자체 관리** | 봇이 캡처한 오디오를 실시간 전사. GPU 사용. 우리가 따로 pull 안 함 |
| Vexa 내장 화자분리 | ✅ 필수(봇 경로) | Vexa 스택 | 실시간 화자 라벨 |
| faster-whisper large-v3 | ⬜ 선택 | 우리 `[transcribe]` | **녹음파일 경로**용. 봇만 쓰면 불필요 |
| pyannote 3.1 | ⬜ 선택 | 우리 `[transcribe]`, HF_TOKEN | **녹음파일 화자분리**용. 봇만 쓰면 불필요 |

## 핵심 결론
- **봇 경로(실시간 회의)만** 할 거면 필수는 **① Vexa 스택(내장 STT/화자분리 포함) + ② Ollama LLM** 둘뿐.
  - 이때 우리 **HTTP 서비스는 `[transcribe]`(torch) 없이도 동작**한다 —
    `/ingest`는 "Vexa 전사 → LLM 회의록"이라 faster-whisper/pyannote를 **안 쓴다.**
- **녹음파일도 처리**하려면 그때 faster-whisper + pyannote(+HF_TOKEN)가 추가로 필요(`/pipeline` 경로).
- **어느 경우든 LLM(Ollama)은 필수.** 이게 빠지면 회의록 자체가 안 만들어진다.

> 정리: 집 PC에서 봇 자동화가 목표라면 → **Vexa 스택 + Ollama(qwen2.5:14b)** 를 먼저 확실히.
> faster-whisper/pyannote는 "녹음파일도 볼 때" 켜는 옵션.
