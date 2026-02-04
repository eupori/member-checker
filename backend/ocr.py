"""
EasyOCR을 사용한 이미지 텍스트 추출
"""
import easyocr
from PIL import Image
import io
import re
from typing import List

# 한글 + 영어 OCR 리더 (최초 1회 로딩에 시간 걸림)
reader = None


def get_reader():
    global reader
    if reader is None:
        print("OCR 모델 로딩 중...")
        reader = easyocr.Reader(['ko', 'en'], gpu=False)  # GPU 없으면 False
        print("OCR 모델 로딩 완료!")
    return reader


def extract_names_from_image(image_bytes: bytes) -> List[str]:
    """
    이미지에서 이름(텍스트) 추출
    """
    import numpy as np
    
    reader = get_reader()
    
    # 이미지 로드 → numpy array로 변환
    image = Image.open(io.BytesIO(image_bytes))
    image_np = np.array(image)
    
    # OCR 실행
    results = reader.readtext(image_np)
    
    # 텍스트만 추출
    texts = []
    for (bbox, text, confidence) in results:
        # 신뢰도 0.3 이상만
        if confidence > 0.3:
            # 공백 정리
            cleaned = text.strip()
            if cleaned:
                texts.append(cleaned)
    
    return texts


def clean_names(texts: List[str]) -> List[str]:
    """
    OCR 결과에서 이름만 정리
    - 한글 이름 추출
    - 특수문자/숫자 제거
    """
    names = []
    for text in texts:
        # 한글만 추출 (2글자 이상)
        korean_match = re.findall(r'[가-힣]{2,}', text)
        names.extend(korean_match)
    
    # 중복 제거
    return list(dict.fromkeys(names))


def extract_and_clean_names(image_bytes: bytes) -> List[str]:
    """
    이미지에서 이름 추출 + 정리
    """
    raw_texts = extract_names_from_image(image_bytes)
    cleaned_names = clean_names(raw_texts)
    return cleaned_names
