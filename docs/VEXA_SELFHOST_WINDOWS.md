# Vexa 셀프호스팅 셋업 (집 GPU PC) + 우리 스택 연결

> 목표: Vexa 봇이 실제 온라인 회의(Google Meet 등)에 참가 → STT/화자분리 →
> 우리 `minutes.bot ingest`로 회의록 생성. **mock 졸업 = 이 문서.**

## 0. 역할 분담 (회사 노트북 / 집 GPU PC)

| 머신 | 역할 | Vexa | LLM |
|---|---|---|---|
| **회사 저사양 노트북** | 코드/워크플로 **개발·플러밍** | `VEXA_CLIENT=mock` | `LLM_PROVIDER=mock` |
| **집 GPU PC(지포스 50번대)** | **실제 구동·검증** | 셀프호스팅(Docker) | Ollama(GPU) |

> ⚠️ **Vexa 내장 STT(whisperlive)는 GPU를 쓴다.** → 저사양 노트북에선 Vexa 실구동 불가.
> 노트북에서는 항상 mock으로 배관만 확인하고, **실제 Vexa는 집 GPU PC에서만** 세운다.

---

## 1. 집 GPU PC 사전 준비 (Windows)

- [ ] **NVIDIA 최신 드라이버**(지포스 50번대 = WSL2 CUDA 지원 버전 필수)
- [ ] **WSL2** 설치: PowerShell(관리자) → `wsl --install` → 재부팅
- [ ] **Docker Desktop** 설치 → Settings에서 **"Use WSL2 based engine"** 켜기
- [ ] **WSL2 GPU 확인**: WSL 터미널에서 `nvidia-smi` 로 GPU 인식 확인
- [ ] (권장) 여유 **Linux 머신/듀얼부팅**이 있으면 네이티브 Linux Docker가 GPU·안정성 면에서 더 쉬움

## 2. Vexa 스택 기동 (공식 레포)

Vexa는 다중 컨테이너 스택이다. (요구사양: **Docker ≥ v26**, 최소 **8 vCPU / 16 GB RAM**)

```bash
git clone https://github.com/Vexa-ai/vexa.git && cd vexa
make all      # 전체 Docker Compose 스택 기동
make bot      # 회의 봇 소스 빌드
```

- [ ] 스택 기동 성공 (컨테이너 healthy)
- [ ] **API 키 자동 생성 확인** — `make all` 완료 시 콘솔에 `API key : vxa_...` 출력.
      → **외부 발급 아님, 로컬 자체 생성.** 이 값을 우리 `.env` `VEXA_API_KEY`에 넣는다.
- [ ] 포트: **API 게이트웨이 `http://localhost:18056`**, 터미널 UI `http://localhost:13000`.
- [ ] **전사(STT) 방식 결정 (B2G 중요)**:
      - (a) vexa.ai/account **무료 전사 토큰** — 간편하나 오디오가 vexa 전사로 나감(민감회의 부적합 가능)
      - (b) **GPU 전사 유닛까지 셀프호스팅 = 완전 air-gapped** — 외부 0. **B2G/secure는 이쪽.**

## 3. 우리 스택 연결 (`.env`)

집 GPU PC의 `.env`에 Vexa 실값 + GPU 프리셋을 반영한다:
```
# --- Vexa (실값) ---
VEXA_API_URL=http://localhost:18056    # 게이트웨이 기본 포트 18056
VEXA_API_KEY=vxa_...                    # make all 이 출력한 값
VEXA_BOT_NAME=회의록봇

# --- GPU 프리셋 (집 PC) ---
ASR_ENGINE=faster-whisper
WHISPER_MODEL=large-v3
DIARIZER=pyannote
HF_TOKEN=<새로_발급한_HF_토큰>
OLLAMA_MODEL=qwen2.5:14b               # 먼저: ollama pull qwen2.5:14b
```
> `VEXA_CLIENT=mock` 은 **주석 처리/삭제**(실제 Vexa 사용).

## 4. 봇 참가 → 회의록 (우리 CLI로 검증)

```bash
# (1) 봇을 실제 회의에 참가시킨다. meeting=회의 URL의 코드(예: abc-defg-hij)
.venv/Scripts/python -m minutes.bot request --platform google_meet --meeting abc-defg-hij

# (2) 회의 중/후 전사 조회 (Vexa 내장 STT 결과)
.venv/Scripts/python -m minutes.bot transcript --platform google_meet --meeting abc-defg-hij --out mtg

# (3) 봇 종료
.venv/Scripts/python -m minutes.bot stop --platform google_meet --meeting abc-defg-hij

# (4) Vexa 전사 → 회의록 생성 (LLM은 집 PC Ollama)
.venv/Scripts/python -m minutes.bot ingest --platform google_meet --meeting abc-defg-hij --profile secure --out mtg
#  → mtg.transcript.json / mtg.minutes.json / mtg.minutes.md
```

- [ ] (1) 봇이 실제 회의 참석자 목록에 **`회의록봇`으로 등장** (mock 졸업 지점!)
- [ ] (2) 실제 발화가 화자별로 전사되어 조회됨
- [ ] (4) 회의록 `.minutes.md` 생성 + 결정/액션 정확도 확인

## 5. n8n 자동화 연결 (그다음)

`workflows/vexa_meeting.json`:
- `POST /webhook/bot-dispatch` `{platform, meetingId}` → 봇 참가
- `POST /webhook/meeting-end` `{meetingId, profile}` → `ingest` → 회의록 → 배포
- ⚠️ 이 워크플로는 도커 경로 전제 → **집 PC 네이티브용 `*_local.json` 수정본 필요**
  (요청 시 제작). n8n도 Docker 금지면 `npm i -g n8n` 네이티브로.

---

## 6. 트러블슈팅 / 흔한 함정

| 증상 | 원인 / 해결 |
|---|---|
| `nvidia-smi` WSL2에서 실패 | 드라이버 구버전 → 50번대 WSL2-CUDA 지원 드라이버로 업데이트 |
| Vexa STT 컨테이너 GPU 못 잡음 | Docker Desktop WSL2 엔진 + compose의 GPU 예약 설정 확인 |
| `minutes.bot`이 401/403 | `VEXA_API_KEY` 오류 → 관리자 API로 재발급, X-API-Key 확인 |
| `Connection refused` | `VEXA_API_URL` 포트 불일치 → 배포본 실제 포트로 수정 |
| 봇이 회의 입장 못 함 | 회의 플랫폼(platform) 값·회의 코드 형식 확인, Vexa 봇 권한/대기실 승인 |
| 회의록 결정/액션 누락 | 전사 품질 문제일 수 있음 → glossary 보강 / large-v3 확인 |

## 7. 참고

- Vexa 공식: https://github.com/Vexa-ai/vexa (배포·API·포트는 이 레포 기준이 정답)
- 우리 연결점: `src/minutes/vexa/client.py`(REST), `bot.py`(CLI), `.env`(VEXA_*)
- 엔드포인트(우리 클라이언트): `POST /bots`, `GET /transcripts/{platform}/{id}`,
  `DELETE /bots/{platform}/{id}`, `GET /bots/status` (X-API-Key 인증)
