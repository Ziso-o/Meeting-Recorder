# 회사 PC(무 GPU)에 Vexa 셀프호스팅 — CPU 모드

> 목표: GPU 없는 PC에서도 **봇 참석 + 전사**를 셀프호스팅으로. 완전 무료.
> 전사는 **CPU 모드**(느림) — 짧은 회의/테스트 위주. 실운영 고품질은 GPU PC 권장.
>
> ⚠️ **사양 확인 먼저**(🐧 WSL): `nproc && free -h` → Docker 권장 **8 vCPU / 16 GB**.
> 부족하면 컨테이너가 버벅이거나 뜨지 않을 수 있음.
>
> 이 문서는 집 PC 셋업에서 실제로 밟은 함정을 모두 반영함:
> STT는 CPU compose로, 전사설정은 `deploy/compose/.env`(우리 .env 아님)에,
> 키는 admin으로 발급(영구), `make down`/`make all` 금지(키 churn 원인).

## 1. WSL2 + Docker Desktop  (🟦 PowerShell 관리자)
```powershell
wsl --install          # 우분투 설치 → 재부팅
```
Docker Desktop 설치 → **Settings → Resources → WSL Integration**에서 **Ubuntu 토글 ON** → Apply & Restart.
(트레이 고래 아이콘이 떠 있어야 함)

## 2. Vexa 받기  (🐧 Ubuntu/WSL)
```bash
sudo apt update && sudo apt install -y make git
cd ~ && git clone https://github.com/Vexa-ai/vexa.git
```

## 3. STT 전사 유닛 — CPU 모드  (🐧 Ubuntu/WSL)
```bash
cd ~/vexa/deploy/transcription
cp .env.example .env
# .env 편집: 아래 두 줄 맞추기
#   API_TOKEN=아무_긴_문자열(기억)
#   MODEL_SIZE=small        # CPU면 small 또는 tiny (large는 너무 느림)
docker compose -f docker-compose.cpu.yml up -d      # ★ CPU 전용 compose
curl http://localhost:8083/health                   # OK/healthy 확인
```

## 4. 메인 Vexa 스택 + STT 연결  (🐧 Ubuntu/WSL)
```bash
cd ~/vexa/deploy/compose
# ★ 전사설정은 '이 파일'(deploy/compose/.env)에 넣는다 — 오타 주의(TRANSCRIPTION, 앞 T!)
sed -i '/RANSCRIPTION_SERVICE_URL/d; /TRANSCRIPTION_SERVICE_TOKEN/d' .env
cat >> .env <<'EOF'
TRANSCRIPTION_SERVICE_URL=http://host.docker.internal:8083
TRANSCRIPTION_SERVICE_TOKEN=여기에_3번의_API_TOKEN_동일하게
EOF
grep TRANSCRIPTION .env          # 두 줄, 오타 없이 확인
docker compose up -d             # ★ make down 하지 말 것 (키 유지)
```

## 5. 고정 API 키 발급 (admin, bot+tx scope)  (🐧 Ubuntu/WSL)
```bash
ADMIN=$(grep -E '^ADMIN_TOKEN=' ~/vexa/deploy/compose/.env | cut -d= -f2)
[ -z "$ADMIN" ] && ADMIN=dev-admin-token
uid=$(curl -s -X POST http://localhost:18057/admin/users \
  -H "X-Admin-API-Key: $ADMIN" -H "Content-Type: application/json" \
  -d '{"email":"me@local.test","name":"me","max_concurrent_bots":1}' \
  | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
[ -z "$uid" ] && uid=$(curl -s "http://localhost:18057/admin/users/email/me@local.test" \
  -H "X-Admin-API-Key: $ADMIN" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
echo "user_id=$uid"
curl -s -X POST "http://localhost:18057/admin/users/$uid/tokens?scopes=bot,tx" \
  -H "X-Admin-API-Key: $ADMIN"; echo
#  → {"token":"vxa_..."}  ← 이 값 복사 (DB 영구 저장, 재기동해도 유지)
```

## 6. 우리 대시보드 `.env`  (🟢 Git Bash)
```bash
cd ~/Meeting-Recorder
grep -q '^VEXA_API_URL=' .env && sed -i 's|^VEXA_API_URL=.*|VEXA_API_URL=http://localhost:18056|' .env || echo 'VEXA_API_URL=http://localhost:18056' >> .env
grep -q '^VEXA_API_KEY=' .env && sed -i 's|^VEXA_API_KEY=.*|VEXA_API_KEY=여기에_5번_vxa_토큰|' .env || echo 'VEXA_API_KEY=여기에_5번_vxa_토큰' >> .env
sed -i 's|^VEXA_CLIENT=mock|# VEXA_CLIENT=mock|' .env      # 실제 모드
grep VEXA .env
# 서버 재시작
.venv/Scripts/python -m minutes.server
```
> LLM(회의록)은 로컬 Ollama 권장: `ollama pull qwen2.5:3b` + `.env`에 `OLLAMA_MODEL=qwen2.5:3b`.

## 7. 검증
대시보드 → 흉내 모드 OFF → **Google Meet** 링크로 참석 → 참석자에 `회의록봇` 등장 → 회의 종료 시 자동 회의록.

---

## 재부팅 후
`make` 쓰지 말고 아래만 (키·설정 유지):
```bash
cd ~/vexa/deploy/transcription && docker compose -f docker-compose.cpu.yml up -d
cd ~/vexa/deploy/compose && docker compose up -d
```
(또는 `Meeting-Recorder/scripts/start_windows.bat` — 단 이 bat은 STT를 GPU compose로 올리므로,
CPU 모드면 STT 줄을 `-f docker-compose.cpu.yml`로 바꿔서 쓰세요.)

## 트러블슈팅 (집 PC에서 실제로 겪은 것들)
| 증상 | 원인 / 해결 |
|---|---|
| `docker: not found` (WSL) | Docker Desktop WSL Integration에서 Ubuntu 토글 ON |
| 503 `no transcription backend` | STT 설정을 **deploy/compose/.env**(우리 .env 아님)에, 오타(앞 T) 확인, 스택 `up -d` |
| 401 `Invalid API key` | 키가 죽음 → `make all` 재실행 금지, admin으로 재발급(5번) |
| 403 `Insufficient scope` | 토큰 scope에 `tx` 포함(`?scopes=bot,tx`) |
| 404 `Meeting not found` | 참석 때와 같은 플랫폼/링크. 대시보드는 링크로 자동 인식 |
| 봇 입장 못 함 | `teams.live.com`(개인) 말고 **Google Meet**로 |
| 전사가 너무 느림/밀림 | CPU 한계 → MODEL_SIZE `tiny`, 짧은 회의로. 고품질은 GPU PC |
