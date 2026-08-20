# TODO — 무료·로컬 구동 로드맵

> **🎯 최종 목표(클라우드 Vexa 봇 자동화)의 육하원칙 TDL은 → [`docs/TARGET_CLOUD_TDL.md`](docs/TARGET_CLOUD_TDL.md)**
> 이 문서(TODO.md)는 그 **1단계인 로컬 구성·검증** 로드맵이다.

> **제약 (로컬 단계)**
> 1. **로컬 엔진 = 무료·로컬.** (⚠️ 최종 클라우드 단계는 GPU/Vexa로 **비용 발생** — 무료 유지 불가, TARGET 문서 §2·D4)
> 2. **로컬 처리박스 = Windows 네이티브(Docker 금지).** (⚠️ 클라우드/Vexa 호스트는 컨테이너 필요 — TARGET 문서 D3)

우선순위: **P0 필수(없으면 구동 불가)** · **P1 품질** · **P2 선택/나중**

---

## ★ 세션 핸드오프 반영 (Cowork → 이 브랜치) — 최우선 정합성

> `SESSION_HANDOFF.md` 기준. Cowork 로컬 `main`(커밋 `2a47d4c`)과 GitHub 작업 브랜치가
> **별개 계보**였던 건을 정합화한 기록이다.
> **2026-08 종결**: 브랜치를 `main` 하나로 통합하고 나머지는 삭제 — 아래 항목은 전부 완료.

- [x] **`.env` 인라인 주석 파서 해결** — `_parse_env_value()`(`config.py`) + 테스트.
      (핸드오프 함정: `OLLAMA_MODEL`/`ASR_ENGINE` 값 뒤 `#` 오염 → 해결)
- [x] **`pyproject` soundfile>=0.12** 추가([transcribe]).
- [x] **`.gitignore`** `*.bak`, `vexa/` 추가.
- [x] **watch 스크립트 구현** — `python -m minutes.watch`(폴더감시→자동 회의록,
      크기 안정화 게이트, `--once` 크론모드). + 테스트.
- [x] **`diarize.py` Windows 수정 4종 반영 완료** — 사용자 검증본으로 교체.
      (token=/use_auth_token 폴백, soundfile 인메모리(torchcodec 우회), DiarizeOutput
      `.speaker_diarization`, torchcodec 경고필터). lazy import 유지 → mock 테스트 정상.
- [x] **계보 정합 결정: 브랜치를 정본으로 단일화**(로컬 `main` 2a47d4c 폐기).
- [x] **브랜치 단일화 실행(2026-08)** — 작업 계보를 `main`으로 강제 갱신, 기본 브랜치 `main`,
      `claude/*` 2개 삭제. 기존 클론은 `git fetch --prune && git checkout main && git reset --hard origin/main`.

---

## 0. 엔진 정책 — 무료·로컬 매핑 (기준표)

| 역할 | 채택(무료·로컬) | 상태 | 제외/보류 | 사유 |
|---|---|---|---|---|
| LLM | **Ollama**(로컬) | ✅ 코드 완료 | Gemini | 클라우드. 무료티어 있으나 정책상 로컬 우선 |
| 전사(ASR) | **faster-whisper**(로컬, GPU 없으면 **CPU**) | ✅ 코드 완료(auto=로컬) | Groq | 클라우드 + 무료티어 크레딧/유료화 리스크 |
| 화자분리 | **pyannote**(로컬) | ✅ Windows 수정 반영 완료 | — | HF 토큰 무료(게이트 동의만) |
| 오케스트레이션 | **watch**(로컬) / n8n **네이티브** | watch ✅ / n8n 네이티브 대기 | n8n Docker | Docker 금지 정책 |
| 봇 참석 | **Vexa** 셀프호스팅(로컬) | ✅ 코드 완료 | Vexa Cloud | 무료 self-host만 사용 |

> 결정: **secure·internal 둘 다 로컬 Ollama로 먼저 검증**한다.
> Gemini/Groq는 "무료티어가 확실히 무료일 때만" 선택적으로 재도입(기본 비활성).

---

## 1. 코드 보완 — 무료·로컬 정책 반영 (P0) ✅ 완료

- [x] **ASR `auto` → 항상 로컬 faster-whisper** (GPU 없으면 CPU). Groq는 명시 시에만.
      `resolve_asr_choice()` 분리 + 테스트. (`asr/__init__.py`)
- [x] **internal 프로파일 무료·로컬 폴백** — GEMINI_API_KEY 없으면 Ollama로 폴백(경고). (`config.py`)
- [x] **화자분리 graceful degrade** — HF_TOKEN 없으면 크래시 대신 단일 화자(경고). (`asr/__init__.py`)
- [x] **`.env` 무료·로컬 프리셋** — ASR_ENGINE=auto, WHISPER_MODEL=medium, OLLAMA_MODEL=qwen2.5:7b.
- [x] docker-compose 기본을 auto/auto 로.

## 2. 로컬 환경 셋업 (P0)

- [x] **원커맨드 실행 스크립트** — `scripts/run_local.sh`(+`.ps1`). uv 없으면 venv 폴백,
      Windows `Scripts/` 경로 자동 판별, ffmpeg/Ollama 사전점검. `--mock`/`--setup-only`/`--audio`.
- [ ] `uv venv && uv pip install -e ".[dev]"` → `pytest -q` (51 passed 확인)
- [ ] 전사 의존성: `uv pip install -e ".[transcribe]"` (torch/faster-whisper/pyannote)
- [ ] **ffmpeg** 설치 (`apt install ffmpeg` / `brew install ffmpeg`)
- [ ] **Ollama 로컬 설치** (https://ollama.com, 무료) + 모델 pull
      - GPU/충분 RAM: `ollama pull qwen2.5:14b`
      - CPU/저사양: `ollama pull qwen2.5:7b` → `.env` `OLLAMA_MODEL` 일치
- [ ] **HF 토큰**(무료) 발급 + pyannote 게이트 동의 → `.env` `HF_TOKEN`
      (토큰 없이 먼저 볼 거면 `DIARIZER=off`로 단일 화자 처리)
- [ ] `.env` 무료·로컬 프리셋:
      ```
      ASR_ENGINE=faster-whisper
      WHISPER_MODEL=medium          # CPU면 medium/small
      DIARIZER=pyannote             # 토큰 없으면 off
      OLLAMA_HOST=http://localhost:11434
      OLLAMA_MODEL=qwen2.5:7b
      # (Groq/Gemini 키는 비워둠 — 클라우드 미사용)
      ```

## 3. 실데이터 튜닝 (P1 — 이 시스템의 진짜 IP)

- [x] `glossary.yaml` acronyms(도메인 공통어) 대폭 확장 + 프롬프트 개조식 튜닝 (`cb8c949`)
- [ ] `glossary.yaml` projects/organizations/people → **실제 사업/참여기관/참석자**로 교체
      (현재 플레이스홀더 `TODO` 마커. 핸드오프상 우선순위 낮음)
- [ ] 실회의 반복하며 틀린 고유명사 반영 루프(4-c)

## 4. 로컬 검증 — "수동 5회 성공" 원칙  (핸드오프상 1건 검증 완료)

- [x] (a) 오프라인 배관: mock e2e (pytest 36개 통과)
- [x] (b) **실오디오 1건 검증됨** — 핸드오프: `test.m4a`(한국어 4분) → 17개 화자구간 →
      개조식 회의록(결정2·액션2·미결1) 생성 성공, 사용자 만족
- [ ] (c) 산출물 검토 → glossary/prompts 반영 루프 (지속)
- [ ] (d) 전사 품질 수치화: `python scripts/cer.py --ref 정답.txt --hyp 회의.transcript.json`
- [ ] (e) 같은 회의 5회 재현성 (핸드오프상 **보류** — 정확도 만족)

## 5. 무인 자동화 — watch(1차) → n8n(2차)

### 5-1. watch 폴더감시 (✅ 구현 — Docker 불필요, 권장 1차)
- [x] `python -m minutes.watch` 구현: `data/incoming` 감시 → 자동 파이프라인 →
      `data/out` 산출 + 처리분 `data/done` 이동(실패 `data/failed`). 크기 안정화 게이트.
- [ ] 실환경 상시 실행: `python -m minutes.watch --profile secure`
      (백그라운드/작업스케줄러 등록은 운영자 재량)

### 5-2. n8n 오케스트레이션 (네이티브 + HTTP) ✅ mock e2e 검증 완료
- [x] n8n Community 네이티브 실행(`npm i -g n8n` → `n8n start`, :5678)
- [x] **executeCommand 미지원(2.8.4) → HTTP 방식으로 전환** (`minutes.server` + `vexa_meeting_http.json`)
- [x] **전체 e2e 성공(mock)**: `/webhook/meeting-end` → n8n → `:8900/ingest`
      → Vexa(mock)→회의록 → `data/out/secure/*.minutes.md` 생성 확인
- [ ] 실물 전환: 서비스 env를 실제(VEXA/HF/GPU)로, 워크플로는 그대로(서버주소만 집 PC)
- 참고: `vexa_meeting.json`/`_local.json`(executeCommand)·docker-compose는 보존만.

## 6. Vexa 봇 — 셀프호스팅 확정 (외부 API 불필요)

- [x] mock ingest 검증(`VEXA_CLIENT=mock`) + HTTP 서비스 e2e 검증
- [x] **회의 링크 자동 파싱** — `parse_meeting_url`(Meet/Zoom/Jitsi/Teams). "링크만 보내면 참가"
      (웹훅 `{url}` / `bot request --url`). Zoom passcode 파싱 포함.
- [x] **방식 확정: 공식 레포 셀프호스팅.** `make all`이 로컬 키(`vxa_...`) 자동생성 → Cloud 발급 X.
      게이트웨이 :18056, UI :13000. 전사 GPU 유닛 셀프호스팅 시 완전 air-gapped(B2G).
- [ ] **집 GPU PC에서 실제 Vexa 기동 + 실회의 봇 참가 1건** (mock 졸업) ← 다음 관문
- [ ] 실회의 검증: Meet(쉬움) / Zoom(passcode·대기실) / Teams(id 형식) / 대기실 승인

## 7. 파생 작업

- [x] (a) `diarize.py` Windows 수정 반영 (Cowork 검증본)
- [x] (b) n8n 워크플로 — HTTP 정본(`vexa_meeting_http.json`) + 네이티브(`_local.json`)
- [x] (c) git push/계보 정합 — 브랜치 정본 단일화
- [ ] (d) 폐쇄망 wheelhouse 설치 절차(선택)

## 8. 클라우드 배포 (Phase B — 집 PC 검증 후, Vultr 등)

> ⚠️ 클라우드 GPU 인스턴스는 비용 발생. 집 PC(Phase A) 검증 완료 후 이관.

- [ ] Vultr 등 GPU 인스턴스로 동일 스택(Vexa+서비스+n8n) 이관 + 시크릿/도메인/보안
- [ ] 외부 노출 시 n8n/Vexa 인증·방화벽, (B2G 실운영) 망분리/CSAP

---

## 즉시 착수 후보 (다음 액션)

1. **집 GPU PC 셋업** — `bash scripts/home_pc_setup.sh` (venv/설치/ollama/.env/pytest 자동).
2. **Vexa 셀프호스팅** — `git clone vexa && make all && make bot` → `vxa_` 키를 `.env`에.
3. **실회의 봇 참가 1건** — `bot request --url "<회의링크>"` → mock 졸업.
4. (완료) 링크 파서·HTTP 서비스·Vexa 실정보(포트 18056)·.env 턴키 — 이번 세션 반영.
