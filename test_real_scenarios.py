"""
실제 OCR 시나리오 테스트

실제 baseline 데이터를 사용한 종합 테스트
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from backend.ocr import correct_ocr_errors


def load_baseline():
    """베이스라인 데이터 로드"""
    baseline_path = os.path.join(os.path.dirname(__file__), 'data', 'baseline.json')
    if os.path.exists(baseline_path):
        with open(baseline_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def test_real_ocr_scenarios():
    """실제 OCR 오류 시나리오 테스트"""
    baseline = load_baseline()
    if not baseline:
        print("베이스라인 데이터가 없습니다.")
        return

    baseline_members = baseline.get('members', [])
    nicknames = [m.split('/')[0].strip() for m in baseline_members]

    print(f"베이스라인: {baseline.get('guildName')} ({len(nicknames)}명)")
    print("=" * 60)

    # 실제 OCR 오류 패턴 시뮬레이션
    test_scenarios = [
        {
            "category": "ㅁ/ㅇ 혼동 (초성/종성)",
            "cases": [
                ("문슬", "윤슬"),  # 초성 변화
                ("뱀커", "벵커"),  # 종성 변화
            ]
        },
        {
            "category": "유사 문자 혼동",
            "cases": [
                ("동캐", "똥캐"),  # ㅇ/ㅇㅇ 혼동
                ("범도루", "하도루"),  # 범/하 혼동
            ]
        },
        {
            "category": "정상 인식 (변경 없음)",
            "cases": [
                ("윤슬", "윤슬"),
                ("똥캐", "똥캐"),
                ("벵커", "벵커"),
            ]
        },
    ]

    total_tests = 0
    passed_tests = 0

    for scenario in test_scenarios:
        print(f"\n📋 {scenario['category']}")
        print("-" * 60)

        ocr_inputs = [case[0] for case in scenario['cases']]
        expected_outputs = [case[1] for case in scenario['cases']]

        # 교정 실행
        corrected = correct_ocr_errors(ocr_inputs, baseline_members)

        # 결과 검증
        for i, (ocr, expected, result) in enumerate(zip(ocr_inputs, expected_outputs, corrected)):
            total_tests += 1

            # 예상 결과가 baseline에 있는지 확인
            expected_exists = expected in nicknames
            result_correct = result == expected

            if result_correct:
                passed_tests += 1
                status = "✓"
                color = "\033[92m"  # Green
            else:
                status = "✗"
                color = "\033[91m"  # Red

            reset = "\033[0m"

            exists_marker = "✓" if expected_exists else "✗"

            print(f"  {color}{status}{reset} {ocr} → {result} (expected: {expected}) [baseline: {exists_marker}]")

    # 최종 결과
    print("\n" + "=" * 60)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f"테스트 결과: {passed_tests}/{total_tests} 통과 ({success_rate:.1f}%)")
    print("=" * 60)

    # baseline에 있는 샘플 이름 표시
    print(f"\n베이스라인 샘플 (처음 10명):")
    for i, nick in enumerate(nicknames[:10], 1):
        print(f"  {i}. {nick}")

    return passed_tests == total_tests


if __name__ == "__main__":
    try:
        success = test_real_ocr_scenarios()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
