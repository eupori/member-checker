"""
OCR 기능 토글 스크립트

사용법:
python toggle_ocr_features.py --preprocessing off  # 전처리 끄기
python toggle_ocr_features.py --preprocessing on   # 전처리 켜기
python toggle_ocr_features.py --decoder greedy     # 기존 방식으로
python toggle_ocr_features.py --decoder beamsearch # 새로운 방식 (더 정확)
python toggle_ocr_features.py --rollback           # 전체 롤백
"""

import sys
import re

def toggle_preprocessing(enable):
    """전처리 on/off"""
    ocr_file = 'backend/ocr.py'

    try:
        with open(ocr_file, 'r', encoding='utf-8') as f:
            content = f.read()

        value = "True" if enable else "False"
        pattern = r'use_preprocessing=(?:True|False)'
        new_content = re.sub(pattern, f'use_preprocessing={value}', content)

        with open(ocr_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        status = "켬" if enable else "끔"
        print(f"✓ 전처리를 {status}으로 설정했습니다.")
        print(f"  파일: {ocr_file}")

        return True

    except Exception as e:
        print(f"✗ 오류: {e}")
        return False


def change_decoder(decoder_type):
    """decoder 변경"""
    ocr_file = 'backend/ocr.py'

    if decoder_type not in ['greedy', 'beamsearch']:
        print("✗ decoder는 'greedy' 또는 'beamsearch'만 가능합니다.")
        return False

    try:
        with open(ocr_file, 'r', encoding='utf-8') as f:
            content = f.read()

        pattern = r"decoder='(?:greedy|beamsearch)'"
        new_content = re.sub(pattern, f"decoder='{decoder_type}'", content)

        with open(ocr_file, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"✓ Decoder를 '{decoder_type}'로 변경했습니다.")
        print(f"  파일: {ocr_file}")

        return True

    except Exception as e:
        print(f"✗ 오류: {e}")
        return False


def rollback():
    """git으로 롤백"""
    import subprocess

    print("이전 버전으로 롤백하시겠습니까? (y/n): ", end="")
    confirm = input().strip().lower()

    if confirm != 'y':
        print("취소되었습니다.")
        return False

    try:
        result = subprocess.run(['git', 'revert', '--no-commit', 'HEAD'], capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ 롤백 완료 (아직 커밋되지 않음)")
            print("  확인 후 커밋: git commit -m 'Revert OCR changes'")
            print("  취소: git reset --hard HEAD")
        else:
            print(f"✗ 롤백 실패: {result.stderr}")

        return result.returncode == 0

    except Exception as e:
        print(f"✗ 오류: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]

    if arg == '--rollback':
        rollback()
    elif arg == '--preprocessing' and len(sys.argv) == 3:
        enable = sys.argv[2].lower() == 'on'
        if toggle_preprocessing(enable):
            print("\n서버를 재시작하세요:")
            print("  uvicorn backend.main:app --reload")
    elif arg == '--decoder' and len(sys.argv) == 3:
        if change_decoder(sys.argv[2]):
            print("\n서버를 재시작하세요:")
            print("  uvicorn backend.main:app --reload")
    else:
        print(__doc__)
        sys.exit(1)
