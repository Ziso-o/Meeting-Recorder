@echo off
setlocal
chcp 65001 >nul
REM =====================================================================
REM  실행 환경 진단 - 이 PC에서 무엇으로 돌려야 빠른지 확인 (더블클릭용)
REM
REM  CPU/GPU/RAM, CUDA 사용 가능 여부, 받아 둔 Whisper 모델, Ollama 상태를
REM  찍고 이 PC에 맞는 .env 값을 알려줍니다. 출력을 그대로 복사해 공유하세요.
REM =====================================================================

set "REPO=%~dp0.."
set "PY=%REPO%\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [오류] 가상환경을 못 찾았습니다: %PY%
  echo        먼저 설치하세요:  uv venv ^&^& uv pip install -e ".[transcribe]"
  echo(
  pause
  exit /b 1
)

"%PY%" "%REPO%\scripts\check_env.py"
echo(
echo ---------------------------------------------------------------
echo  위 내용을 전부 복사해서 공유하시면 됩니다.
echo ---------------------------------------------------------------
pause
