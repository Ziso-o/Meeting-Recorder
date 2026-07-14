"""CER (Character Error Rate) 측정 — 전사 품질 평가.

CER = (치환 + 삭제 + 삽입) / 정답 문자 수  (문자 단위 Levenshtein).
한국어 전사 평가에는 WER보다 CER이 적합하다.

사용법:
    python scripts/cer.py --ref reference.txt --hyp hypothesis.txt
    python scripts/cer.py --ref "정답 문장" --hyp "가설 문장" --text
    # 전사 JSON에서 텍스트만 뽑아 비교:
    python scripts/cer.py --ref ref.txt --hyp out.transcript.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _levenshtein(ref: str, hyp: str) -> int:
    """문자 단위 편집 거리."""
    m, n = len(ref), len(hyp)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]


def normalize(text: str, keep_spaces: bool = False) -> str:
    """공백/문장부호 정규화. 기본은 공백 제거(한국어 CER 관례)."""
    text = text.strip()
    text = re.sub(r"[^\w가-힣\s]", "", text)  # 문장부호 제거
    if keep_spaces:
        return re.sub(r"\s+", " ", text)
    return re.sub(r"\s+", "", text)


def cer(reference: str, hypothesis: str, keep_spaces: bool = False) -> float:
    ref = normalize(reference, keep_spaces)
    hyp = normalize(hypothesis, keep_spaces)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def _read(arg: str, as_text: bool) -> str:
    """파일 경로면 파일을, --text면 문자열 그대로. .json이면 세그먼트 text 결합."""
    if as_text:
        return arg
    p = Path(arg)
    if not p.exists():
        return arg  # 파일이 없으면 리터럴로 취급
    if p.suffix == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        segs = data.get("segments", data) if isinstance(data, dict) else data
        return " ".join(s.get("text", "") for s in segs)
    return p.read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cer", description="CER 측정")
    ap.add_argument("--ref", required=True, help="정답(파일 경로 또는 문자열)")
    ap.add_argument("--hyp", required=True, help="가설/전사 결과(파일/json/문자열)")
    ap.add_argument("--text", action="store_true", help="--ref/--hyp를 파일이 아닌 문자열로 처리")
    ap.add_argument("--keep-spaces", action="store_true", help="공백을 유지하고 비교")
    args = ap.parse_args(argv)

    ref = _read(args.ref, args.text)
    hyp = _read(args.hyp, args.text)
    score = cer(ref, hyp, keep_spaces=args.keep_spaces)
    print(f"CER: {score:.4f} ({score * 100:.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
