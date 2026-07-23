# 스택별 수동 작업 TDL (육하원칙)

> 전제 정책: **Docker/VM 금지 · Windows 로컬 네이티브 · 무료·로컬 우선 · (설치 외) 오프라인**
> 이 정책 때문에 **원래 Docker 기반인 n8n·Vexa는 "네이티브 대안" 또는 "보류"** 로 처리한다.

## ⚠️ 정책 충돌 요약 (먼저 결정할 것)

| 스택 | 원래 방식 | 정책 충돌 | 조치 |
|---|---|---|---|
| **n8n** | Docker(compose) | Docker 금지 | **네이티브 설치**(Node.js + `npm i -g n8n`). 단, 제공 워크플로우는 도커 경로(`$MINUTES_PY`,`/data/...`) 전제 → **Windows 경로로 수정 필요** |
| **Vexa** | 다중 컨테이너 Docker 스택 | Docker 금지 | **보류 권장**. 봇 자동참석 대신 **회의 녹음 파일 수동 확보 → Phase 2 투입**. (봇이 꼭 필요하면 Docker 예외 호스트 별도 협의) |
| 나머지(전사/화자분리/LLM/Python) | 로컬 네이티브 | 없음 | 그대로 진행 |

---

## 1. 언어 / 의존성 — Python 3.11 / uv  `[선행·필수]`

| 육하 | 내용 |
|---|---|
| **왜(Why)** | 전 파이프라인 런타임. 이게 없으면 어떤 단계도 실행 불가 |
| **누가(Who)** | 개발자 |
| **언제(When)** | **가장 먼저**. 모든 작업의 선행 |
| **어디서(Where)** | Windows 로컬, 프로젝트 루트. venv는 `.venv\Scripts\` |
| **무엇을(What)** | ① venv 생성 ② 패키지 `-e` 설치 ③ 실행은 venv python으로 |
| **어떻게(How)** | `uv venv` → `uv pip install -e ".[transcribe]"` → `.venv\Scripts\python -m minutes.<...>` |

- [ ] `uv venv` (프로젝트 루트에 `.venv` 생성)
- [ ] `uv pip install -e ".[transcribe]"` (torch/faster-whisper/pyannote 포함)
- [ ] 검증: `.venv\Scripts\python -c "import minutes, torch, faster_whisper, pyannote.audio; print('ok')"`
- [ ] (선택) 3.11 고정 필요 시: `uv python install 3.11` → `uv venv --python 3.11`
      (현재 3.12 사용 중 — `requires-python>=3.11`이라 3.12도 동작)

## 2. 전사 — faster-whisper large-v3 (로컬) / ~~Groq~~  `[필수]`

| 육하 | 내용 |
|---|---|
| **왜** | 오디오 → 텍스트. 로컬·무료·민감회의 대응(오디오 외부 유출 없음) |
| **누가** | 개발자(설치), 인프라(GPU 드라이버) |
| **언제** | 실오디오 검증 직전. **large-v3 모델 최초 다운로드는 1회**(네트워크 필요) |
| **어디서** | Windows venv. 모델 캐시 `%USERPROFILE%\.cache\huggingface`. GPU면 NVIDIA 드라이버+CUDA |
| **무엇을** | ① `[transcribe]` 설치 ② 모델 자동 다운로드 확인 ③ GPU 유무에 따라 모델 크기 결정 |
| **어떻게** | `ASR_ENGINE=faster-whisper`, GPU면 `WHISPER_MODEL=large-v3`, **CPU면 `medium`/`small`**(large-v3는 CPU 매우 느림) |

- [ ] GPU 유무 확인: `.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"`
- [ ] GPU면 NVIDIA 드라이버/CUDA 확인, 없으면 `.env`에 `WHISPER_MODEL=medium`
- [ ] 최초 전사 실행 시 모델 다운로드(~3GB, large-v3) — **폐쇄망이면 모델 사전 반입 필요**
- [ ] ~~Groq(클라우드 fallback)~~ → **무료·정책상 미사용**(명시 `ASR_ENGINE=groq` 시에만)

## 3. 화자분리 — pyannote.audio 3.1  `[필수 or 생략]`

| 육하 | 내용 |
|---|---|
| **왜** | "누가 말했는지" 화자 라벨. 회의록 참석자/발언 매칭 품질 좌우 |
| **누가** | 개발자(토큰 설정), 계정 소유자(게이트 약관 동의) |
| **언제** | 전사와 함께. 토큰/동의는 최초 1회 |
| **어디서** | HF 웹(약관 동의), Windows 로컬(`.env`, 모델 캐시). **실행은 로컬** |
| **무엇을** | ① HF 토큰 발급 ② **게이트 모델 2개 약관 동의** ③ `.env` 설정 ④ 최초 모델 다운로드 |
| **어떻게** | `HF_TOKEN=...`, `DIARIZER=pyannote`. 토큰 없으면 자동 단일화자(비활성) |

- [ ] huggingface.co 로그인 → Settings → Access Tokens → read 토큰 발급
- [ ] 게이트 동의: `pyannote/speaker-diarization-3.1`, `pyannote/segmentation-3.0` 페이지에서 약관 수락
- [ ] `.env`: `HF_TOKEN=hf_xxx`, `DIARIZER=pyannote`
- [ ] **보안 검토**: HF 토큰=외부 인증 → 조직 정책 확인. 화자 이름은 개인정보(secure 회의 유의)
- [ ] 화자분리 불필요/토큰 미승인 시 → `DIARIZER=off`(단일 화자로 진행)
- [ ] 폐쇄망: 게이트 모델은 인증+네트워크 필요 → 사전 반입

## 4. LLM — Ollama(로컬) / ~~Gemini~~  `[필수]`

| 육하 | 내용 |
|---|---|
| **왜** | 전사문 → 구조화 회의록(요약·결정·액션 추출). 시스템의 최종 산출 |
| **누가** | 개발자/운영자 |
| **언제** | 회의록 생성 단계(항상). 모델 pull은 최초 1회(완료) |
| **어디서** | Windows 로컬 `localhost:11434`. 모델은 Ollama 저장소 |
| **무엇을** | ① Ollama 실행 확인 ② 모델 준비(`qwen2.5:7b` 완료) ③ 프로파일 매핑 확인 |
| **어떻게** | `--profile secure`→Ollama, `internal`→키 없으면 Ollama 폴백. Gemini 원하면 키 설정 |

- [x] Ollama 설치 + `ollama pull qwen2.5:7b` (완료)
- [ ] Ollama 서비스 실행 확인: `ollama list` / `curl http://localhost:11434/api/tags`
- [ ] (고품질 필요 시) `ollama pull qwen2.5:14b` + `.env` `OLLAMA_MODEL=qwen2.5:14b`
- [ ] ~~Gemini(클라우드)~~ → **무료·정책상 기본 제외**. 둘 다 로컬 Ollama로 검증
      (내부회의를 굳이 Gemini로 쓸 거면: aistudio.google.com/apikey → `GEMINI_API_KEY`)

## 5. 오케스트레이션 — n8n Community `[네이티브 전환·후순위]`

| 육하 | 내용 |
|---|---|
| **왜** | 폴더감시/웹훅 → 전사 → 생성 → 배포 자동화(사람이 CLI 반복 안 하게) |
| **누가** | 운영자/개발자 |
| **언제** | **후순위** — 실오디오 CLI로 "수동 5회 성공" 검증 후. 초기엔 불필요 |
| **어디서** | Windows 로컬. Node.js 필요. 데이터 `%USERPROFILE%\.n8n` |
| **무엇을** | ① **Docker 대신 네이티브 설치** ② 워크플로우 import ③ **도커 경로→Windows 경로 수정** |
| **어떻게** | Node.js LTS → `npm i -g n8n` → `n8n start` → :5678 UI에서 JSON import |

- [ ] Node.js LTS 설치 → `npm install -g n8n`(또는 `npx n8n`) → `n8n start`
- [ ] http://localhost:5678 접속 → 워크플로우 import
- [ ] **⚠️ 워크플로우 수정 필수**: `workflows/*.json`의 Execute Command가 도커 경로
      (`$MINUTES_PY`, `$MINUTES_HOME`, `/data/inbox`, `/data/out`)를 전제 →
      Windows 경로(`.venv\Scripts\python`, `<repo>`, `data\inbox`, `data\out`)로 교체 필요
      → **별도 작업 항목(§7)**
- [ ] `docker-compose.yml`은 정책상 **미사용**

## 6. 봇 참석 — Vexa (셀프호스팅) `[보류 권장]`

| 육하 | 내용 |
|---|---|
| **왜** | 온라인 회의(Meet/Zoom/Teams)에 봇이 자동 참석해 오디오/전사 수집 |
| **누가** | 인프라/보안 |
| **언제** | **최후순위**. 로컬 파이프라인 완성 후 |
| **어디서** | **Docker 다중 컨테이너 필요** → 현재 정책(Docker 금지)과 **직접 충돌** |
| **무엇을** | 정책 유지 시 **보류**, 대신 회의 녹음 수동 확보 → Phase 2 투입 |
| **어떻게** | (대안) 회의 녹음(.m4a)을 사람이 저장 → `minutes.pipeline --audio`. (봇 필수 시) Docker 예외 호스트 별도 협의 |

- [ ] **결정 필요**: (A) 봇 없이 수동 녹음 파이프라인으로 운영 / (B) Vexa용 Docker 예외 호스트 승인
- [ ] (A 선택 시) 회의 녹음 확보 표준 절차 수립(어떤 도구로 녹음·저장·반입)
- [ ] (B 선택 시) 격리 호스트에 Vexa 공식 스택 배포 + 보안 검토(외부 미팅 접속 경로)

---

## 7. 파생 작업 (정책 대응으로 새로 생김)

- [ ] **n8n 워크플로우 Windows 네이티브 버전** 작성 — Execute Command 경로/명령을 로컬 venv·상대경로로.
      (원하면 `workflows/*_local.json` 로 만들어 드림)
- [ ] **폐쇄망 설치 절차(wheelhouse)** — 인터넷 PC에서 `uv pip download`로 휠 수집 → 오프라인 `--find-links` 설치.
      (transcribe 설치 자체는 네트워크 필요하므로 air-gapped면 필수)

## 우선순위 요약

1. **§1 Python/uv → §2 전사 → §4 LLM** = 최소 로컬 파이프라인(오디오→회의록). **여기까지가 1차 목표.**
2. **§3 화자분리** = 품질(토큰/동의 되면 켜기, 안 되면 off로 우회).
3. **§5 n8n(네이티브)** = 자동화, CLI 검증 후.
4. **§6 Vexa** = 보류/결정.
