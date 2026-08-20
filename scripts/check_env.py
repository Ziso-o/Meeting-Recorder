"""실행 환경 진단 — 이 PC에서 무엇으로 돌려야 빠른지 판단할 근거를 모은다.

    python scripts/check_env.py

CPU/GPU/RAM, CTranslate2·torch가 실제로 보는 것, 이미 받아 둔 Whisper 모델,
Ollama 상태를 찍고 **권장 설정**을 제안한다. 추가 의존성 없이 표준 라이브러리로만 돈다
(faster-whisper 등은 있으면 쓰고 없으면 건너뛴다).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

OK, NO, WARN = "✓", "✗", "!"


def head(title: str) -> None:
    print(f"\n{'─' * 62}\n{title}\n{'─' * 62}")


def run(cmd: list[str], timeout: float = 15) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (out.stdout or out.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------- 하드웨어
def cpu_info() -> dict:
    info = {"name": platform.processor() or platform.machine(),
            "logical": os.cpu_count() or 0, "physical": 0, "ram_gb": 0.0}
    if platform.system() == "Windows":
        script = (
            "$c=Get-CimInstance Win32_Processor|Select-Object -First 1;"
            "$m=(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory;"
            "ConvertTo-Json @{name=$c.Name;cores=$c.NumberOfCores;"
            "logical=$c.NumberOfLogicalProcessors;ram=$m}"
        )
        ps = run(["powershell", "-NoProfile", "-Command", script])
        try:
            d = json.loads(ps)
            info.update(name=str(d.get("name", "")).strip(), physical=int(d.get("cores") or 0),
                        logical=int(d.get("logical") or info["logical"]),
                        ram_gb=round(int(d.get("ram") or 0) / 1024**3, 1))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    else:
        try:
            txt = Path("/proc/cpuinfo").read_text()
            for line in txt.splitlines():
                if line.startswith("model name"):
                    info["name"] = line.split(":", 1)[1].strip()
                    break
            info["physical"] = len({
                ln.split(":")[1].strip() for ln in txt.splitlines() if ln.startswith("core id")
            }) or 0
            mem = Path("/proc/meminfo").read_text().splitlines()[0]
            info["ram_gb"] = round(int(mem.split()[1]) / 1024**2, 1)
        except (OSError, IndexError, ValueError):
            pass
    return info


def gpu_info() -> list[str]:
    if shutil.which("nvidia-smi"):
        out = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                   "--format=csv,noheader"])
        if out and "not found" not in out.lower():
            return [ln.strip() for ln in out.splitlines() if ln.strip()]
    if platform.system() == "Windows":
        out = run(["powershell", "-NoProfile", "-Command",
                   "(Get-CimInstance Win32_VideoController).Name"])
        return [ln.strip() for ln in out.splitlines() if ln.strip()]
    return []


# ---------------------------------------------------------------- 런타임
def nvidia_hint(gpus: list[str]) -> bool:
    return any(k in g.lower() for g in gpus
               for k in ("nvidia", "geforce", "rtx", "quadro", "tesla"))


def runtime_info() -> dict:
    r: dict = {}
    try:
        import ctranslate2

        r["ct2"] = ctranslate2.__version__
        r["cuda_count"] = ctranslate2.get_cuda_device_count()
        r["cpu_types"] = sorted(ctranslate2.get_supported_compute_types("cpu"))
        if r["cuda_count"]:
            r["cuda_types"] = sorted(ctranslate2.get_supported_compute_types("cuda"))
    except Exception as e:  # noqa: BLE001
        r["ct2_error"] = f"{type(e).__name__}: {e}"
    try:
        import torch

        r["torch"] = torch.__version__
        r["torch_cuda"] = torch.cuda.is_available()
    except Exception as e:  # noqa: BLE001
        r["torch_error"] = f"{type(e).__name__}: {e}"
    try:
        import faster_whisper

        r["fw"] = faster_whisper.__version__
        r["batched"] = hasattr(faster_whisper, "BatchedInferencePipeline")
    except Exception as e:  # noqa: BLE001
        r["fw_error"] = f"{type(e).__name__}: {e}"
    return r


#: 후보 모델 — 실제로 받을 수 있는지 이 PC에서 확인한다(추측 금지).
CANDIDATES = [
    ("Systran/faster-whisper-large-v3", "large-v3", "최고 품질 · 가장 느림"),
    ("deepdml/faster-whisper-large-v3-turbo-ct2", "large-v3-turbo", "large급 품질 · 훨씬 빠름"),
    ("Systran/faster-whisper-medium", "medium", "무난한 절충"),
    ("Systran/faster-whisper-small", "small", "빠름 · 고유명사 약함"),
]


def model_availability() -> list[tuple[str, str, str, bool | None, bool]]:
    from minutes.asr.info import is_model_cached

    try:
        from huggingface_hub import HfApi

        api = HfApi()
    except Exception:  # noqa: BLE001
        api = None
    rows = []
    for repo, short, note in CANDIDATES:
        reachable: bool | None = None
        if api is not None:
            try:
                api.model_info(repo, timeout=10)
                reachable = True
            except Exception:  # noqa: BLE001  없거나 네트워크 문제
                reachable = False
        rows.append((repo, short, note, reachable, is_model_cached(repo)))
    return rows


def ollama_info(host: str) -> dict:
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/api/tags", timeout=5) as r:
            data = json.load(r)
        return {"up": True, "models": [m.get("name", "?") for m in data.get("models", [])]}
    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as e:
        return {"up": False, "error": str(e)}


# ---------------------------------------------------------------- 리포트
def main() -> int:
    from minutes.config import load_dotenv

    load_dotenv()

    cpu, gpus, rt = cpu_info(), gpu_info(), runtime_info()
    nvidia = [g for g in gpus if nvidia_hint([g])]
    cuda_usable = bool(rt.get("cuda_count")) or bool(rt.get("torch_cuda"))

    head("하드웨어")
    print(f"  OS       : {platform.system()} {platform.release()}")
    print(f"  CPU      : {cpu['name']}")
    print(f"  코어     : 물리 {cpu['physical'] or '?'} / 논리 {cpu['logical']}")
    print(f"  RAM      : {cpu['ram_gb'] or '?'} GB")
    print(f"  GPU      : {', '.join(gpus) if gpus else '(감지 안 됨)'}")

    head("전사 런타임")
    if "ct2" in rt:
        print(f"  {OK} CTranslate2 {rt['ct2']} · CUDA 장치 {rt['cuda_count']}개")
        print(f"      CPU 지원 연산: {', '.join(rt['cpu_types'])}")
        if rt.get("cuda_types"):
            print(f"      GPU 지원 연산: {', '.join(rt['cuda_types'])}")
    else:
        print(f"  {NO} CTranslate2 없음 — {rt.get('ct2_error')}")
    if "torch" in rt:
        print(f"  {OK if rt['torch_cuda'] else WARN} torch {rt['torch']} · CUDA "
              f"{'사용 가능' if rt['torch_cuda'] else '없음(CPU)'}")
    if "fw" in rt:
        print(f"  {OK} faster-whisper {rt['fw']} · 배치 추론 "
              f"{'지원' if rt['batched'] else '미지원(업그레이드 권장)'}")
    if platform.system() == "Windows" and (rt.get("cuda_count") or nvidia_hint(gpus)):
        from minutes.asr.info import cuda_dll_dirs

        dirs = cuda_dll_dirs()
        if dirs:
            print(f"  {OK} CUDA DLL 폴더 {len(dirs)}개 발견(자동 등록됨)")
            for d in dirs:
                print(f"      {d}")
        else:
            print(f"  {NO} CUDA DLL(cublas/cudnn)을 못 찾았습니다 — 전사가 다음 오류로 죽습니다:")
            print("      Library cublas64_12.dll is not found or cannot be loaded")
            print("      해결: uv pip install nvidia-cublas-cu12 nvidia-cudnn-cu12")

    head("Whisper 모델 (받아졌는지 · 캐시됐는지)")
    from minutes.asr.info import dir_size_mb, hf_cache_home

    cache_mb = dir_size_mb(hf_cache_home())
    if cache_mb:
        print(f"  캐시 폴더 {hf_cache_home()}  ({cache_mb:,.0f} MB 사용 중)")
    for repo, short, note, reachable, cached in model_availability():
        mark = OK if reachable else (NO if reachable is False else WARN)
        print(f"  {mark} {short:22s} {'[캐시됨]' if cached else '        '} {note}")
        print(f"      {repo}")

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    head(f"로컬 LLM (Ollama · {host})")
    oll = ollama_info(host)
    if oll["up"]:
        print(f"  {OK} 실행 중 · 설치된 모델: {', '.join(oll['models']) or '(없음)'}")
    else:
        print(f"  {NO} 응답 없음 — {oll['error']}")

    head("현재 .env 설정")
    for k, default in (("ASR_ENGINE", "auto"), ("WHISPER_MODEL", "large-v3"),
                       ("DIARIZER", "auto"), ("OLLAMA_MODEL", "qwen2.5:14b"),
                       ("LLM_TERM_CORRECTION", "1"), ("OLLAMA_TIMEOUT", "1800")):
        print(f"  {k:22s} = {os.environ.get(k, default)}"
              f"{'  (기본값)' if k not in os.environ else ''}")
    hf = bool(os.environ.get("HF_TOKEN"))
    print(f"  {'HF_TOKEN':22s} = {'설정됨' if hf else '없음 → 화자분리 꺼짐'}")
    if hf and os.environ.get("DIARIZER", "auto").lower() not in ("off", "none"):
        print(f"  {WARN} 화자분리(pyannote)가 켜집니다 — CPU에서는 전사가 끝난 뒤")
        print("      녹음 길이의 0.2~0.5배가 더 걸립니다(30분 회의 → +6~15분).")
        print("      속도부터 확인하려면 DIARIZER=off 로 두고 나중에 켜세요.")

    # ------------------------------------------------------------ 권장
    head("권장 설정")
    # CTranslate2 는 스레드가 늘수록 동기화 비용이 커져 8 근처에서 평평해진다.
    # 특히 12세대+ 인텔은 P코어/E코어가 섞여 있어(예: i7-1360P = P4 + E8)
    # 물리 코어를 전부 물리면 느린 E코어에 발이 묶인다.
    physical = cpu["physical"] or max(1, (cpu["logical"] or 2) // 2)
    threads = min(physical, 8)
    if cuda_usable:
        print("  GPU를 쓸 수 있습니다 — 품질을 포기할 이유가 없어요.")
        rec = {"WHISPER_MODEL": "large-v3", "WHISPER_BEAM_SIZE": "5",
               "WHISPER_BATCH_SIZE": "8", "OLLAMA_MODEL": "qwen2.5:14b",
               "LLM_TERM_CORRECTION": "1"}
        print("  예상: 30분 회의 → 전사 2~5분")
    else:
        print("  CPU 전용입니다 — large-v3는 실시간보다 느립니다(30분 회의에 1시간+).")
        if nvidia:
            print(f"  {WARN} NVIDIA GPU({nvidia[0]})는 보이는데 CUDA를 못 씁니다.")
            print("      → CUDA 지원 빌드 설치로 10배 이상 빨라집니다(아래 참고).")
        rec = {"WHISPER_MODEL": "deepdml/faster-whisper-large-v3-turbo-ct2",
               "WHISPER_BEAM_SIZE": "1", "WHISPER_BATCH_SIZE": "8",
               "WHISPER_CPU_THREADS": str(threads),
               "WHISPER_COMPUTE_TYPE": "int8",
               "OLLAMA_MODEL": "qwen2.5:7b", "LLM_TERM_CORRECTION": "0"}
        if physical > threads:
            print(f"  ※ 물리 코어는 {physical}개지만 스레드는 {threads}로 잡습니다"
                  " — 더 늘려도 빨라지지 않고, 느린 코어에 발이 묶일 수 있어요.")
        print("  예상: 30분 회의 → 전사 8~20분 (지금 대비 3~5배 개선)")
        print("  ※ turbo 줄이 ✗ 면 WHISPER_MODEL=medium 을 쓰세요.")
    print("\n  .env 에 넣을 값:")
    for k, v in rec.items():
        print(f"    {k}={v}")

    if nvidia and not cuda_usable:
        head("CUDA 켜기 (해당하면 이게 제일 큰 개선)")
        print("  1) nvidia-smi 로 드라이버 확인")
        print("  2) uv pip install --force-reinstall torch --index-url \\")
        print("       https://download.pytorch.org/whl/cu124")
        print("  3) faster-whisper용 cuDNN/cuBLAS: uv pip install nvidia-cudnn-cu12 nvidia-cublas-cu12")
        print("  4) 다시 이 스크립트를 실행해 'CUDA 장치'가 1 이상인지 확인")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
