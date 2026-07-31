@echo off
setlocal
chcp 65001 >nul
REM =====================================================================
REM  회의록 봇 - 원클릭 실행 (Windows)
REM  Docker Desktop + Vexa(WSL) + STT 전사 유닛 + 웹 대시보드를 한 번에.
REM
REM  * 최초 1회 설치(WSL/Docker/Vexa/venv/.env/키 발급)는 끝나 있어야 함.
REM    이 파일은 "설치"가 아니라 "켜기" 전용 — 재부팅 후 더블클릭만 하면 됨.
REM  * Vexa 를 ~/vexa 가 아닌 곳에 뒀으면 아래 VEXA_DIR 만 바꾸세요.
REM  * WSL 배포판이 Ubuntu 가 아니면 아래 wsl 호출에 -d 이름 추가.
REM =====================================================================

set "REPO=%~dp0.."
set "VEXA_DIR=~/vexa"

echo(
echo [1/4] Docker 엔진 확인...
wsl -e bash -c "docker info >/dev/null 2>&1"
if errorlevel 1 (
  echo    Docker 가 꺼져 있어 Docker Desktop 을 실행합니다...
  start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
)
:waitdocker
wsl -e bash -c "docker info >/dev/null 2>&1" && goto dockerready
echo    Docker 엔진 뜰 때까지 대기 중... (처음엔 30초~1분)
timeout /t 3 >nul
goto waitdocker
:dockerready
echo    Docker 준비 완료.

echo(
echo [2/4] STT 전사 유닛 기동 (포트 8083)...
wsl -e bash -c "cd %VEXA_DIR%/deploy/transcription && docker compose up -d"

echo(
echo [3/4] Vexa 스택 기동 (게이트웨이 18056)...  ※ make 아님 - 키 안 바뀜
wsl -e bash -c "cd %VEXA_DIR%/deploy/compose && docker compose up -d"

echo(
echo [4/4] 웹 대시보드 시작 → 브라우저 열기
start "" http://127.0.0.1:8900/
cd /d "%REPO%"
".venv\Scripts\python.exe" -m minutes.server

REM 대시보드는 이 창에서 계속 실행됩니다. 종료하려면 이 창에서 Ctrl+C 또는 창 닫기.
endlocal
