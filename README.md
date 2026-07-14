# Meeting-Recorder — AI 회의록 자동화 시스템

온라인 회의 오디오 → **전사 / 화자분리** → **LLM 회의록(JSON + Markdown)** 자동 생성.
n8n이 오케스트레이션하고 Vexa 봇이 회의에 자동 참석한다.

> 프로젝트의 상세 설계·규칙·현재 상태는 [`CLAUDE.md`](./CLAUDE.md)를 참고.

## 스택 (전부 무료 / 오픈소스)

- **오케스트레이션**: n8n Community Edition (Docker)
- **전사**: faster-whisper large-v3 (로컬) / Groq (fallback)
- **화자분리**: pyannote.audio 3.1
- **LLM**: Ollama(로컬, 민감회의) / Gemini Flash(내부회의) — 어댑터 교체 가능
- **봇 참석**: Vexa (셀프호스팅)
- **언어 / 의존성**: Python 3.11 / uv

## 보안등급 분기 (B2G 공공사업)

| 프로파일 | LLM | 용도 |
|---|---|---|
| `secure` | Ollama (로컬) | 민감 회의 |
| `internal` | Gemini (클라우드) | 내부 회의 |

## 구현 로드맵 (역순 구축)

- **Phase 1** — 회의록 생성기 (텍스트 → 회의록)  ← 다음 단계
- **Phase 2** — 전사 엔진 (오디오 → 화자라벨 텍스트)
- **Phase 3** — 결합 + n8n 워크플로우
- **Phase 4** — Vexa 봇 참석 연동

## 설치 (준비)

```bash
cp .env.example .env               # 키 값 채우기
uv venv
uv pip install -e ".[dev]"         # 패키지(editable) + 개발 의존성

# 테스트 (네트워크 없이 MockProvider로 e2e)
.venv/bin/python -m pytest -q
```

## 사용법 (목표)

```bash
# Phase 1: 회의록 생성 (✅ 구현됨)
python -m minutes.generate --input transcript.json --profile internal   # Gemini(클라우드)
python -m minutes.generate --input transcript.json --profile secure     # Ollama(로컬)

# 오프라인 스모크 테스트 (실제 LLM 호출 없이 파이프라인 확인)
LLM_PROVIDER=mock python -m minutes.generate --input tests/fixtures/sample_transcript.json --profile secure

# Phase 2: 전사 (✅ 구현됨) — 오디오 → 화자라벨 전사 JSON(= Phase 1 입력)
python -m minutes.transcribe --audio meeting.m4a           # GPU 있으면 faster-whisper, 없으면 Groq
uv pip install -e ".[transcribe]"                          # 전사 실사용 시 (torch/pyannote/faster-whisper)

# 전체 체인 오프라인 데모 (실제 LLM/모델 없이)
ASR_ENGINE=mock DIARIZER=mock python -m minutes.transcribe --audio meeting.m4a
LLM_PROVIDER=mock python -m minutes.generate --input meeting.transcript.json --profile secure

# CER(전사 품질) 측정
python scripts/cer.py --ref reference.txt --hyp meeting.transcript.json

# Phase 3: 결합 파이프라인 (오디오 → 회의록 한 번에)
python -m minutes.pipeline --audio meeting.m4a --profile secure

# Phase 3: n8n 오케스트레이션 (Docker)
docker compose up -d --build         # n8n(:5678) + ollama(:11434)
# → ./data/inbox 에 오디오 투입 → ./data/out/{secure,internal}/ 에 회의록

# Phase 4: Vexa 봇 (회의 자동 참석 → 내장 전사 → 회의록)
python -m minutes.bot request  --platform google_meet --meeting abc-defg-hij   # 봇 참석
python -m minutes.bot ingest   --platform google_meet --meeting abc-defg-hij --profile internal
docker compose --profile vexa up -d  # Vexa 서비스 포함 기동(이미지 교체 필요)

# Vexa 내장 전사 vs 우리 Phase 2 전사 A/B 비교
python scripts/ab_transcribe.py --vexa mtg.vexa.json --ours mtg.transcript.json --ref ref.txt
```

## n8n 오케스트레이션 (Phase 3)

`workflows/meeting_minutes.json` 을 n8n에 import. 흐름:
폴더감시/웹훅 → 전사 → 회의록 생성 → **보안등급 분기(secure/internal)** → Markdown 배포 → 실패 시 재시도·알림.
자세한 내용은 [`workflows/README.md`](./workflows/README.md).

## 진행 상태

- ✅ **Phase 1** — 회의록 생성기: 3단 LLM 체인(용어교정→청크요약→통합) + pydantic 검증 + Ollama/Gemini 어댑터.
- ✅ **Phase 2** — 전사 엔진: ffmpeg→faster-whisper(Groq 폴백)→pyannote 화자분리→병합. CER 스크립트 포함.
- ✅ **Phase 3** — 결합 파이프라인 + n8n 워크플로우 + docker-compose(n8n/ollama).
- ✅ **Phase 4** — Vexa 봇 참석 연동 + 봇 dispatch/ingest CLI + Vexa↔Phase2 A/B 비교.
