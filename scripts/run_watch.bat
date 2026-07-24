@echo off
REM ============================================================
REM  run_watch.bat — 24/7 무인 폴더감시 런처 (Windows 네이티브)
REM  data\incoming 감시 → 자동 회의록 → data\out (처리분 data\done)
REM  crash 시 자동 재시작. 작업 스케줄러로 부팅 시 자동 실행 권장.
REM  로그: logs\watch.log
REM ============================================================
setlocal
REM 스크립트 위치 기준 저장소 루트로 이동
cd /d "%~dp0.."

if not exist logs mkdir logs
if not exist data\incoming mkdir data\incoming
if not exist data\out mkdir data\out

set PROFILE=%1
if "%PROFILE%"=="" set PROFILE=secure

:loop
echo [%date% %time%] watch 시작 (profile=%PROFILE%) >> logs\watch.log
".venv\Scripts\python.exe" -m minutes.watch --profile %PROFILE% >> logs\watch.log 2>&1
echo [%date% %time%] watch 종료(code %errorlevel%) — 10초 후 재시작 >> logs\watch.log
timeout /t 10 /nobreak >nul
goto loop
