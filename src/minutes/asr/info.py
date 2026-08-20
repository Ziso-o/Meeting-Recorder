"""전사 런타임 정보 — 어떤 모델이 어디서(CPU/GPU) 도는지, 모델을 받아야 하는지.

대시보드가 "전사하는 중"만 보여주면 **3GB 모델을 받는 중인지 진짜 전사 중인지**
구분할 수 없다. 여기서 그 판단에 필요한 사실만 모아 준다.

무거운 의존성(torch/ctranslate2/faster_whisper)은 **지연 임포트**하고, 없으면
조용히 기본값으로 떨어진다 — 이 모듈 때문에 서버가 죽으면 안 된다.
"""

from __future__ import annotations

import os
from pathlib import Path

#: faster-whisper 모델의 대략적인 다운로드 크기(MB). 진행률 분모로만 쓴다.
MODEL_SIZE_MB = {
    "tiny": 75, "base": 145, "small": 480, "medium": 1530,
    "large": 3090, "large-v1": 3090, "large-v2": 3090, "large-v3": 3090,
    "distil-large-v3": 1510, "turbo": 1620, "large-v3-turbo": 1620,
}

#: (디바이스, 크기군) → 오디오 길이 대비 처리 시간 배수의 (최소, 최대).
#: 실측 편차가 커서 범위로만 준다 — 정확한 예측이 목적이 아니라
#: "몇 분인지 몇 시간인지" 감을 주는 게 목적이다.
_SPEED_RANGE = {
    ("cuda", "tiny"): (0.005, 0.02), ("cpu", "tiny"): (0.03, 0.10),
    ("cuda", "base"): (0.01, 0.03), ("cpu", "base"): (0.05, 0.18),
    ("cuda", "small"): (0.02, 0.06), ("cpu", "small"): (0.12, 0.40),
    ("cuda", "medium"): (0.03, 0.10), ("cpu", "medium"): (0.30, 1.00),
    ("cuda", "large"): (0.05, 0.15), ("cpu", "large"): (0.80, 2.50),
}


def size_bucket(model_size: str) -> str:
    """모델 이름을 속도 추정용 크기군으로 묶는다."""
    m = model_size.lower()
    for bucket in ("tiny", "base", "small", "medium"):
        if bucket in m:
            return bucket
    return "large"  # large-v3 · turbo · distil 등은 large 군으로


def _cuda_via_ctranslate2() -> bool | None:
    """CTranslate2 기준 CUDA 가용 여부. 판단 불가면 None."""
    try:
        import ctranslate2  # 지연 임포트

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001  미설치·드라이버 문제 등 — 다음 수단으로
        return None


def _cuda_via_torch() -> bool | None:
    try:
        import torch  # 지연 임포트

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return None


def asr_device() -> str:
    """faster-whisper 가 실제로 쓸 디바이스("cuda" | "cpu").

    faster-whisper 는 torch 가 아니라 CTranslate2 로 도니 그쪽을 먼저 본다.
    둘 다 판단 못 하면 보수적으로 "cpu"(느린 쪽)로 본다 — 예상 시간을 낙관하지 않기 위해.
    """
    for probe in (_cuda_via_ctranslate2, _cuda_via_torch):
        got = probe()
        if got is not None:
            return "cuda" if got else "cpu"
    return "cpu"


def whisper_repo_id(model_size: str) -> str:
    """모델 이름 → HuggingFace 저장소 id.

    경로(/)가 들어 있으면 사용자가 직접 지정한 repo 로 보고 그대로 쓴다.
    """
    if "/" in model_size:
        return model_size
    return f"Systran/faster-whisper-{model_size}"


def hf_cache_home() -> Path:
    """huggingface_hub 이 실제로 쓰는 캐시 폴더(환경변수 우선순위 반영)."""
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def model_cache_path(repo_id: str) -> Path:
    """해당 모델이 저장되는 캐시 폴더(존재하지 않을 수 있음)."""
    return hf_cache_home() / ("models--" + repo_id.replace("/", "--"))


def dir_size_mb(path: Path) -> float:
    """폴더 크기(MB). 없으면 0 — 다운로드 진행률 표시에만 쓴다."""
    if not path.exists():
        return 0.0
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:  # 다운로드 중 사라지는 임시파일
            continue
    return total / (1024 * 1024)


def is_model_cached(repo_id: str, model_size: str = "") -> bool:
    """모델을 이미 받아 뒀는지(=이번 실행에서 다운로드가 없을지).

    스냅샷 폴더에 실제 가중치(model.bin 등)가 있고 `.incomplete` 조각이 없어야
    받아 둔 것으로 본다. 크기 비교는 하지 않는다(파일 구성이 모델마다 다름).
    """
    root = model_cache_path(repo_id)
    snapshots = root / "snapshots"
    if not snapshots.is_dir():
        return False
    if any(root.rglob("*.incomplete")):
        return False
    return any(p.is_file() and p.stat().st_size > 1_000_000 for p in snapshots.rglob("*"))


def expected_model_mb(model_size: str) -> int:
    return MODEL_SIZE_MB.get(model_size.lower(), MODEL_SIZE_MB["large-v3"])


def estimate_range_sec(duration_sec: float, model_size: str, device: str) -> tuple[float, float] | None:
    """오디오 길이 → 전사 예상 시간(최소, 최대) 초. 추정 불가면 None."""
    if duration_sec <= 0:
        return None
    lo, hi = _SPEED_RANGE.get((device, size_bucket(model_size)), (0.0, 0.0))
    if not hi:
        return None
    return duration_sec * lo, duration_sec * hi


def describe_engine(engine) -> str:
    """대시보드에 그대로 띄울 한 줄: "faster-whisper large-v3 · CPU"."""
    name = getattr(engine, "name", "?")
    if name != "faster-whisper":
        return name
    return f"{name} {getattr(engine, 'model_size', '?')} · {asr_device().upper()}"
