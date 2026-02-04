"""
OCR 개선 테스트 스크립트

실행 방법:
1. 서버 실행: uvicorn backend.main:app --reload
2. 브라우저 접속: http://localhost:8000
3. sample/images/image (1).png 업로드
"""

import os
import sys
import json

# 백엔드 모듈 import 경로 추가
sys.path.insert(0, os.path.dirname(__file__))

def test_confusion_correction():
    """ㅁ/ㅇ 혼동 교정 테스트"""
    from backend.ocr import apply_confusion_correction

    baseline_set = {"윤슬", "똥캐", "법도루", "벵커"}

    test_cases = [
        ("문슬", "윤슬"),   # 초성 ㅁ→ㅇ
        ("동캐", "똥캐"),   # 중성 혼동 (실제로는 퍼지 매칭)
        ("범도루", "법도루"), # 종성 ㅁ→ㅂ
        ("뱀커", "벵커"),   # 종성 ㅁ→ㅇ
    ]

    print("=== ㅁ/ㅇ 혼동 교정 테스트 ===")
    for ocr_result, expected in test_cases:
        corrected = apply_confusion_correction(ocr_result, baseline_set)
        status = "✓" if corrected == expected else "✗"
        print(f"{status} {ocr_result} → {corrected} (expected: {expected})")


def test_fuzzy_matching():
    """퍼지 매칭 테스트"""
    from backend.ocr import find_fuzzy_match

    baseline_set = {"윤슬", "똥캐", "법도루", "벵커"}

    test_cases = [
        ("동캐", "똥캐"),   # 1글자 차이
        ("뱀커", "벵커"),   # 1글자 차이
    ]

    print("\n=== 퍼지 매칭 테스트 ===")
    for ocr_result, expected in test_cases:
        matched = find_fuzzy_match(ocr_result, baseline_set)
        status = "✓" if matched == expected else "✗"
        print(f"{status} {ocr_result} → {matched} (expected: {expected})")


def test_integrated_correction():
    """통합 교정 테스트"""
    from backend.ocr import correct_ocr_errors

    baseline_members = [
        "윤슬/마법사/150",
        "똥캐/부마스터",
        "법도루/전사/180",
        "벵커/도적/170"
    ]

    ocr_names = ["문슬", "동캐", "범도루", "뱀커"]

    print("\n=== 통합 교정 테스트 ===")
    corrected = correct_ocr_errors(ocr_names, baseline_members)

    expected = ["윤슬", "똥캐", "법도루", "벵커"]
    for i, (original, result, expect) in enumerate(zip(ocr_names, corrected, expected)):
        status = "✓" if result == expect else "✗"
        print(f"{status} {original} → {result} (expected: {expect})")


def load_baseline():
    """베이스라인 데이터 로드"""
    baseline_path = os.path.join(os.path.dirname(__file__), 'data', 'baseline.json')
    if os.path.exists(baseline_path):
        with open(baseline_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def test_with_baseline():
    """실제 베이스라인 데이터로 테스트"""
    from backend.ocr import correct_ocr_errors

    baseline = load_baseline()
    if not baseline:
        print("\n베이스라인 데이터가 없습니다.")
        return

    baseline_members = baseline.get('members', [])
    print(f"\n베이스라인: {baseline.get('guildName')} ({len(baseline_members)}명)")

    # 샘플 OCR 오류 데이터
    sample_errors = ["문슬", "동캐", "범도루", "뱀커"]

    print("\n=== 실제 베이스라인 교정 테스트 ===")
    corrected = correct_ocr_errors(sample_errors, baseline_members)

    for original, result in zip(sample_errors, corrected):
        changed = "→" + result if original != result else ""
        print(f"  {original}{changed}")


if __name__ == "__main__":
    try:
        test_confusion_correction()
        test_fuzzy_matching()
        test_integrated_correction()
        test_with_baseline()

        print("\n" + "="*50)
        print("✓ 모든 테스트 완료")
        print("="*50)

    except ImportError as e:
        print(f"\n오류: {e}")
        print("\n실행 방법:")
        print("1. pip install -r requirements.txt")
        print("2. python test_ocr_improvements.py")
