#!/usr/bin/env bash
# =====================================================================
#  Vexa 셀프호스팅 자동 설치 (WSL/Ubuntu에서 실행)
#  STT(CPU) 기동 → 전사연결 → 메인스택 → API키 발급 → 대시보드 .env 자동 기입
#
#  전제(자동화 불가, 1회 수동): WSL2 + Docker Desktop 설치 +
#    Docker Desktop > Settings > Resources > WSL Integration 에서 이 배포판 ON.
#  사용:  bash scripts/install_vexa_cpu.sh          # CPU(기본)
#         bash scripts/install_vexa_cpu.sh --gpu     # GPU PC면
# =====================================================================

STT_COMPOSE="-f docker-compose.cpu.yml"
[ "${1:-}" = "--gpu" ] && STT_COMPOSE=""

# 이 스크립트 위치 → repo 루트(Meeting-Recorder). .env 여기에 씀.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO/.env"
VEXA_DIR="$HOME/vexa"

say(){ printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31m[중단] %s\033[0m\n' "$*"; exit 1; }

say "0) 사전 확인"
command -v docker >/dev/null 2>&1 || die "WSL에서 docker 를 못 찾습니다.
  Docker Desktop 을 실행하고, Settings > Resources > WSL Integration 에서
  이 배포판(Ubuntu) 토글을 켠 뒤(Apply & Restart) 다시 실행하세요."
docker info >/dev/null 2>&1 || die "Docker 엔진이 응답하지 않습니다. Docker Desktop 이 실행 중인지 확인하세요."
command -v git  >/dev/null 2>&1 || die "git 이 없습니다:  sudo apt install -y git"
command -v curl >/dev/null 2>&1 || die "curl 이 없습니다:  sudo apt install -y curl"
echo "  docker/git/curl OK · repo=$REPO"

say "1) Vexa 소스"
if [ ! -d "$VEXA_DIR/.git" ]; then
  git clone https://github.com/Vexa-ai/vexa.git "$VEXA_DIR" || die "vexa clone 실패"
else
  echo "  이미 있음: $VEXA_DIR"
fi

say "2) STT 전사 유닛 기동 ${STT_COMPOSE:-(GPU)}"
cd "$VEXA_DIR/deploy/transcription" || die "deploy/transcription 없음"
[ -f .env ] || cp .env.example .env
# API_TOKEN: 이미 값 있으면 재사용, 없으면 생성 (STT<->스택 공용 비밀)
STT_TOKEN="$(grep -E '^API_TOKEN=' .env | cut -d= -f2)"
if [ -z "$STT_TOKEN" ]; then
  STT_TOKEN="vexa-stt-$(date +%s)"
  if grep -q '^API_TOKEN=' .env; then sed -i "s|^API_TOKEN=.*|API_TOKEN=$STT_TOKEN|" .env; else echo "API_TOKEN=$STT_TOKEN" >> .env; fi
fi
if grep -q '^MODEL_SIZE=' .env; then sed -i "s|^MODEL_SIZE=.*|MODEL_SIZE=small|" .env; else echo "MODEL_SIZE=small" >> .env; fi
docker compose $STT_COMPOSE up -d || die "STT compose 실패"
printf '  STT 준비 대기'
for _ in $(seq 1 80); do curl -sf http://localhost:8083/health >/dev/null 2>&1 && { echo " OK"; break; }; printf '.'; sleep 3; done

say "3) 메인 스택 + 전사연결"
cd "$VEXA_DIR/deploy/compose" || die "deploy/compose 없음"
[ -f .env ] || cp .env.example .env
sed -i '/RANSCRIPTION_SERVICE_URL/d; /TRANSCRIPTION_SERVICE_TOKEN/d' .env
{ echo "TRANSCRIPTION_SERVICE_URL=http://host.docker.internal:8083"
  echo "TRANSCRIPTION_SERVICE_TOKEN=$STT_TOKEN"; } >> .env
docker compose up -d || die "메인 스택 compose 실패"
printf '  게이트웨이 대기'
for _ in $(seq 1 80); do curl -s -o /dev/null -m 2 http://localhost:18056/bots/status && { echo " OK"; break; }; printf '.'; sleep 3; done
printf '  admin-api 대기'
for _ in $(seq 1 60); do curl -sf http://localhost:18057/health >/dev/null 2>&1 && { echo " OK"; break; }; printf '.'; sleep 3; done

say "4) API 키 발급 (scope: bot,tx)"
ADMIN="$(grep -E '^ADMIN_TOKEN=' .env | cut -d= -f2)"; [ -z "$ADMIN" ] && ADMIN="dev-admin-token"
uid="$(curl -s -X POST http://localhost:18057/admin/users -H "X-Admin-API-Key: $ADMIN" -H "Content-Type: application/json" \
        -d '{"email":"me@local.test","name":"me","max_concurrent_bots":1}' | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')"
[ -z "$uid" ] && uid="$(curl -s "http://localhost:18057/admin/users/email/me@local.test" -H "X-Admin-API-Key: $ADMIN" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')"
KEY=""
for _ in 1 2 3; do
  KEY="$(curl -s -X POST "http://localhost:18057/admin/users/$uid/tokens?scopes=bot,tx" -H "X-Admin-API-Key: $ADMIN" | grep -o '"token":"[^"]*"' | head -1 | cut -d'"' -f4)"
  [ -n "$KEY" ] && break; sleep 3
done
[ -n "$KEY" ] && echo "  발급됨: ${KEY:0:14}…" || echo "  [경고] 키 발급 실패 — admin 토큰/포트(18057) 확인 필요"

say "5) 대시보드 .env 반영 ($ENV_FILE)"
touch "$ENV_FILE"
set_env(){ if grep -q "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi; }
set_env VEXA_API_URL "http://localhost:18056"
[ -n "$KEY" ] && set_env VEXA_API_KEY "$KEY"
sed -i 's|^VEXA_CLIENT=mock|# VEXA_CLIENT=mock|' "$ENV_FILE" 2>/dev/null || true

say "완료"
echo "  Vexa 게이트웨이 : http://localhost:18056"
echo "  대시보드 .env   : $ENV_FILE  (VEXA_API_URL/KEY 기입, mock 해제)"
[ -n "$KEY" ] && echo "  → 대시보드 재시작 후 실제 모드로 Google Meet 링크 참석하세요." \
              || echo "  → 키 발급이 실패했으니 위 4) 로그를 확인하세요."
echo "  (재부팅 후 켜기: scripts/start_windows_cpu.bat)"
