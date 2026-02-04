"""
EasyOCR을 사용한 이미지 텍스트 추출
"""
import easyocr
from PIL import Image
import io
import re
from typing import List, Optional
import numpy as np
import cv2

# 한글 + 영어 OCR 리더 (최초 1회 로딩에 시간 걸림)
reader = None


def get_reader():
    global reader
    if reader is None:
        print("OCR 모델 로딩 중...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)  # GPU 없으면 False
        print("OCR 모델 로딩 완료!")
    return reader


def preprocess_image(image_np: np.ndarray) -> np.ndarray:
    """
    이미지 전처리: CLAHE + 적응형 이진화 + 노이즈 제거
    OCR 인식률 향상 (15-30% 개선 예상)
    """
    # 그레이스케일 변환
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY) if len(image_np.shape) == 3 else image_np

    # CLAHE 대비 향상
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 적응형 이진화
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=11, C=2
    )

    # 노이즈 제거 (Morphological Opening)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # RGB로 복원 (EasyOCR 입력용)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)


def extract_names_from_image(
    image_bytes: bytes,
    use_preprocessing: bool = False,
    confidence_threshold: float = 0.3
) -> List[str]:
    """
    이미지에서 이름(텍스트) 추출
    - 전처리 옵션 추가 (CLAHE + 이진화)
    - 신뢰도 임계값 조정 (0.3 → 0.6)
    - beamsearch decoder 사용
    """
    reader = get_reader()

    # 이미지 로드 → numpy array로 변환
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image)

    # 전처리 적용 (옵션)
    if use_preprocessing:
        image_np = preprocess_image(image_np)

    # OCR 실행 (최적화된 파라미터)
    results = reader.readtext(
        image_np,
        decoder='greedy',  # beamsearch는 너무 엄격함
        batch_size=1
    )

    # 텍스트만 추출
    texts = []
    for (bbox, text, confidence) in results:
        # 신뢰도 필터링
        if confidence > confidence_threshold:
            # 공백 정리
            cleaned = text.strip()
            if cleaned:
                texts.append(cleaned)

    return texts


def clean_names(texts: List[str]) -> List[str]:
    """
    OCR 결과에서 이름만 정리
    - 한글 이름 추출
    - 특수문자/숫자/영어 제거
    """
    names = []
    for text in texts:
        # 영어/숫자/특수문자가 섞인 텍스트는 스킵
        if re.search(r'[a-zA-Z0-9]', text):
            # 한글만 추출 시도
            korean_only = re.sub(r'[^가-힣]', '', text)
            if len(korean_only) >= 2:
                names.append(korean_only)
            continue

        # 순수 한글 텍스트에서 2글자 이상 추출
        korean_match = re.findall(r'[가-힣]{2,}', text)
        names.extend(korean_match)

    # 중복 제거
    return list(dict.fromkeys(names))


def apply_confusion_correction(name: str, baseline_set: set) -> str:
    """
    ㅁ/ㅇ 혼동 패턴 보정 (유니코드 자모 분해)
    - 초성: ㅁ(6) ↔ ㅇ(11)
    - 종성: ㅁ(16) ↔ ㅂ(17), ㅁ(16) ↔ ㅇ(21)

    예시:
    - 문슬 → 윤슬 (초성 ㅁ→ㅇ)
    - 범도루 → 법도루 (종성 ㅁ→ㅂ)
    - 뱀커 → 뱅커 (종성 ㅁ→ㅇ)
    """
    for i, char in enumerate(name):
        if not ('가' <= char <= '힣'):
            continue

        # 유니코드 분해: 초성/중성/종성
        code = ord(char) - 0xAC00
        cho = code // 588          # 초성 (0-18)
        jung = (code % 588) // 28  # 중성 (0-20)
        jong = code % 28           # 종성 (0-27)

        # 초성 ㅁ(6) ↔ ㅇ(11) 혼동 교정
        for old, new in [(6, 11), (11, 6)]:
            if cho == old:
                new_code = new * 588 + jung * 28 + jong
                candidate = name[:i] + chr(new_code + 0xAC00) + name[i+1:]
                if candidate in baseline_set:
                    return candidate

        # 종성 ㅁ(16) ↔ ㅂ(17), ㅁ(16) ↔ ㅇ(21) 혼동 교정
        for old, new in [(16, 17), (17, 16), (16, 21), (21, 16)]:
            if jong == old:
                new_code = cho * 588 + jung * 28 + new
                candidate = name[:i] + chr(new_code + 0xAC00) + name[i+1:]
                if baseline_set and candidate in baseline_set:
                    return candidate

    return name


def find_fuzzy_match(name: str, baseline_set: set, max_distance: int = 1) -> Optional[str]:
    """
    편집거리 기반 유사 이름 찾기
    - 길이가 같은 것만 비교
    - 유사도 임계값: 0.5 (2글자 중 1글자 일치)
    """
    from difflib import SequenceMatcher

    best_match = None
    best_ratio = 0.0

    for baseline_name in baseline_set:
        # 길이가 같아야 함
        if len(name) != len(baseline_name):
            continue

        # 유사도 계산
        ratio = SequenceMatcher(None, name, baseline_name).ratio()

        # 임계값: 0.5 (절반 이상 일치)
        # 2글자: 1글자 일치 = 0.5
        # 3글자: 2글자 일치 = 0.67
        # 4글자: 3글자 일치 = 0.75
        threshold = 0.5

        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = baseline_name

    return best_match


def correct_ocr_errors(names: List[str], baseline_members: Optional[List[str]] = None) -> List[str]:
    """
    OCR 오류 보정: 문자 혼동 + 퍼지 매칭

    처리 순서:
    1. 완전 일치 → 보정 불필요
    2. ㅁ/ㅇ 혼동 보정
    3. 퍼지 매칭 (편집거리)
    """
    if not baseline_members:
        return names

    # 베이스라인에서 닉네임만 추출
    baseline_nicknames = set()
    for member in baseline_members:
        nickname = member.split('/')[0].strip()
        baseline_nicknames.add(nickname)

    corrected = []
    for name in names:
        # 1. 완전 일치 → 보정 불필요
        if name in baseline_nicknames:
            corrected.append(name)
            continue

        # 2. ㅁ/ㅇ 혼동 보정
        corrected_name = apply_confusion_correction(name, baseline_nicknames)

        # 3. 퍼지 매칭
        if corrected_name not in baseline_nicknames:
            fuzzy_match = find_fuzzy_match(corrected_name, baseline_nicknames)
            if fuzzy_match:
                corrected_name = fuzzy_match

        corrected.append(corrected_name)

    return corrected


def extract_and_clean_names(
    image_bytes: bytes,
    baseline_members: Optional[List[str]] = None
) -> List[str]:
    """
    이미지에서 이름 추출 + 정리 + 보정

    개선 사항:
    1. 전처리 (CLAHE + 이진화)
    2. 최적화된 OCR 파라미터 (beamsearch, 신뢰도 0.6)
    3. 후처리 교정 (ㅁ/ㅇ 혼동, 퍼지 매칭)
    """
    # 1. OCR 실행 (전처리 OFF, 신뢰도 낮춤)
    raw_texts = extract_names_from_image(
        image_bytes,
        use_preprocessing=False,
        confidence_threshold=0.3
    )

    # 2. 한글 이름만 추출
    cleaned_names = clean_names(raw_texts)

    # 3. 오류 보정 (baseline 있을 때만)
    if baseline_members:
        cleaned_names = correct_ocr_errors(cleaned_names, baseline_members)

    # 4. 중복 제거
    return list(dict.fromkeys(cleaned_names))
