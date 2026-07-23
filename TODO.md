# TODO — 무료·로컬 구동 로드맵

> **제약 (확정)**
> 1. **모든 엔진 = 무료.** API가 크레딧 결제를 요구하면 유료로 간주하고 **제외**.
> 2. **구동 환경 = 로컬.** 로컬 테스트 완료 후 필요 시 클라우드 배포(후순위).

우선순위: **P0 필수(없으면 구동 불가)** · **P1 품질** · **P2 선택/나중**

---

## 0. 엔진 정책 — 무료·로컬 매핑 (기준표)

| 역할 | 채택(무료·로컬) | 상태 | 제외/보류 | 사유 |
|---|---|---|---|---|
| LLM | **Ollama**(로컬) | ✅ 코드 완료 | Gemini | 클라우드. 무료티어 있으나 정책상 로컬 우선 |
| 전사(ASR) | **faster-whisper**(로컬, GPU 없으면 **CPU**) | ⚠️ 코드 보완 필요 | Groq | 클라우드 + 무료티어 크레딧/유료화 리스크 |
| 화자분리 | **pyannote**(로컬) | ✅ 코드 완료 | — | HF 토큰 무료(게이트 동의만) |
| 오케스트레이션 | **n8n** Community(로컬) | ✅ 완료 | — | 무료 |
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

- [ ] `uv venv && uv pip install -e ".[dev]"` → `pytest -q` (26 passed 확인)
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

- [ ] `glossary.yaml` 예시 → **실제 사업명/기관/약어/인명**으로 교체
- [ ] `prompts/*.md` 튜닝 — 실회의 1건 결과(`.minutes.md`) 검토 후 결정/액션 누락 규칙 보강

## 4. 로컬 검증 — "수동 5회 성공" 원칙 (P0)

- [ ] (a) 오프라인 배관: `ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock python -m minutes.pipeline ...`
- [ ] (b) **완전 로컬 실오디오 1건**: `python -m minutes.pipeline --audio 회의.m4a --profile secure`
      (faster-whisper CPU/GPU + pyannote + Ollama — 클라우드 0)
- [ ] (c) 산출물 `.minutes.md` 사람 검토 → 오류를 glossary/prompts에 반영 → (b) 재실행
- [ ] (d) 전사 품질 수치화: `python scripts/cer.py --ref 정답.txt --hyp 회의.transcript.json`
- [ ] (e) 같은 회의 5회 안정 재현 확인 → 자동화 신뢰

## 5. n8n 로컬 오케스트레이션 (P1)

- [ ] `docker compose up -d --build` (n8n + ollama) — 단, 로컬 전사는 이미지에 transcribe 포함 필요:
      `docker compose build --build-arg INSTALL_TRANSCRIBE=1 n8n` + `.env ASR_ENGINE=faster-whisper`
      ※ CPU 전사는 컨테이너에서 느림 → 로컬 CLI 우선, n8n은 소규모 회의로 검증
- [ ] `docker exec -it mr_ollama ollama pull qwen2.5:7b`
- [ ] n8n UI: `workflows/meeting_minutes.json` import → Error Workflow 지정 → Active
- [ ] `data/inbox`에 오디오 투입 → `data/out/{secure,internal}` 산출 확인

## 6. Vexa 봇 로컬 (P2 — 선택)

- [ ] Vexa **공식 스택 로컬 배포**(무료 self-host, 다중 컨테이너 — 리소스 큼) 여부 결정
- [ ] 배포 시 `docker-compose.yml`의 `VEXA_IMAGE`/`VEXA_API_*` 실제값으로 교체
- [ ] `python -m minutes.bot request/ingest` 로컬 e2e
- [ ] `scripts/ab_transcribe.py` 로 Vexa 내장 vs faster-whisper A/B (무료끼리 비교)

## 7. 클라우드 배포 (P2 — 로컬 검증 완료 후)

> ⚠️ 클라우드 GPU 인스턴스·관리형 서비스는 **비용 발생** — 무료 제약과 충돌하므로 후순위.

- [ ] 무료/저비용 옵션 우선 조사: 자체 서버(온프레미스) / 무료 크레딧 한도 내 VM / 학교·기관 GPU
- [ ] 로컬 `docker-compose` → 대상 환경 이관, 비밀관리(.env→시크릿)
- [ ] 외부 노출 시 n8n/Vexa 인증·방화벽

---

## 즉시 착수 후보 (다음 액션)

1. ~~**§1 코드 보완** — 무료·로컬 정책 코드 고정~~ ✅ 완료 (MVP)
2. **§2 로컬 환경 셋업** — Ollama 설치 + `ollama pull qwen2.5:7b` + `[transcribe]` 설치
3. **§4(b) 실오디오 1건** 완전 로컬 e2e (faster-whisper CPU + Ollama, 클라우드 0)
