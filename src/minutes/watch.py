"""폴더 감시 자동 처리기 (반응형 watch) — n8n 없이 로컬에서 무인 운영.

data/incoming 에 오디오가 들어오면 → 파이프라인(전사+화자분리+회의록) 자동 실행 →
회의록을 data/out 에 저장하고, 처리한 오디오는 data/done 으로 이동. 실패 시 data/failed.

추가 의존성 없이 폴링 루프로 동작한다. **파일 크기가 안정된 뒤**(연속 스캔에서
크기가 안 변할 때) 처리하여 업로드 중 미완성 파일을 건드리지 않는다.

사용법:
    python -m minutes.watch --profile secure
    python -m minutes.watch --incoming data/incoming --out data/out --interval 5
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from . import pipeline
from .audio_formats import AUDIO_EXTS
from .config import load_dotenv


def find_audio(incoming: Path) -> list[Path]:
    return sorted(
        p for p in incoming.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    )


def _unique_dest(dest_dir: Path, name: str) -> Path:
    """대상 폴더에 동일 이름이 있으면 접미사를 붙여 충돌을 피한다."""
    dest = dest_dir / name
    if not dest.exists():
        return dest
    stem, suf = Path(name).stem, Path(name).suffix
    i = 1
    while (dest_dir / f"{stem}_{i}{suf}").exists():
        i += 1
    return dest_dir / f"{stem}_{i}{suf}"


def process_file(
    audio: Path,
    out_dir: Path,
    done_dir: Path,
    failed_dir: Path,
    profile: str,
    glossary: str,
) -> bool:
    """오디오 1건 처리 → 회의록 out_dir 저장, 성공 시 done_dir/ 실패 시 failed_dir 로 이동."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_stem = out_dir / audio.stem
    try:
        rc = pipeline.main(
            [
                "--audio", str(audio),
                "--profile", profile,
                "--glossary", glossary,
                "--out", str(out_stem),
            ]
        )
        if rc != 0:
            raise RuntimeError(f"pipeline 반환코드 {rc}")
    except Exception as e:  # 복구 가능 오류: 로그 + failed 이동(무한 재시도 방지)
        print(f"✗ 처리 실패: {audio.name} — {e}", file=sys.stderr)
        failed_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(audio), str(_unique_dest(failed_dir, audio.name)))
        return False

    done_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(audio), str(_unique_dest(done_dir, audio.name)))
    print(f"✓ 완료: {audio.name} → {out_stem}.minutes.md")
    return True


def run_once(
    incoming: Path,
    out_dir: Path,
    done_dir: Path,
    failed_dir: Path,
    profile: str,
    glossary: str,
    size_cache: dict[str, int],
    require_stable: bool = True,
) -> list[Path]:
    """한 번 스캔한다.

    require_stable=True(연속 감시): 크기가 직전 스캔과 동일한(안정된) 파일만 처리
      → 업로드 중 미완성 파일을 건드리지 않음.
    require_stable=False(--once/크론): 캐시가 프로세스마다 초기화되므로 안정성 게이트를
      건너뛰고 발견된 파일을 즉시 처리.

    반환: 이번에 처리 시도한 파일 목록.
    """
    processed: list[Path] = []
    for audio in find_audio(incoming):
        try:
            size = audio.stat().st_size
        except OSError:
            continue
        if require_stable:
            key = str(audio)
            if size_cache.get(key) != size:
                # 크기가 바뀌었거나 처음 본 파일 → 다음 스캔에서 안정되면 처리.
                size_cache[key] = size
                continue
            size_cache.pop(key, None)
        process_file(audio, out_dir, done_dir, failed_dir, profile, glossary)
        processed.append(audio)
    return processed


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(prog="minutes.watch", description="폴더 감시 자동 회의록")
    ap.add_argument("--incoming", default="data/incoming", help="감시 폴더")
    ap.add_argument("--out", default="data/out", help="회의록 출력 폴더")
    ap.add_argument("--done", default="data/done", help="처리 완료 오디오 보관")
    ap.add_argument("--failed", default="data/failed", help="처리 실패 오디오 보관")
    ap.add_argument("--profile", "-p", choices=("internal", "secure"), default="secure")
    ap.add_argument("--glossary", "-g", default="glossary.yaml")
    ap.add_argument("--interval", type=float, default=5.0, help="폴링 간격(초)")
    ap.add_argument("--once", action="store_true", help="한 번만 스캔하고 종료(테스트/크론)")
    args = ap.parse_args(argv)

    incoming = Path(args.incoming)
    out_dir = Path(args.out)
    incoming.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    size_cache: dict[str, int] = {}
    common = dict(
        incoming=incoming,
        out_dir=out_dir,
        done_dir=Path(args.done),
        failed_dir=Path(args.failed),
        profile=args.profile,
        glossary=args.glossary,
        size_cache=size_cache,
    )

    if args.once:
        run_once(**common, require_stable=False)
        return 0

    print(f"👀 감시 시작: {incoming} → {out_dir} [profile={args.profile}] (Ctrl+C 종료)")
    try:
        while True:
            run_once(**common)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n감시를 종료합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
