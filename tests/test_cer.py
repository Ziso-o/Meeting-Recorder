"""CER 측정 스크립트 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import cer as cer_mod  # noqa: E402


def test_cer_identical_is_zero():
    assert cer_mod.cer("회의를 시작합니다", "회의를 시작합니다") == 0.0


def test_cer_one_char_substitution():
    # 공백 제거 후 정답 "회의시작"(4자) 중 1자 오류 → 0.25
    score = cer_mod.cer("회의 시작", "회이 시작")
    assert abs(score - 0.25) < 1e-9


def test_cer_empty_reference():
    assert cer_mod.cer("", "") == 0.0
    assert cer_mod.cer("", "여분") == 1.0


def test_normalize_removes_punctuation_and_spaces():
    assert cer_mod.normalize("안녕, 하세요!") == "안녕하세요"
