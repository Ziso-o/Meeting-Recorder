# 수동 작업 가이드 (Manual Setup)

이 시스템은 코드/자동화는 완성되어 있으나, **사람이 직접 해야만 하는 작업**이 있다.
크게 ① 외부 계정·키 발급 ② 도메인 지식 주입(용어집·프롬프트) ③ 인프라 기동 ④ 실데이터 검증 이다.

> 왜 수동인가: 외부 서비스 가입·게이트 모델 동의·실제 사업 용어·GPU 서버 운영·회의 오디오는
> 코드가 대신 만들 수 없다. AI가 만든 것을 **읽고 검증**하는 사람의 역할이 남는다(Loop-Engineering).

---

## 0. 우선순위 한눈에

| 순위 | 작업 | 없으면 |
|---|---|---|
| 🔴 필수 | `.env` 생성 + LLM 키(또는 로컬 Ollama) | 회의록 생성 불가 |
| 🔴 필수 | 전사 경로 확보(Groq 키 **또는** GPU+HF 토큰) | 오디오 전사 불가 |
| 🟡 품질 | `glossary.yaml` 실제 용어로 교체 | 고유명사 오인식 |
| 🟡 품질 | `prompts/*.md` 실회의로 튜닝 | 회의록 품질 저하 |
| 🟢 운영 | Docker 기동 + n8n 워크플로우 import | 수동 CLI로는 동작 |
| 🟢 운영 | Vexa 스택 배포 | 봇 자동참석 불가(수동 오디오는 가능) |

---

## 1. 외부 계정·API 키 발급 (🔴 필수)

`.env`를 만들고 아래 값을 채운다.
```bash
cp .env.example .env
```

### 1-1. LLM (회의록 생성) — 프로파일별 택1
- **internal(클라우드, 무료)** → **Gemini API 키**
  1. https://aistudio.google.com/apikey 접속(구글 계정)
  2. *Create API key* → 키 복사 → `.env`의 `GEMINI_API_KEY=` 에 붙여넣기
  3. 무료티어로 충분(회의록 생성은 호출량 적음)
- **secure(로컬, 민감회의)** → **Ollama** (키 불필요, 로컬 구동)
  - 아래 3-2 참조. 회의 내용이 외부로 나가지 않음.

### 1-2. 전사(ASR) — GPU 유무로 택1
- **GPU 없음 → Groq(클라우드, 무료)**
  1. https://console.groq.com/keys (가입)
  2. 키 생성 → `.env`의 `GROQ_API_KEY=`
  3. `.env`에 `ASR_ENGINE=groq`
  - ⚠️ 오디오가 Groq로 전송됨 → **민감회의 부적합**. 민감회의는 아래 GPU 경로.
- **GPU 있음 → faster-whisper(로컬)**
  1. `.env`에 `ASR_ENGINE=faster-whisper`
  2. `uv pip install -e ".[transcribe]"` (torch/pyannote/faster-whisper)

### 1-3. 화자분리(pyannote) — HF 토큰 (전사 시 필요)
1. https://huggingface.co/settings/tokens → *New token*(read) 발급 → `.env`의 `HF_TOKEN=`
2. **게이트 모델 사용 조건 동의**(로그인 상태에서 각 페이지 접속 → 약관 수락):
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. 화자분리가 불필요하거나 토큰이 없으면 `.env`에 `DIARIZER=off` (단일 화자로 처리)

### 1-4. Vexa (Phase 4, 봇 자동참석) — 선택
- Vexa 스택 배포 후 발급되는 API 키를 `.env`의 `VEXA_API_KEY=`, 주소를 `VEXA_API_URL=` 에.
- 봇 표시명: `VEXA_BOT_NAME=회의록봇` (회의 참석자 목록에 보임)
- 봇 없이 **녹음 파일만** 처리하려면 Vexa 불필요(Phase 2 경로 사용).

---

## 2. 도메인 지식 주입 (🟡 품질 — 이게 이 시스템의 진짜 IP)

### 2-1. `glossary.yaml` 실제 용어로 교체
현재는 **예시 항목**이다. 실제 사업명/기관명/인명/약어로 바꾼다.
```yaml
projects:      ["실제 사업 정식명칭"]
organizations: ["발주기관", "수행사"]
acronyms:
  - term: "정답표기"
    aliases: ["STT가 자주 틀리는 표기1", "표기2"]
people:        ["실제 참석자/직책"]
```
- 효과: ① 전사 `initial_prompt` 주입(인식률↑) ② 회의록 용어교정 단계에서 오인식 정정.

### 2-2. `prompts/*.md` 튜닝 (실제 회의 결과를 보며)
- `01_term_correction.md` / `02_chunk_summary.md` / `03_integrate_minutes.md`
- **작업 방식**: 실제 회의 1건을 돌려 → 산출된 `.minutes.md`를 사람이 검토 →
  누락·오류 패턴을 프롬프트 규칙으로 추가. (AI에게 맡기지 말고 사람이 손볼 것)
- 최대 실패모드는 **결정/액션 누락** — 이미 "추측 금지, 없으면 빈 배열" 규칙이 있으나
  실제 회의체 말투에 맞게 결정/논의 구분 기준을 다듬는다.

---

## 3. 인프라 기동 (🟢 운영)

### 3-1. Docker 스택
```bash
mkdir -p data/inbox data/out           # 입출력 폴더
docker compose up -d --build           # n8n(:5678) + ollama(:11434)
# (Vexa 포함) docker compose --profile vexa up -d
```
- `docker/Dockerfile.n8n`은 기본 경량(전사는 Groq). **secure 로컬 전사**가 필요하면:
  ```bash
  docker compose build --build-arg INSTALL_TRANSCRIBE=1 n8n   # + GPU 런타임 설정
  ```

### 3-2. Ollama 모델 내려받기 (secure 프로파일)
```bash
docker exec -it mr_ollama ollama pull qwen2.5:14b     # .env의 OLLAMA_MODEL과 일치
```
- 14B 모델은 대략 VRAM/RAM 10GB+ 필요. 사양이 낮으면 `qwen2.5:7b` 등으로 `.env` 조정.

### 3-3. n8n 워크플로우 import (UI 수동 작업)
1. http://localhost:5678 접속(최초 계정 생성)
2. **Workflows → Import from File** → `workflows/meeting_minutes.json`
   (Phase 4는 `workflows/vexa_meeting.json` 도)
3. **Settings → Error Workflow** 를 해당 워크플로우로 지정(에러 알림 노드 동작 조건)
4. 워크플로우 **Activate**
5. (선택) 실패 알림용 `ALERT_WEBHOOK_URL`(Slack/Teams incoming webhook)을 `.env`에

### 3-4. ffmpeg (로컬에서 CLI 직접 실행 시)
- Docker 사용 시 이미지에 포함 → 불필요.
- 로컬 실행 시: `apt install ffmpeg` / `brew install ffmpeg`.

### 3-5. Vexa 스택(선택, Phase 4)
- 공식 배포 권장: https://github.com/Vexa-ai/vexa (다중 컨테이너 스택)
- 본 레포 `docker-compose.yml`의 `vexa` 서비스 `image`(`VEXA_IMAGE`)를 실제 게이트웨이로 교체.

---

## 4. 실데이터 검증 (🟢 — "수동으로 5회 성공" 원칙)

자동 루프를 신뢰하기 전, 같은 작업을 **손으로 몇 번 성공**시켜 패턴을 검증한다.

```bash
# (a) 오프라인 배관 확인 — 키 없이
ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock \
  python -m minutes.pipeline --audio dummy.m4a --profile secure

# (b) 실제 오디오 1건 — 내부회의(클라우드)
python -m minutes.pipeline --audio 회의.m4a --profile internal --title "..." --date 2026-07-14

# (c) 산출물 사람이 검토: 회의.minutes.md 의 결정/액션 정확성 확인
# (d) 오류 패턴 → glossary.yaml / prompts 로 반영 후 (b) 재실행
```
- 전사 품질 수치화: `python scripts/cer.py --ref 정답.txt --hyp 회의.transcript.json`
- Vexa 도입 시 A/B: `python scripts/ab_transcribe.py --vexa v.json --ours o.transcript.json --ref 정답.txt`

---

## 5. 보안 체크리스트 (B2G 민감회의)

- [ ] 민감회의는 `--profile secure` (LLM=로컬 Ollama)
- [ ] 민감회의 전사는 `ASR_ENGINE=faster-whisper`(로컬 GPU). **Groq(클라우드) 금지**
- [ ] `.env`는 git에 커밋되지 않음(`.gitignore` 확인 완료). 키 유출 주의
- [ ] Vexa/n8n을 외부 노출 시 인증·방화벽 적용
- [ ] 산출물 `data/out/secure/` 접근권한 관리
