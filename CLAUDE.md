# CLAUDE.md — AI 회의록 자동화 시스템

> 이 파일은 프로젝트의 **영구 메모리**다. 세션이 바뀌어도(`/clear` 후에도) 이 문맥은 유지된다.
> 에이전트는 잊어도 레포는 잊지 않는다 — 중요한 결정은 반드시 여기(또는 `STATE.md`)에 기록한다.

---

## 목표

온라인 회의 오디오 → **전사 / 화자분리** → **LLM 회의록(JSON + Markdown)** 자동 생성.
최종적으로 **n8n**이 오케스트레이션하고, **Vexa 봇**이 회의에 자동 참석한다.

---

## 스택 (전부 무료 / 오픈소스)

| 역할 | 도구 | 비고 |
|---|---|---|
| 오케스트레이션 | **n8n** Community Edition (Docker) | Phase 3 |
| 전사 | **faster-whisper** large-v3 (로컬) / **Groq** whisper-large-v3-turbo (fallback) | Phase 2 |
| 화자분리 | **pyannote.audio** 3.1 | HF 토큰 필요 |
| LLM | **Ollama**(로컬, 민감회의) / **Gemini Flash** 무료티어(내부회의) | 어댑터로 교체 가능 |
| 봇 참석 | **Vexa** (Apache-2.0, 셀프호스팅) | **Phase 4에서만** 도입 |
| 언어 / 의존성 | **Python 3.11** / **uv** | |

---

## 제약 (설계에 반드시 반영)

1. **보안등급 분기**: 회의는 **B2G 공공사업 회의**다. 민감 회의는 **로컬 LLM(Ollama)**, 내부 회의는 **클라우드 LLM(Gemini)**.
   보안 프로파일(`secure` / `internal`)을 **처음부터** 설계에 넣는다.
2. **CLI 독립 실행**: 각 단계는 CLI로 독립 실행 가능해야 한다. n8n은 이 CLI를 **호출만** 한다.
3. **언어**: 한국어 회의가 기본. 영어 혼용 회의도 처리.
4. **비밀정보**: 외부 API 키는 **`.env`로만**. 코드에 하드코딩 **금지**.

---

## 구현 순서 (역순 구축 — 반드시 이 순서를 지킬 것)

| Phase | 범위 | 상태 |
|---|---|---|
| **Phase 1** | 회의록 생성기 (텍스트 → 회의록). **가장 먼저.** | ✅ 완료 |
| **Phase 2** | 전사 엔진 (오디오 → 화자라벨 텍스트) | ✅ 완료 |
| **Phase 3** | 1+2 결합 + n8n 워크플로우 | ✅ 완료 |
| **Phase 4** | Vexa 봇 참석 연동 | ✅ 완료 |

> **각 Phase는 사용자가 명시적으로 지시할 때만 시작한다. 앞서가지 마라.**

---

## CLI 인터페이스 (목표 형태)

```bash
# Phase 1
python -m minutes.generate --input transcript.json --profile internal|secure

# Phase 2
python -m minutes.transcribe --audio meeting.m4a
```

---

## 작업 규칙 (Loop-Engineering 원칙)

1. **작업 시작 전 항상 plan을 먼저 제시하고 사용자 승인을 받는다.** (Plan Mode 습관)
2. **각 Phase가 끝나면 작업 Report를 작성**하고, 다음 Phase 진행 여부를 질문한다.
3. **메모리는 컨텍스트가 아니라 디스크에** — 중요한 결정/실패는 이 파일이나 `STATE.md`에 남긴다.
4. **정지조건은 관측 가능한 신호로** — "충분히 좋아 보임"이 아니라 `pytest` 통과 / 스키마 검증 통과.
5. **프롬프트 파일(`prompts/*.md`)은 이 시스템의 진짜 IP** — 실제 회의 결과를 보며 사람이 직접 튜닝한다.

---

## 디렉토리 구조

```
Meeting-Recorder/
├── CLAUDE.md              # 이 파일 (영구 메모리)
├── README.md
├── .env.example           # 키 목록 (값 없음)
├── .gitignore
├── pyproject.toml         # uv 프로젝트 (의존성은 각 Phase에서 추가)
├── src/minutes/
│   ├── __init__.py
│   ├── config.py          # 보안 프로파일 / 설정
│   ├── generate.py        # Phase 1: 회의록 생성기 CLI
│   ├── transcribe.py      # Phase 2: 전사 엔진 CLI
│   └── providers/         # LLM 어댑터 (Ollama / Gemini)
│       └── __init__.py
├── prompts/               # LLM 프롬프트 (사람이 직접 튜닝)
├── glossary.yaml          # 용어집 (사업명/기관명/기술약어)
├── tests/
│   └── fixtures/          # 샘플 전사 JSON
├── workflows/             # n8n export (Phase 3)
└── docker/                # docker-compose (Phase 3/4)
```

---

## 현재 상태

- **부트스트랩 완료**: CLAUDE.md + 디렉토리 스켈레톤.
- **Phase 1 완료**: 회의록 생성기 (3단 LLM 체인 + pydantic 검증 + 어댑터 + CLI). pytest 6개 통과.
  - `schema.py` 회의록 스키마 / `chain.py` 3단 체인(용어교정→청크요약→통합·1회 재시도)
  - `providers/` Ollama·Gemini·Mock 어댑터, `config.py` 프로파일→프로바이더 선택
  - `prompts/01·02·03.md` (사람이 튜닝할 IP), `glossary.py`, `render.py`(Markdown)
  - 실행: `python -m minutes.generate --input transcript.json --profile internal|secure`
  - 오프라인 검증: `LLM_PROVIDER=mock` 로 네트워크 없이 파이프라인 실행 가능
- **Phase 2 완료**: 전사 엔진 (오디오 → 화자라벨 텍스트). pytest 17개 통과.
  - `asr/audio.py` ffmpeg 16kHz mono / `asr/whisper_engine.py`(faster-whisper, initial_prompt에 glossary 주입) / `asr/groq_engine.py`(폴백)
  - `asr/diarize.py`(pyannote) / `asr/merge.py`(화자 배정+연속 병합 → Phase 1 스키마)
  - `asr/__init__.py` 팩토리: `ASR_ENGINE=auto`(GPU 있으면 faster-whisper, 없으면 Groq)|mock, `DIARIZER=auto|mock|off`
  - `scripts/cer.py` CER 측정. 실행: `python -m minutes.transcribe --audio meeting.m4a`
  - 오프라인 검증: `ASR_ENGINE=mock DIARIZER=mock` — transcribe→generate 전체 체인 확인됨
- **Phase 3 완료**: 결합 파이프라인 + n8n 오케스트레이션. pytest 20개 통과.
  - `pipeline.py`: 오디오→회의록 한 번에(`python -m minutes.pipeline --audio X --profile ...`)
  - `docker-compose.yml`(n8n + ollama) + `docker/Dockerfile.n8n`(n8n에 python+ffmpeg+CLI 통합)
  - `workflows/meeting_minutes.json`: 폴더감시/웹훅 → transcribe → generate → **보안등급 IF 분기** → Markdown 배포 → 실패 재시도(3회)·에러알림
  - 보안분기 규칙: 경로/파일명에 `secure` 포함 → 로컬 LLM(out/secure), 그 외 → 클라우드(out/internal)
- **Phase 4 완료**: Vexa 봇 참석 연동. pytest 26개 통과. **전 Phase 완료 🎉**
  - `vexa/client.py`(REST: dispatch/transcript/stop) + `vexa/convert.py`(Vexa전사→Segment) + `vexa/mock.py`
  - `bot.py` CLI: `request`/`stop`/`transcript`/`ingest`(Vexa전사→회의록). 봇명 `VEXA_BOT_NAME` config
  - `scripts/ab_transcribe.py`: Vexa 내장 전사 vs 우리 Phase 2 전사 A/B(세그먼트/화자/문자수 + CER)
  - `docker-compose.yml`: vexa 서비스(opt-in `--profile vexa`) 추가, n8n에 VEXA_* 주입
  - `workflows/vexa_meeting.json`: 봇 dispatch 웹훅 + 회의종료 웹훅 → ingest → 보안분기 → 배포/알림
  - 오프라인 검증: `VEXA_CLIENT=mock`

### MVP: 무료·로컬 정책 (2026-07, 코드에 반영됨)
- **제약**: 모든 엔진 무료 / 로컬 우선(클라우드 배포는 후순위). 상세 로드맵 `TODO.md`.
- `ASR_ENGINE=auto` → **항상 로컬 faster-whisper**(GPU 없으면 CPU). Groq는 명시 시에만(`resolve_asr_choice`).
- `internal` 프로파일: GEMINI_API_KEY 없으면 **로컬 Ollama로 폴백**(경고). secure는 항상 Ollama.
- `DIARIZER=auto` + HF_TOKEN 없음 → **화자분리 비활성**(단일 화자, 경고). 강제는 `DIARIZER=pyannote`.
- `.env.example`이 무료·로컬 프리셋(auto/medium/qwen2.5:7b). pytest 32개 통과.

### 세션 핸드오프 반영 (Cowork→브랜치, 2026-07)
- `SESSION_HANDOFF.md` 기준 정합화. Cowork 로컬 `main`(2a47d4c)과 이 브랜치는 별개 계보.
- 반영됨: `.env` 인라인 주석 파서(`_parse_env_value`), `pyproject` soundfile, `.gitignore`(*.bak/vexa),
  **`minutes.watch`**(폴더감시 자동 회의록, `--once` 크론모드). pytest 36개.
- **미반영(대기)**: `diarize.py` Windows 수정 4종(token=/soundfile 인메모리/DiarizeOutput/torchcodec 우회)
  — Cowork 로컬에만 존재. 사용자 원본 받아 반영 예정. 상세 `TODO.md` ★ 섹션.
- 무인 자동화는 **watch(1차, Docker 불필요)** → n8n은 **네이티브**(Docker 금지 정책).

### 개발 환경 메모
- `uv venv && uv pip install -e ".[dev]"` 후 `python -m minutes.generate` 사용(‑e 설치 필요).
- 무인 자동화: `python -m minutes.watch --profile secure` (data/incoming→data/out, done/failed 이동).
- 전사 실사용: `uv pip install -e ".[transcribe]"` + ffmpeg + HF_TOKEN(pyannote)/GROQ_API_KEY.
- 테스트: `.venv/bin/python -m pytest -q` (mock으로 네트워크·GPU·오디오 없이 e2e).
- 오프라인 데모: `ASR_ENGINE=mock DIARIZER=mock ... transcribe` → `LLM_PROVIDER=mock ... generate`.
