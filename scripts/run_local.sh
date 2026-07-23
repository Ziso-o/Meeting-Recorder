#!/usr/bin/env bash
# run_local.sh — 무료·로컬 원커맨드 실행기 (Linux / macOS / Windows Git-Bash)
#
# uv가 없어도 python -m venv 로 폴백한다. venv 경로(bin/ vs Scripts/)를 자동 판별한다.
#
# 사용 예:
#   bash scripts/run_local.sh --setup-only              # 설치/셋업만
#   bash scripts/run_local.sh --mock                    # 오프라인 데모(엔진 없이 배관 확인)
#   bash scripts/run_local.sh --audio 회의.m4a           # 완전 로컬 파이프라인(secure)
#   bash scripts/run_local.sh --audio 회의.m4a --profile internal --title "..." --date 2026-07-23
#
# 옵션:
#   --audio PATH     오디오 파일 → pipeline 실행
#   --profile NAME   secure(기본, 로컬 Ollama) | internal
#   --title / --date 회의 메타
#   --minimal        전사 의존성([transcribe]) 제외, 코어만 설치(가벼움)
#   --mock           ASR/DIARIZER/LLM 을 mock 으로(네트워크·GPU·모델 불필요)
#   --setup-only     설치·셋업만 하고 종료
#   --reinstall      의존성 강제 재설치
#   -h | --help

set -euo pipefail

# ---- 저장소 루트로 이동 (스크립트 위치 기준) ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

# ---- 인자 파싱 ----
AUDIO=""; PROFILE="secure"; TITLE=""; DATE=""
MINIMAL=0; MOCK=0; SETUP_ONLY=0; REINSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --audio) AUDIO="${2:-}"; shift 2;;
    --profile) PROFILE="${2:-}"; shift 2;;
    --title) TITLE="${2:-}"; shift 2;;
    --date) DATE="${2:-}"; shift 2;;
    --minimal) MINIMAL=1; shift;;
    --mock) MOCK=1; shift;;
    --setup-only) SETUP_ONLY=1; shift;;
    --reinstall) REINSTALL=1; shift;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 2;;
  esac
done

info()  { printf '\033[36m▶ %s\033[0m\n' "$*"; }
warn()  { printf '\033[33m⚠ %s\033[0m\n' "$*"; }
ok()    { printf '\033[32m✓ %s\033[0m\n' "$*"; }

# ---- python 찾기 ----
PY_BOOT=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then PY_BOOT="$c"; break; fi
done
[ -n "$PY_BOOT" ] || { echo "python을 찾을 수 없습니다. Python 3.11+ 설치 필요." >&2; exit 1; }

# ---- venv 생성 + venv python 경로 판별 (Windows=Scripts, 그 외=bin) ----
if [ ! -d ".venv" ]; then
  info "가상환경(.venv) 생성"
  if command -v uv >/dev/null 2>&1; then uv venv; else "$PY_BOOT" -m venv .venv; fi
fi
if [ -x ".venv/Scripts/python.exe" ]; then VPY=".venv/Scripts/python.exe"   # Windows
elif [ -x ".venv/bin/python" ]; then VPY=".venv/bin/python"                 # Linux/macOS
else echo ".venv 파이썬을 찾을 수 없습니다." >&2; exit 1; fi

# ---- 설치 (uv 있으면 uv, 없으면 pip 폴백) ----
EXTRAS=".[dev]"
[ "$MINIMAL" -eq 1 ] || EXTRAS=".[dev,transcribe]"

NEED_INSTALL=1
if [ "$REINSTALL" -eq 0 ] && "$VPY" -c "import minutes" >/dev/null 2>&1; then
  if [ "$MINIMAL" -eq 1 ] || "$VPY" -c "import faster_whisper" >/dev/null 2>&1; then
    NEED_INSTALL=0
  fi
fi

if [ "$NEED_INSTALL" -eq 1 ]; then
  info "의존성 설치: $EXTRAS  (transcribe는 torch 포함 — 시간이 걸릴 수 있음)"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$VPY" -e "$EXTRAS"
  else
    "$VPY" -m pip install --upgrade pip
    "$VPY" -m pip install -e "$EXTRAS"
  fi
  ok "설치 완료"
else
  ok "의존성 이미 설치됨 (재설치는 --reinstall)"
fi

# ---- .env 준비 ----
if [ ! -f ".env" ]; then
  cp .env.example .env
  ok ".env 생성 (무료·로컬 프리셋). 필요 시 값 수정."
fi
mkdir -p data/inbox data/out

# ---- 사전 점검 ----
if [ "$MOCK" -eq 0 ]; then
  # ffmpeg (실오디오 전사에 필요)
  if ! command -v ffmpeg >/dev/null 2>&1; then
    warn "ffmpeg 미설치 — 실제 오디오 전사에 필요."
    warn "  Windows: winget install Gyan.FFmpeg   |  macOS: brew install ffmpeg   |  Linux: apt install ffmpeg"
  fi
  # Ollama (secure/로컬 LLM에 필요)
  if command -v ollama >/dev/null 2>&1; then
    MODEL="$("$VPY" - <<'PYEOF'
import os, pathlib
env = {}
p = pathlib.Path(".env")
if p.exists():
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln=ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k,_,v=ln.partition("="); env[k.strip()]=v.strip()
print(env.get("OLLAMA_MODEL","qwen2.5:7b"))
PYEOF
)"
    if ! ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
      warn "Ollama 모델 '$MODEL' 미확인 — 필요 시:  ollama pull $MODEL"
    else
      ok "Ollama 모델 '$MODEL' 확인"
    fi
  else
    warn "ollama 미설치 — secure/로컬 LLM에 필요. https://ollama.com (설치 후 'ollama pull qwen2.5:7b')"
  fi
fi

if [ "$SETUP_ONLY" -eq 1 ]; then ok "셋업 완료 (--setup-only)"; exit 0; fi

# ---- 실행 ----
run_pipeline() {
  local audio="$1"
  local args=(--audio "$audio" --profile "$PROFILE")
  [ -n "$TITLE" ] && args+=(--title "$TITLE")
  [ -n "$DATE" ] && args+=(--date "$DATE")
  "$VPY" -m minutes.pipeline "${args[@]}"
}

if [ "$MOCK" -eq 1 ]; then
  info "오프라인 데모 (mock 엔진 — 네트워크/GPU/모델 불필요)"
  DEMO="${AUDIO:-demo.m4a}"; touch "$DEMO"
  ASR_ENGINE=mock DIARIZER=mock LLM_PROVIDER=mock run_pipeline "$DEMO"
  ok "데모 산출물: ${DEMO%.*}.minutes.md"
  exit 0
fi

if [ -n "$AUDIO" ]; then
  [ -f "$AUDIO" ] || { echo "오디오 파일이 없습니다: $AUDIO" >&2; exit 1; }
  info "완전 로컬 파이프라인 실행 [profile=$PROFILE]"
  run_pipeline "$AUDIO"
  ok "산출물: ${AUDIO%.*}.transcript.json / .minutes.json / .minutes.md"
else
  warn "실행할 오디오가 없습니다. 예: bash scripts/run_local.sh --audio 회의.m4a"
  warn "또는 오프라인 데모: bash scripts/run_local.sh --mock"
fi
