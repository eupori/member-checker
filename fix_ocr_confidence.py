"""
OCR 신뢰도 조정 스크립트

사용법:
python fix_ocr_confidence.py 0.3  # 신뢰도를 0.3으로 낮춤 (더 많이 인식)
python fix_ocr_confidence.py 0.4  # 신뢰도를 0.4로 낮춤
python fix_ocr_confidence.py 0.6  # 신뢰도를 0.6으로 높임 (더 정확하게)
"""

import sys
import re

def update_confidence_threshold(new_value):
    """OCR 신뢰도 임계값 변경"""
    ocr_file = 'backend/ocr.py'

    try:
        with open(ocr_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # confidence_threshold=0.6 찾아서 변경
        pattern = r'confidence_threshold=[\d\.]+'
        new_content = re.sub(pattern, f'confidence_threshold={new_value}', content)

        with open(ocr_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ OCR 신뢰도를 {new_value}로 변경했습니다.")
        print(f"  파일: {ocr_file}")
        print(f"\n서버를 재시작하세요:")
        print(f"  uvicorn backend.main:app --reload")

        return True

    except Exception as e:
        print(f"✗ 오류: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python fix_ocr_confidence.py [신뢰도]")
        print("예시:")
        print("  python fix_ocr_confidence.py 0.3  # 더 많이 인식 (정확도 낮음)")
        print("  python fix_ocr_confidence.py 0.4  # 중간")
        print("  python fix_ocr_confidence.py 0.6  # 더 정확하게 (인식 적음)")
        sys.exit(1)

    try:
        confidence = float(sys.argv[1])
        if not (0.0 <= confidence <= 1.0):
            print("✗ 신뢰도는 0.0~1.0 사이여야 합니다.")
            sys.exit(1)

        update_confidence_threshold(confidence)
    except ValueError:
        print("✗ 올바른 숫자를 입력하세요 (예: 0.3, 0.4, 0.6)")
        sys.exit(1)
