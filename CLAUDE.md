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
| **Phase 1** | 회의록 생성기 (텍스트 → 회의록). **가장 먼저.** | ⬜ 대기 |
| **Phase 2** | 전사 엔진 (오디오 → 화자라벨 텍스트) | ⬜ 대기 |
| **Phase 3** | 1+2 결합 + n8n 워크플로우 | ⬜ 대기 |
| **Phase 4** | Vexa 봇 참석 연동 | ⬜ 대기 |

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

- **부트스트랩 완료**: CLAUDE.md + 디렉토리 스켈레톤 생성. 실제 로직은 아직 없음(스텁).
- **다음**: Phase 1 (회의록 생성기) — 사용자 지시 대기 중.
