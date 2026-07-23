<#
run_local.ps1 — 무료·로컬 원커맨드 실행기 (Windows PowerShell)

uv가 없어도 python -m venv 로 폴백한다.

사용 예:
  powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -SetupOnly
  powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Mock
  powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Audio 회의.m4a -Profile secure
#>
param(
  [string]$Audio = "",
  [ValidateSet("secure","internal")][string]$Profile = "secure",
  [string]$Title = "",
  [string]$Date = "",
  [switch]$Minimal,
  [switch]$Mock,
  [switch]$SetupOnly,
  [switch]$Reinstall
)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Info($m){ Write-Host "▶ $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "⚠ $m" -ForegroundColor Yellow }
function Ok($m){ Write-Host "✓ $m" -ForegroundColor Green }

# python 찾기
$PyBoot = @("python","python3","py") | Where-Object { Get-Command $_ -ErrorAction SilentlyContinue } | Select-Object -First 1
if (-not $PyBoot) { throw "python을 찾을 수 없습니다. Python 3.11+ 설치 필요." }

# venv
if (-not (Test-Path ".venv")) {
  Info "가상환경(.venv) 생성"
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv } else { & $PyBoot -m venv .venv }
}
$VPy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VPy)) { throw ".venv 파이썬을 찾을 수 없습니다." }

# 설치
$Extras = if ($Minimal) { ".[dev]" } else { ".[dev,transcribe]" }
$Have = $false
if (-not $Reinstall) {
  & $VPy -c "import minutes" 2>$null
  if ($LASTEXITCODE -eq 0) {
    if ($Minimal) { $Have = $true }
    else { & $VPy -c "import faster_whisper" 2>$null; if ($LASTEXITCODE -eq 0){ $Have = $true } }
  }
}
if (-not $Have) {
  Info "의존성 설치: $Extras  (transcribe는 torch 포함 — 시간이 걸릴 수 있음)"
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv pip install --python $VPy -e $Extras }
  else { & $VPy -m pip install --upgrade pip; & $VPy -m pip install -e $Extras }
  Ok "설치 완료"
} else { Ok "의존성 이미 설치됨 (재설치는 -Reinstall)" }

# .env / 폴더
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Ok ".env 생성 (무료·로컬 프리셋)" }
New-Item -ItemType Directory -Force -Path "data\inbox","data\out" | Out-Null

# 사전 점검
if (-not $Mock) {
  if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Warn "ffmpeg 미설치 — 실제 오디오 전사에 필요. winget install Gyan.FFmpeg"
  }
  if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Ok "ollama 확인 — 모델 필요 시: ollama pull qwen2.5:7b"
  } else {
    Warn "ollama 미설치 — secure/로컬 LLM에 필요. https://ollama.com"
  }
}

if ($SetupOnly) { Ok "셋업 완료 (-SetupOnly)"; exit 0 }

function Run-Pipeline($audioPath) {
  $args = @("-m","minutes.pipeline","--audio",$audioPath,"--profile",$Profile)
  if ($Title) { $args += @("--title",$Title) }
  if ($Date)  { $args += @("--date",$Date) }
  & $VPy @args
}

if ($Mock) {
  Info "오프라인 데모 (mock 엔진)"
  $Demo = if ($Audio) { $Audio } else { "demo.m4a" }
  New-Item -ItemType File -Force -Path $Demo | Out-Null
  $env:ASR_ENGINE="mock"; $env:DIARIZER="mock"; $env:LLM_PROVIDER="mock"
  Run-Pipeline $Demo
  Ok "데모 산출물: $([IO.Path]::ChangeExtension($Demo,'minutes.md'))"
  exit 0
}

if ($Audio) {
  if (-not (Test-Path $Audio)) { throw "오디오 파일이 없습니다: $Audio" }
  Info "완전 로컬 파이프라인 실행 [profile=$Profile]"
  Run-Pipeline $Audio
  Ok "산출물: transcript.json / minutes.json / minutes.md"
} else {
  Warn "실행할 오디오가 없습니다. 예: -Audio 회의.m4a  또는 -Mock"
}
