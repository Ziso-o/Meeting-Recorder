@echo off
setlocal
chcp 65001 >nul
echo ============================================================
echo   회의록 봇 - Vexa 자동 설치 (CPU 모드)
echo   STT 기동 - 전사연결 - 스택 - API키 발급 - .env 기입 전부 자동
echo.
echo   전제(1회 수동): Docker Desktop 실행 +
echo     Settings ^> Resources ^> WSL Integration 에서 Ubuntu 토글 ON
echo ============================================================
echo.

REM 이 배치와 같은 폴더의 install_vexa_cpu.sh 를 WSL 경로로 바꿔 실행
set "SCRIPT_WIN=%~dp0install_vexa_cpu.sh"
for /f "usebackq delims=" %%i in (`wsl wslpath -u "%SCRIPT_WIN%"`) do set "SCRIPT_WSL=%%i"

if "%SCRIPT_WSL%"=="" (
  echo [주의] WSL 경로 변환 실패 - WSL/Ubuntu 가 설치돼 있는지 확인하세요.
  pause & exit /b 1
)

REM 윈도우 체크아웃 시 붙는 CR(\r) 제거 후 실행 (bash가 $'\r' 로 죽는 것 방지)
wsl -e bash -c "sed -i 's/\r$//' '%SCRIPT_WSL%'"
wsl -e bash "%SCRIPT_WSL%"

echo.
echo 설치 스크립트가 끝났습니다. 위 메시지를 확인하세요.
echo 성공했으면 대시보드를 재시작하고 실제 모드로 참석하면 됩니다.
pause
endlocal
