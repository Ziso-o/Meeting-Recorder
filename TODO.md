# TODO — 무료·로컬 구동 로드맵

> **제약 (확정)**
> 1. **모든 엔진 = 무료.** API가 크레딧 결제를 요구하면 유료로 간주하고 **제외**.
> 2. **구동 환경 = 로컬 · Windows 네이티브.** Docker/VM 금지. 클라우드 배포는 후순위.

우선순위: **P0 필수(없으면 구동 불가)** · **P1 품질** · **P2 선택/나중**

---

## ★ 세션 핸드오프 반영 (Cowork → 이 브랜치) — 최우선 정합성

> `SESSION_HANDOFF.md` 기준. Cowork 로컬 `main`(커밋 `2a47d4c`, 미push)과 GitHub
> 브랜치 `claude/meeting-minutes-automation-07augh`는 **별개 계보**다. 아래를 정합화한다.

- [x] **`.env` 인라인 주석 파서 해결** — `_parse_env_value()`(`config.py`) + 테스트.
      (핸드오프 함정: `OLLAMA_MODEL`/`ASR_ENGINE` 값 뒤 `#` 오염 → 해결)
- [x] **`pyproject` soundfile>=0.12** 추가([transcribe]).
- [x] **`.gitignore`** `*.bak`, `vexa/` 추가.
- [x] **watch 스크립트 구현** — `python -m minutes.watch`(폴더감시→자동 회의록,
      크기 안정화 게이트, `--once` 크론모드). + 테스트.
- [ ] **⚠️ `diarize.py` Windows 수정 4종 반영** — Cowork 로컬에만 존재, 브랜치엔 없음.
      (token=/use_auth_token 폴백, soundfile 인메모리(torchcodec 우회), DiarizeOutput
      `.speaker_diarization`, torchcodec 경고필터) → **사용자 원본 파일 받아 정확히 반영 예정**.
- [ ] **계보 정합 결정** — 로컬 `main`(2a47d4c) vs 브랜치. 택1:
      (a) 로컬 변경분(주로 diarize.py)만 이 브랜치에 얹어 단일화(권장) /
      (b) 로컬 `main`을 별도 push 후 병합.

---

## 0. 엔진 정책 — 무료·로컬 매핑 (기준표)

| 역할 | 채택(무료·로컬) | 상태 | 제외/보류 | 사유 |
|---|---|---|---|---|
| LLM | **Ollama**(로컬) | ✅ 코드 완료 | Gemini | 클라우드. 무료티어 있으나 정책상 로컬 우선 |
| 전사(ASR) | **faster-whisper**(로컬, GPU 없으면 **CPU**) | ✅ 코드 완료(auto=로컬) | Groq | 클라우드 + 무료티어 크레딧/유료화 리스크 |
| 화자분리 | **pyannote**(로컬) | ⚠️ Windows 수정 반영 대기 | — | HF 토큰 무료(게이트 동의만) |
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
- [ ] `uv venv && uv pip install -e ".[dev]"` → `pytest -q` (32 passed 확인)
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

### 5-2. n8n 오케스트레이션 (P2 — **네이티브**, Docker 금지 정책)
- [ ] **Docker 미사용** → Node.js LTS + `npm i -g n8n` → `n8n start`(:5678)
- [ ] ⚠️ `workflows/*.json`은 도커 경로(`$MINUTES_PY`,`/data/...`) 전제 →
      **Windows 네이티브 경로로 수정한 `*_local.json` 필요**(파생작업 §7-b)
- [ ] `docker-compose.yml`/`Dockerfile.n8n`은 정책상 미사용(참고용 보존)

## 6. Vexa 봇 (P2 — 보류 결정 필요)

- [x] mock ingest 검증 완료(`VEXA_CLIENT=mock`)
- [ ] **결정**: Vexa는 다중 컨테이너 Docker → 정책 충돌. (A) 봇 없이 수동 녹음 →
      watch/파이프라인 운영 / (B) Docker 예외 호스트 승인. 상세 `docs/STACK_MANUAL_TDL.md`

## 7. 파생 작업

- [ ] (a) **`diarize.py` Windows 수정 반영** (최우선, 위 ★ 참조 — 원본 파일 필요)
- [ ] (b) **n8n 네이티브 워크플로우** `workflows/*_local.json` (도커 경로 제거)
- [ ] (c) **git push/계보 정합** (위 ★ 참조)
- [ ] (d) 폐쇄망 wheelhouse 설치 절차(선택)

## 8. 클라우드 배포 (P2 — 로컬 검증 완료 후)

> ⚠️ 클라우드 GPU 인스턴스·관리형 서비스는 **비용 발생** — 무료 제약과 충돌하므로 후순위.

- [ ] 무료/저비용 옵션 우선 조사: 자체 서버(온프레미스) / 무료 크레딧 한도 내 VM / 학교·기관 GPU
- [ ] 외부 노출 시 n8n/Vexa 인증·방화벽

---

## 즉시 착수 후보 (다음 액션)

1. **★ diarize.py 정합** — 사용자 원본(Cowork) 파일 확보 → 브랜치 반영 (§7-a). **최우선.**
2. **계보 정합 결정** (§★) — 로컬 `main` vs 브랜치 단일화 방침 확정.
3. **watch 상시 실행** — `python -m minutes.watch --profile secure` (무인 자동화 1차, Docker 불필요).
4. (완료) `.env` 파서·soundfile·gitignore·watch — 이번 세션 반영.
