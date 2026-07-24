#!/usr/bin/env bash
# home_pc_setup.sh — 집 GPU PC 셋업 자동화(가능한 부분). Git Bash에서 실행.
#   bash scripts/home_pc_setup.sh
# 자동: 코드 최신화 → venv → [transcribe] 설치 → ollama 모델 → .env 준비 → pytest
# 수동(스크립트 밖, GUI): NVIDIA 드라이버 / WSL2 / Docker Desktop / Vexa 스택 / n8n import
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"; cd "$ROOT"

info(){ printf '\033[36m▶ %s\033[0m\n' "$*"; }
warn(){ printf '\033[33m⚠ %s\033[0m\n' "$*"; }
ok(){   printf '\033[32m✓ %s\033[0m\n' "$*"; }

# ---- 0. 전제 점검 ----
info "전제 도구 점검"
for c in python uv git; do
  command -v "$c" >/dev/null 2>&1 && ok "$c 있음" || { echo "필수 '$c' 없음"; exit 1; }
done
command -v ollama >/dev/null 2>&1 && ok "ollama 있음" || warn "ollama 없음 → https://ollama.com 설치 필요(LLM)"
command -v ffmpeg >/dev/null 2>&1 && ok "ffmpeg 있음" || warn "ffmpeg 없음 → winget install Gyan.FFmpeg (녹음파일 전사용)"
command -v docker >/dev/null 2>&1 && ok "docker 있음" || warn "docker 없음 → Docker Desktop 필요(Vexa 셀프호스팅용)"

# ---- 1. 코드 최신화 ----
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
info "코드 최신화 (origin/$BRANCH)"
git pull --ff-only origin "$BRANCH" || warn "자동 pull 실패 — 수동으로 git pull 확인"

# ---- 2. venv + 설치 ----
if [ ! -d ".venv" ]; then info "venv 생성"; uv venv; fi
if [ -x ".venv/Scripts/python.exe" ]; then VPY=".venv/Scripts/python.exe"     # Windows
elif [ -x ".venv/bin/python" ]; then VPY=".venv/bin/python"                   # Linux/macOS
else echo ".venv python 못 찾음"; exit 1; fi
info "의존성 설치(.[transcribe] — torch 포함, 시간 걸림)"
uv pip install -e ".[transcribe]"
ok "설치 완료"

# ---- 3. Ollama 모델 ----
if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "qwen2.5:14b"; then
    ok "Ollama qwen2.5:14b 이미 있음"
  else
    info "Ollama 모델 내려받기 (qwen2.5:14b — 수 GB)"
    ollama pull qwen2.5:14b || warn "ollama pull 실패 — Ollama 실행 여부 확인"
  fi
fi

# ---- 4. .env 준비 ----
if [ ! -f ".env" ]; then
  cp .env.example .env
  ok ".env 생성 — HF_TOKEN, VEXA_API_KEY 두 줄만 채우세요"
else
  ok ".env 이미 있음(그대로 사용)"
fi
mkdir -p data/incoming data/out

# ---- 5. 테스트 ----
info "테스트"
"$VPY" -m pytest -q

# ---- 6. 다음 단계(수동) 안내 ----
cat <<'NEXT'

========================================================================
✅ 자동 셋업 완료. 이제 수동 단계:

1) .env 키 채우기:      notepad .env   (HF_TOKEN, VEXA_API_KEY)
2) Vexa 셀프호스팅:      docs/VEXA_SELFHOST_WINDOWS.md
                        (Docker Desktop+WSL2 GPU → Vexa 스택 → API 키/포트)
3) HTTP 서비스 (터미널 A, 계속 켜둠):
     export MINUTES_HOME="$PWD"
     .venv/Scripts/python -m minutes.server
4) n8n (터미널 C, 계속 켜둠):
     export MINUTES_SERVER_URL="http://127.0.0.1:8900"
     n8n start
     → 브라우저서 workflows/vexa_meeting_http.json import → Active
5) 실회의 봇 참가 테스트 (터미널 B):
     curl -X POST http://localhost:5678/webhook/bot-dispatch -H "Content-Type: application/json" -d "{\"platform\":\"google_meet\",\"meetingId\":\"<회의코드>\"}"
========================================================================
NEXT
