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
  **`minutes.watch`**(폴더감시 자동 회의록, `--once` 크론모드), **`diarize.py` Windows 수정 4종**
  (token=/use_auth_token 폴백, soundfile 인메모리 torchcodec 우회, DiarizeOutput, 경고필터). pytest 36개.
- **계보: 이 브랜치가 정본**(로컬 `main` 2a47d4c 폐기 방침). Cowork 로컬 변경분 반영 완료.
  → **2026-08 실행 완료**: 아래 '브랜치 단일화' 참고.
- 무인 자동화는 **watch(1차, Docker 불필요)** → n8n은 **네이티브**(Docker 금지 정책).

### n8n 연동은 HTTP 방식 (2026-07, executeCommand 회피)
- **문제**: n8n 2.8.4에서 `n8n-nodes-base.executeCommand`가 미지원(Unrecognized node type).
- **해결**: `minutes.server`(표준 라이브러리 HTTP 서비스)를 띄우고 n8n은 **HTTP Request 노드**로 호출.
  - 엔드포인트: `GET /health`, `POST /bot/dispatch|/bot/stop|/ingest|/pipeline` (기본 127.0.0.1:8900).
  - 워크플로: **`workflows/vexa_meeting_http.json`**(httpRequest만, executeCommand 0 → n8n 버전 무관).
  - `MINUTES_SERVER_URL`(n8n측), `MINUTES_SERVER_HOST/PORT`(서버측)로 주소 지정.
- executeCommand 기반(`vexa_meeting.json`/`_local.json`)은 참고용 보존. **정본은 HTTP 방식.**

### 녹음본(클로바 노트) 업로드 지원 (2026-08)
- **배경**: 대시보드 업로드가 텍스트 전용이라 `.m4a`를 못 받았고, 5MB 상한이 하드코딩돼 있었다.
  (엔진은 처음부터 ffmpeg 경유라 m4a/aac를 지원했음 — 막힌 건 **웹 업로드 경로**뿐.)
- `audio_formats.py`: 지원 확장자 **단일 출처**(server 검증 · watch 스캔 · 대시보드 `accept` 모두 여기서).
- **`POST /api/upload/audio`**: JSON/base64가 아니라 **raw 바이너리 스트리밍**. 파일명은 `X-Filename`(URL 인코딩),
  옵션은 쿼리(`profile`/`title`/`auto`). 1MB 청크로 디스크에 흘려보내 큰 파일도 메모리를 안 씀.
  `.part`로 쓰고 완료 시 rename → watch가 미완성 파일을 집지 않음.
- **상한은 환경변수**: `MINUTES_MAX_UPLOAD_MB`(녹음본, 기본 500) / `MINUTES_MAX_TEXT_UPLOAD_MB`(텍스트, 기본 5).
  텍스트 상한은 **바이트 기준으로 수정**(예전엔 문자 수라 한글이 실질 3배로 헐거웠음).
  거부 시: `Expect: 100-continue` 응답 + 남은 본문 버리기(32MB까지) + **브라우저 측 사전 검사**(사유를 정확히 보여주려면 필수 —
  서버가 중간에 끊으면 XHR이 응답을 못 읽는다).
- **작업 큐**: 업로드 즉시 응답하고 전사→회의록은 백그라운드 스레드(`_JOBS`), 진행상황은 `GET /api/jobs` 폴링.
  `auto=1` → `data/uploads/audio/`(서버가 처리) / `auto=0` → `data/incoming/`(외부 `minutes.watch`가 처리) — **폴더를 갈라 중복 처리 방지**.
- `POST /api/audio/process`로 기존 녹음본 재처리. 파일 목록/삭제/이름변경에 `audio` 종류 추가(확장자 보존).
- pytest 통과(HTTP 소켓 레벨 테스트 포함). 브라우저(Playwright)로 업로드→회의록 UI 경로까지 확인.

### 전사 진행 가시성 (2026-08)
- **문제**: 첫 실행에서 large-v3(3GB)를 받는 40분 동안 대시보드가 계속 "전사하는 중"만 표시 →
  멈춘 것과 구분 불가. 실사용 중 실제로 겪음.
- `asr/info.py`(신규): 디바이스 판정(ctranslate2 → torch 순, 불명이면 보수적으로 cpu),
  HF 캐시 경로(`HF_HUB_CACHE`/`HF_HOME` 반영), `is_model_cached`(.incomplete 있으면 미완),
  모델별 예상 크기·(디바이스,크기군)별 전사 소요 **범위** 추정.
- **`engine.load()`를 `transcribe()`에서 분리** — 다운로드 구간과 전사 구간을 호출자가 구분해 표시.
  ASREngine 프로토콜에 `load()` 추가(mock·groq는 no-op).
- `transcribe_audio(..., on_phase=cb)`: start/convert/model/asr/diarize/merge 단계 통지.
  `start`에 engine·device·model·duration(ffprobe)·repo_id·cached를 실어 보냄. CLI 동작은 그대로.
- 서버: job에 phase/phase_since/engine/device/duration/eta·dl_mb 추가, `ep_jobs`가 **경과 시간을
  서버 시계로 계산**(브라우저 시계 어긋남 방지). 미캐시 모델이면 캐시 폴더 크기를 2초마다 재는
  감시 스레드로 진행률 표시(huggingface_hub이 콜백을 안 줌).
- 대시보드: 단계별 경과·전체 경과·다운로드 진행바·`faster-whisper large-v3 · CPU · 녹음 19분 ·
  전사 예상 15분~49분 · 화자분리 꺼짐` 한 줄. 폴링 3s→2s.
- 예상 시간은 **범위**로만 준다(하드웨어 편차가 커서 단일값은 거짓말이 됨).

### 긴 회의 타임아웃 장애 + 실제 진행률 (2026-08)
- **장애**: 19분 회의가 LLM 단계에서 `timed out`. 사슬 전체가 원인이었다.
  1. `diarizer=off` → 모든 세그먼트가 SPEAKER_00 → `merge_segments`가 **회의 전체를 1개로 병합**
  2. `chunk_segments`는 세그먼트 **사이**에서만 자름 → 1개면 분할 무력화
  3. `correct_terms`는 애초에 청크를 안 쓰고 전문을 한 프롬프트로 보냄. 게다가
     LLM이 **전문을 그대로 다시 출력**해야 함(출력≈입력) → CPU qwen2.5:14b에서 600초 초과
  4. 그 단계는 "실패해도 원문 유지" 설계인데 `JSONDecodeError/KeyError/TypeError`만 잡아
     **타임아웃이 작업 전체를 죽임**
  5. `_write`가 LLM 뒤라 40분 걸린 전사가 통째로 유실
- **고침**: merge 상한(`MAX_MERGE_CHARS/SEC/GAP` — 228개→19개) · `_split_oversized`로 거대
  세그먼트 내부 분할 · `correct_terms` 청크화 + **모든 예외 원문 폴백** + `LLM_TERM_CORRECTION=0`
  스위치 · **전사를 LLM 전에 저장**(`_write_transcript`) · `OLLAMA_TIMEOUT`(기본 1800) +
  타임아웃 메시지에 model/host/입력크기/해결책 명시.
- **실제 진행률**: faster-whisper는 세그먼트를 생성기로 내놓고 각 세그먼트에 오디오 타임스탬프가
  있다 — 리스트로 삼키지 말고 소비하며 `on_progress(done_sec, total_sec)` 통지.
  회의록은 청크 n/N. 남은 시간은 **실측 처리속도**로 계산(사전 추정 범위는 실측이 생기면 물러남).
- pytest 129개.

### 전사 속도 튜닝 + 환경 진단 (2026-08)
- **실측**: 28분 회의가 CPU large-v3에서 0.42배속(≈57분 예상). 실사용 불가 수준.
- `scripts/check_env.py`: CPU/GPU/RAM · ct2 CUDA 개수 · CPU 지원 연산 · 후보 모델의
  **실제 접근 가능 여부(HfApi로 확인 — 레포명 추측 금지)** · 캐시 여부 · Ollama 모델 목록 ·
  현재 .env → **권장 .env 값 출력**. 표준 라이브러리만, 무엇이 없어도 안 죽는다.
- 엔진 손잡이(전부 env, 0=자동): `WHISPER_BEAM_SIZE`(비우면 **CPU=1 greedy**, GPU=5) ·
  `WHISPER_BATCH_SIZE`(BatchedInferencePipeline) · `WHISPER_CPU_THREADS` · `WHISPER_COMPUTE_TYPE`.
- 확인된 사실: faster-whisper 1.2.1 배치추론 지원 / ct2 4.8.1 CPU 연산 = int8·int8_float32·
  int16·float32 (`compute_type=auto`면 int8 선택) / `beam_size` 기본이 5라 CPU에서 손해.
- 우선순위: **GPU 켜기(10배+) > 모델 교체(3~5배) > beam=1(1.5~2배) > 배치 > 스레드**.
  distil-whisper는 영어 전용이라 한국어 회의에 못 씀 — turbo 계열을 쓸 것.
- pytest 134개.

### 회의록 문체 = 개조식 + 단계별 소요시간 (2026-08)
- 사용자 요구: **개조식**(명사형 종결 `~함/~됨/~필요`) · **문장 끝 마침표 없음**.
- 2겹으로 강제: ① `prompts/03`에 '문체 — 개조식(엄수)' 섹션(금지/권장 대조표 + discussion 예시),
  `prompts/02`도 같은 문체로, `MINUTES_JSON_HINT` 예시 자체를 개조식으로(LLM은 형식 예시를
  문체 예시로도 읽는다). ② `style.py`가 코드로 마침표 제거 — 로컬 7b가 지시를 흘려도 구두점은 보장.
- `style.py` 규칙: 마침표 **앞**이 한글/영문/닫는괄호일 때만 처리 → `1.5억`·`v3.1`·`2026-08-20` 보존.
  문장 **사이**는 줄바꿈으로(그냥 지우면 두 문장이 붙음), 줄 **끝**은 제거.
  적용은 pydantic `Brief` 애노테이션(`Annotated[str, AfterValidator]`) — `Segment.text`(전사 원문)와
  `owner`/`due_date`/`attendees`는 **제외**. `MINUTES_STRIP_PERIODS=0`으로 끌 수 있음.
- job에 `timings{phase: sec}` 적립 → 완료 후 "전사 18분 · 회의록 5분" 표시. 다음 최적화 지점 판단용.
  단계 전환 시 진행률 초기화(끝난 작업에 낡은 막대가 남지 않게).
- 실측: i7-1360P CPU에서 28분 회의 = 23분(turbo+beam1+batch8). 이전 large-v3 대비 2.9배.
- pytest 148개.

### LLM이 병목 (2026-08) — 전사는 해결됨
- **실측(i7-1360P, turbo+beam1+batch8)**: 28분 회의 = 전사 11분(2.5배속) + LLM 30분 타임아웃.
  전사는 더 이상 병목이 아니다. **남은 병목은 CPU 로컬 LLM 100%.**
- **조용한 정확성 버그 발견**: Ollama 기본 `num_ctx`(보통 4096)를 넘으면 프롬프트
  **앞부분이 말없이 잘린다** → 회의 앞부분이 사라진 채 요약됨. 8,743자 프롬프트면 확실히 초과.
  → `OllamaProvider.context_size()`가 요청마다 필요한 만큼(4k/8k/16k/32k) 잡고 `OLLAMA_MAX_CTX`로 상한.
- `MINUTES_CHUNK_CHARS`(기본 6000→**3000**): CPU 로컬 LLM 기준으로 낮춤. 크게 잡으면 한 번의
  실패로 전부 잃고 num_ctx가 커져 CPU에서 급격히 느려진다. GPU·클라우드면 올릴 것.
- `summarize_chunks` 부분 실패 내성: 구간 하나가 실패해도 나머지로 회의록 생성.
  단 **전부 실패하면 지어내지 말고** 원인을 그대로 올린다.
- **구조적 결론**: CPU 로컬 LLM으로 8천 자 프롬프트는 무리. 선택지는 (a) 3b급 소형 모델,
  (b) internal 프로파일을 클라우드로(Gemini/Groq), (c) GPU. 속도로 클로바/ChatGPT를 이길 수는 없고,
  이 시스템의 축은 **보안(secure는 대안 없음) + 사람 손 0분 자동화**여야 한다.
- **미구현 갭 2개**: ① 완료 알림이 n8n 워크플로에만 있고 native(server/watch) 경로엔 없음
  ② ASR이 프로파일을 안 따름(LLM만 분기) → internal도 무조건 로컬 전사.
- pytest 154개.

### LLM 폭주 차단 — 스트리밍 전환 (2026-08)
- **증상**: 같은 크기 청크인데 1번은 80초, 2번은 1800초 초과(qwen2.5:**3b**, 입력 5,522자).
  30배 차이는 성능으로 설명 안 됨 → **반복 생성 폭주**.
- **원인**: `num_predict` 미지정(모델이 컨텍스트를 다 채울 때까지 생성) + `stream=False`
  (폭주해도 타임아웃까지 아무것도 모름).
- **고침**: `stream=True`로 전환. httpx `read` 타임아웃이 **토큰 사이 간격**에 걸리므로
  멈춘 모델을 `OLLAMA_STALL_TIMEOUT`(기본 180초) 안에 잡는다. 전체 상한은 루프에서 직접 체크.
  `num_predict`(기본 2048) · `repeat_penalty`(1.15) · `keep_alive`(10m, 청크마다 재로딩 방지).
- **진단 메시지가 실패 모드를 구분**: 생성 토큰 ≈ 상한 → 폭주 / 0토큰 → 로딩·메모리 부족 /
  그 사이 → 그냥 느림. 대처가 다르니 메시지도 달라야 한다.
- `done_reason == "length"`면 잘렸다고 경고(조용히 뒷부분이 사라지는 걸 막음).
- 실측 tok/s를 콘솔에 출력 — 다음 판단의 근거.
- pytest 162개(가짜 Ollama HTTP 서버로 폭주·무응답·잘림·오류 재현).
- **실측 2.2 tok/s (qwen2.5:3b, i7-1360P)** — 정상(8~15)의 1/4~1/7. 대역폭 계산상
  2GB 모델 × 2.2 = 4.4GB/s로 LPDDR5(50~70GB/s)의 7%만 씀 → **메모리가 아니라 연산이 굶음**
  (전원 모드 절전 / RAM 부족 스왑 / 스레드 부족 / WSL 안의 Ollama 중 하나).
- `OLLAMA_NUM_THREAD`(0=Ollama 기본) 추가. `scripts/bench_llm.py`로 수십 초 만에
  스레드·모델별 tok/s 비교(회의록 1건은 15분이라 설정 실험이 불가능했음).

### 출력 길이가 진짜 병목 (2026-08)
- **실측**: 2.2 → **3.9 tok/s**(환경 조치 후). 그런데 3,000자(≈2,200토큰) 청크 요약에
  **1,992토큰을 출력**하고 상한에 걸림 → 요약이 입력만큼 길다 = 요약을 안 하고 늘어놓는 중.
  qwen2.5:3b가 `02` 프롬프트의 복잡한 규칙(라벨별 항목 + 개조식 + 보존 규칙)을 못 따름.
- **CPU에서 출력 길이 = 시간.** 2000토큰 = 8분, 600토큰 = 2.5분. tok/s를 두 배 올리는 것보다
  출력을 1/3로 줄이는 게 크다.
- **2겹 제약**: ① `LLMProvider.generate(..., max_tokens=)` 를 프로토콜에 추가하고
  `chain.MAX_TOKENS`가 단계별로 다르게 준다(summary 600 / integrate·terms 2048).
  Ollama는 `num_predict`와 **num_ctx까지** 그만큼만 잡아 CPU 부담을 줄인다.
  ② `prompts/02`에 '분량(엄수)' — 12줄 이내 · 한 줄 40자 · **입력보다 짧아야 함**.
- 잘림 경고 문구를 '모델이 요약하지 않고 늘어놓는 중일 수 있음'으로 바꿔 원인을 가리키게 함.
- pytest 166개.

### 브랜치 단일화 (2026-08, 완료)
- **이제 브랜치는 `main` 하나뿐이다.** 기본 브랜치도 `main`.
- `main`을 작업 계보(`claude/clova-note-recording-support-1kna7y`, 51커밋)로 강제 갱신하고
  옛 `main`(2a47d4c, Cowork 스냅샷)은 폐기 — 고유 파일 0개라 유실 없음.
- `claude/meeting-minutes-automation-07augh` · `claude/clova-note-recording-support-1kna7y` 삭제됨
  (전자는 후자에 완전히 포함, 후자는 `main`과 동일 커밋).
- 앞으로 작업 브랜치는 `main`에서 딴다. 문서의 clone/pull 예시도 `main` 기준으로 갱신됨.

### 개발 환경 메모
- `uv venv && uv pip install -e ".[dev]"` 후 `python -m minutes.generate` 사용(‑e 설치 필요).
- 무인 자동화: `python -m minutes.watch --profile secure` (data/incoming→data/out, done/failed 이동).
- 전사 실사용: `uv pip install -e ".[transcribe]"` + ffmpeg + HF_TOKEN(pyannote)/GROQ_API_KEY.
- 테스트: `.venv/bin/python -m pytest -q` (mock으로 네트워크·GPU·오디오 없이 e2e).
- 오프라인 데모: `ASR_ENGINE=mock DIARIZER=mock ... transcribe` → `LLM_PROVIDER=mock ... generate`.
