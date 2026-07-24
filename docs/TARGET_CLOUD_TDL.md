# 최종 목표 아키텍처 & TDL (클라우드 · Vexa 봇) — 육하원칙

> **최종 목표(사용자 확정)**: 클라우드에서 Vexa 봇이 회의 참가 → STT 저장 → 회의록 자동작성.
> 사용 모델: Vexa AI · faster-whisper · pyannote (+ **회의록 작성용 LLM은 별도 필수**).
> 배포: **로컬에서 구성·검증 후 클라우드에 적재(n8n)**.

---

## 1. 아키텍처 — 2개 입력 경로가 LLM 회의록으로 수렴

```
[실시간 경로] 온라인 회의(Meet/Teams/Zoom)
     → Vexa 봇 참가 → Vexa STT+화자분리(내장) → 회의종료 웹훅
                                                     │
[파일 경로]  녹음파일 업로드 → faster-whisper + pyannote ──┤
                                                     ▼
                              n8n 오케스트레이션 → LLM 회의록 작성 → 저장/배포/알림
```
- **실시간(Vexa)**: 봇이 회의에 들어가 자체 STT/화자분리 제공 → 우리는 **회의록(LLM)만**.
- **파일(로컬 모델)**: 녹음/민감회의 → 우리 faster-whisper+pyannote → 회의록.
- **두 경로 공통 필수 = LLM 회의록 작성기**(Vexa가 대체 못 함). → 아래 결정 D2.
- 근거: `SESSION_HANDOFF.md §7`(Vexa vs 로컬 모델 역할 정리)와 일치.

---

## 2. ⚠️ 제약 재조정 (이전 로컬 정책 vs 최종 클라우드 타깃)

| 항목 | 이전(로컬 dev) | 최종(클라우드) | 조치 |
|---|---|---|---|
| **가상화** | Docker/VM 금지, Windows 네이티브 | Vexa·n8n = **컨테이너 기반** | 로컬 처리박스=네이티브 유지 / **클라우드 호스트=Docker 허용** 필요 (결정 D3) |
| **비용** | 모든 엔진 무료 | 클라우드 24/7 + GPU + Vexa = **비용 발생** | **완전 무료 불가** 인정 → 예산·무료티어 조합 결정 (결정 D4) |
| **STT** | faster-whisper/pyannote(로컬) | Vexa 내장 STT와 **중복** | 실시간=Vexa, 파일=로컬모델로 **역할 분리**(공존) |
| **LLM** | Ollama(secure)/Gemini(internal) | 모델 목록에 **누락** | 회의록 작성엔 LLM 필수 → 클라우드 LLM 결정 (D2) |

---

## 3. 결정 (Decisions) — ✅ 확정됨

- **D1. Vexa = 셀프호스팅(Docker).** 무료·데이터 자체보관. 봇+STT 자체 처리.
- **D2. LLM = 집 로컬 PC의 Ollama (지포스 50번대 GPU).** 로컬=회의내용 외부유출 없음(secure 적합), GPU라 고성능.
- **D3. Docker = 허용(집 서버 한정).** Vexa/n8n 컨테이너 구동. (⚠️ Windows에선 Docker Desktop+WSL2 필요 — §3.1)
- **D4. 예산 = Phase A 완전 무료(집 GPU PC 자체 서버, 전기료만).** Phase B 배포 시 Vultr 등 임대(유료).
- **D5. 배포 대상 = Phase A: 집 PC / Phase B: Vultr 등 클라우드 GPU 임대.**

### 확정 아키텍처 — Phase A(집 GPU 서버) → Phase B(클라우드 임대)

```
Phase A  [집 PC · 지포스 50번대 · 24/7 자체 서버]
  ├─ Vexa (Docker/WSL2, GPU)      : 봇 참가 + STT + 화자분리
  ├─ Ollama (GPU)                 : 회의록 작성 LLM (qwen2.5:14b+)
  ├─ faster-whisper+pyannote (GPU): 녹음파일 경로 (large-v3)
  └─ n8n                          : 오케스트레이션
        │  (로컬에서 전부 구성·검증)
        ▼
Phase B  [Vultr 등 클라우드 GPU 임대]  ← 동일 스택 이관(docker compose + 시크릿)
```

### 3.1 ⚠️ Vexa 셀프호스팅 on Windows — 진짜 관문
- Vexa 스택은 **Linux 컨테이너** 기반 → Windows에선 **Docker Desktop + WSL2**(경량 VM) 필요.
  (이전 "Docker/VM 금지"는 로컬 처리박스 한정. Vexa 서버엔 예외 적용 — D3.)
- Vexa 내장 STT(whisperlive)는 **GPU 사용** → **WSL2 GPU 패스스루(NVIDIA CUDA on WSL2)** 설정 필요.
  지포스 50번대는 최신 드라이버 필요(WSL2 CUDA 지원 드라이버 확인).
- 대안: 집에 여유 Linux 머신/듀얼부팅이 있으면 **네이티브 Linux Docker**가 GPU·안정성 면에서 더 쉬움.

### 3.2 GPU 상향에 따른 모델 재설정 (small→large)
- 지포스 50번대 GPU이므로 CPU용 축소설정 불필요:
  - `.env`: `WHISPER_MODEL=large-v3` (기존 small에서 상향), `OLLAMA_MODEL=qwen2.5:14b`(또는 32b)
  - `ASR_ENGINE=faster-whisper`(GPU 자동), `DIARIZER=pyannote`

### 3.3 B2G 보안 유의 (참고)
- 집 PC는 **개발·PoC용**으로 적합. 실제 B2G 공공회의 운영은 **망분리·CSAP·개인정보(화자명)**
  요건상 별도 인증 인프라가 필요할 수 있음(Phase B에서 검토).

---

## 4. 현 상황 gap 분석 (Done vs Needed)

| 구성요소 | 코드/검증 상태 | 최종 타깃까지 남은 것 |
|---|---|---|
| Vexa 봇 연동 | ✅ 클라이언트/CLI(`bot.py`)·변환기 — **mock만** 검증 | ❌ **실제 Vexa 배포 + 실회의 봇참가 미검증** |
| STT(파일) | ✅ faster-whisper+pyannote 실오디오 검증 | 클라우드 이관 시 GPU/모델 반입 |
| 회의록(LLM) | ✅ Ollama 실검증 | 클라우드 LLM 결정·배치(D2) |
| n8n 워크플로우 | ⚠️ JSON 존재하나 **Docker경로 전제·미검증** | 실 Vexa/LLM 연동 검증 + 클라우드 이관 |
| 클라우드 인프라 | ❌ 없음 | 서버·네트워크·시크릿·도메인·인증서 |

**요약: 코드 골격은 있으나 "실제 Vexa 배포 + 실회의 + 클라우드"는 전부 미착수.**

---

## 5. 육하원칙 TDL (단계별)

### STEP 1. 봇 참여 — Vexa
| 육하 | 내용 |
|---|---|
| 왜 | 사람 없이 온라인 회의에 봇이 들어가 오디오/STT 확보 |
| 누가 | 인프라/운영자(배포), Vexa 봇(참가) |
| 언제 | 로컬 검증 → 클라우드. 회의 시작 시 dispatch |
| 어디서 | **집 PC**의 Vexa 셀프호스팅(Docker Desktop+WSL2, GPU) |
| 무엇을 | Vexa 공식 스택 기동 → API 키 발급 → `bot request`로 회의 참가 |
| 어떻게 | Vexa 공식 레포 compose로 집 PC에 기동(WSL2 GPU) → 실회의 1건 봇참가 검증 → `minutes.bot request` 연동 |

- [ ] **집 PC에 Docker Desktop+WSL2 + NVIDIA CUDA(WSL2) 세팅** (50번대 드라이버)
- [ ] Vexa 공식 스택(github.com/Vexa-ai/vexa) 집 PC 기동 + API 키
- [ ] `docker-compose.yml`의 `VEXA_IMAGE`/`VEXA_API_URL`/`VEXA_API_KEY` 실값 반영
- [ ] 실제 회의(Meet 등)에 봇 참가 성공 1건 (mock 졸업)
- [ ] `minutes.bot request/stop` 실 API 연동 확인

### STEP 2. STT 기록/저장
| 육하 | 내용 |
|---|---|
| 왜 | 발화를 화자별 텍스트로 확보(회의록 입력) |
| 누가 | Vexa(실시간) / faster-whisper+pyannote(파일) |
| 언제 | 회의 중(실시간) / 회의 후(파일) |
| 어디서 | Vexa 컨테이너 / 우리 파이프라인(GPU 권장) |
| 무엇을 | Vexa 전사 조회·저장, 또는 녹음→로컬 전사 |
| 어떻게 | `minutes.bot transcript`로 Vexa 전사 저장 → `vexa_to_segments`로 스키마 통일. 품질 비교는 `scripts/ab_transcribe.py` |

- [ ] Vexa 실 전사 조회·저장 검증(실회의)
- [ ] (선택) Vexa STT vs faster-whisper A/B로 품질 확인 → 실시간 STT 채택안 확정
- [ ] 전사 영구 저장 위치(파일/DB) 결정

### STEP 3. 회의록 작성 — LLM (⚠️ 모델 목록 누락분)
| 육하 | 내용 |
|---|---|
| 왜 | STT는 '받아쓰기'일 뿐, 구조화 회의록은 LLM이 작성 |
| 누가 | LLM(Ollama/Gemini) |
| 언제 | 회의 종료 후(웹훅 트리거) |
| 어디서 | **집 PC의 Ollama(GPU)** — `qwen2.5:14b+` |
| 무엇을 | 3단 체인(용어교정→요약→통합) — 이미 구현됨 |
| 어떻게 | `minutes.bot ingest`(Vexa전사→회의록) 재사용. profile=secure(로컬 Ollama) |

- [x] LLM 회의록 3단 체인 구현·실검증(Ollama)
- [ ] GPU에 맞춰 `OLLAMA_MODEL=qwen2.5:14b` 상향 pull + 품질 확인
- [ ] Vexa 전사 → `ingest` 실연동(집 PC)

### STEP 4. 오케스트레이션 — n8n
| 육하 | 내용 |
|---|---|
| 왜 | 봇dispatch·회의종료 웹훅·회의록·배포·알림을 자동 연결 |
| 누가 | 운영자(구성), n8n(실행) |
| 언제 | 로컬 구성·검증 → 클라우드 적재 |
| 어디서 | 로컬 n8n → 클라우드 n8n(컨테이너/n8n Cloud) |
| 무엇을 | `workflows/vexa_meeting.json` 실연동 검증 후 이관 |
| 어떻게 | 로컬에서 실 Vexa+LLM로 워크플로우 검증 → 경로/시크릿을 클라우드용으로 치환 → 적재 |

- [ ] `vexa_meeting.json`을 **실제 Vexa/LLM**과 로컬 연동 검증(현재 미검증)
- [ ] 웹훅 공개 경로(도메인/HTTPS) + 인증
- [ ] 클라우드 n8n 이관(환경변수·시크릿 재설정)

### STEP 5. 클라우드 적재 (로컬 검증 완료 후)
| 육하 | 내용 |
|---|---|
| 왜 | 24/7 상시·외부 회의 접속(집 PC 한계 넘어설 때) |
| 누가 | 인프라/보안 |
| 언제 | **Phase A(집 PC) 검증 완료 후** |
| 어디서 | **Vultr 등 클라우드 GPU 임대**(B2G 실운영이면 CSAP 고려) |
| 무엇을 | 동일 docker 스택 이관 + 서버·네트워크·시크릿·도메인·모니터링 |
| 어떻게 | 집 PC에서 검증한 compose를 Vultr GPU 인스턴스로 이관, `.env`→시크릿, HTTPS/도메인 |

- [ ] Vultr(등) GPU 인스턴스 사양·요금 산정
- [ ] 집 PC 스택 → 클라우드 이관(compose/시크릿/도메인)
- [ ] 보안(B2G): 접근통제·개인정보(화자명)·(실운영 시) 망분리/CSAP

---

## 6. 권장 진행 순서 (결정 확정 반영)

**Phase A — 집 GPU PC 자체 서버 (지금)**
1. **집 PC 환경**: Docker Desktop + WSL2 + NVIDIA CUDA(WSL2) + 50번대 드라이버
2. **모델 상향**: `.env` `WHISPER_MODEL=large-v3`, `ollama pull qwen2.5:14b` → `OLLAMA_MODEL=qwen2.5:14b`
3. **Vexa 셀프호스팅**: 공식 스택 집 PC 기동 → API 키 → 실회의 봇참가 1건 (mock 졸업) ← **다음 관문**
4. **`vexa_meeting.json` 실연동 검증**: Vexa전사 → `ingest` → 회의록 → 배포/알림
5. **24/7**: 집 PC에서 n8n/Vexa/Ollama 상시 구동(전원·오토스타트)

**Phase B — 클라우드 임대 (나중)**
6. Vultr 등 GPU 인스턴스로 동일 스택 이관 + 시크릿/도메인/보안

> 현재는 "코드 골격 + 파일경로 실검증"까지. **다음 단일 관문 = 집 PC에 Vexa 셀프호스팅 세우고
> 실제 회의에 봇을 넣는 것.** 여기가 mock을 졸업하는 지점이다.
