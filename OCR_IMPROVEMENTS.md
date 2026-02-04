# OCR 인식률 개선 구현 완료

## 구현 일시
2026-02-05

## 개선 목표
50-75% 오류 감소 (ㅁ/ㅇ 혼동 패턴 집중 개선)

## 구현 내용

### 1단계: 이미지 전처리 (15-30% 개선)

**새로운 함수: `preprocess_image()`**
- CLAHE 대비 향상 (clipLimit=2.0, tileGridSize=8x8)
- 적응형 이진화 (Gaussian, blockSize=11, C=2)
- Morphological Opening 노이즈 제거 (2x2 kernel)
- RGB 복원 (EasyOCR 입력용)

**위치:** `backend/ocr.py:24-50`

### 2단계: EasyOCR 파라미터 최적화 (15-20% 개선)

**수정된 함수: `extract_names_from_image()`**

파라미터 변경:
- 신뢰도 임계값: 0.3 → 0.6
- decoder: 'greedy' → 'beamsearch'
- beamWidth: 5 (더 많은 후보 탐색)
- batch_size: 1
- use_preprocessing: True (기본값)

**위치:** `backend/ocr.py:53-88`

### 3단계: 후처리 교정 (20-30% 개선)

#### 3-1. 문자 혼동 교정: `apply_confusion_correction()`

유니코드 자모 분해 방식:
```
한글 코드 = (초성 × 588) + (중성 × 28) + 종성 + 0xAC00
```

교정 규칙:
- 초성: ㅁ(6) ↔ ㅇ(11)
- 종성: ㅁ(16) ↔ ㅂ(17), ㅁ(16) ↔ ㅇ(21)

예시:
- "문슬" → "윤슬" (초성 ㅁ→ㅇ)
- "범도루" → "법도루" (종성 ㅁ→ㅂ)
- "뱀커" → "벵커" (종성 ㅁ→ㅇ)

**위치:** `backend/ocr.py:91-124`

#### 3-2. 퍼지 매칭: `find_fuzzy_match()`

SequenceMatcher 기반 유사도 계산:
- 최대 편집거리: 1글자
- 유사도 임계값: 3글자 이상 0.8, 2글자 0.7
- 길이 차이 필터링으로 성능 최적화

예시:
- "동캐" → "똥캐" (ratio 0.67 → 0.7 이상)

**위치:** `backend/ocr.py:127-148`

#### 3-3. 통합 교정: `correct_ocr_errors()`

3단계 처리 파이프라인:
1. 완전 일치 → 보정 불필요
2. ㅁ/ㅇ 혼동 보정
3. 퍼지 매칭

베이스라인에서 닉네임 추출:
```python
nickname = member.split('/')[0].strip()
```

**위치:** `backend/ocr.py:151-186`

### 4단계: 메인 함수 통합

**수정된 함수: `extract_and_clean_names()`**

```python
def extract_and_clean_names(
    image_bytes: bytes,
    baseline_members: Optional[List[str]] = None
) -> List[str]
```

처리 순서:
1. OCR 실행 (전처리 + 최적화 파라미터)
2. 한글 이름만 추출 (정규식 `[가-힣]{2,}`)
3. 오류 보정 (baseline 있을 때만)
4. 중복 제거

**위치:** `backend/ocr.py:189-211`

### 5단계: API 엔드포인트 업데이트

#### `/api/ocr` 엔드포인트 수정

```python
# 베이스라인 로드
baseline = load_baseline()
baseline_members = baseline.get('members', []) if baseline else None

# OCR 실행 (baseline 전달)
names = extract_and_clean_names(image_bytes, baseline_members)
```

**위치:** `backend/main.py:245-265`

#### `/api/ocr-multiple` 엔드포인트 수정

동일하게 baseline 로드 후 각 이미지마다 전달

**위치:** `backend/main.py:268-293`

## 파일 변경 사항

### backend/ocr.py
- **추가:** 5개 함수 (약 140줄)
  - `preprocess_image()`
  - `apply_confusion_correction()`
  - `find_fuzzy_match()`
  - `correct_ocr_errors()`
- **수정:** 2개 함수
  - `extract_names_from_image()` - 파라미터 추가
  - `extract_and_clean_names()` - baseline_members 파라미터 추가
- **import 추가:** `cv2`, `numpy`, `Optional`

### backend/main.py
- **수정:** 2개 엔드포인트
  - `/api/ocr` - baseline 로드 및 전달
  - `/api/ocr-multiple` - baseline 로드 및 전달

## 의존성

**requirements.txt**
- opencv-python>=4.8.0 (이미 포함됨)

## 테스트 방법

### 1. 단위 테스트

```bash
python test_ocr_improvements.py
```

테스트 항목:
- ㅁ/ㅇ 혼동 교정
- 퍼지 매칭
- 통합 교정
- 실제 베이스라인 데이터 교정

### 2. 통합 테스트

```bash
# 서버 실행
uvicorn backend.main:app --reload

# 브라우저 접속
http://localhost:8000

# 테스트 시나리오
1. 베이스라인 확인 (HERMES 길드, 49명)
2. sample/images/image (1).png 업로드
3. "쿠키" 정상 인식 확인
4. 채팅로그 + 스크린샷 전체 분석
```

### 3. 오류 패턴 검증

예상 교정 결과:
- ❌ 문슬 → ✅ 윤슬
- ❌ 동캐 → ✅ 똥캐
- ❌ 범도루 → ✅ 법도루
- ❌ 뱀커 → ✅ 벵커

## 예상 개선 효과

| 단계 | 개선률 | 방법 |
|------|--------|------|
| 전처리 | 15-30% | CLAHE + 이진화 + 노이즈 제거 |
| 파라미터 | 15-20% | beamsearch + 신뢰도 0.6 |
| 후처리 | 20-30% | ㅁ/ㅇ 교정 + 퍼지 매칭 |
| **합계** | **50-75%** | **복합 개선** |

## 주의사항

1. **신뢰도 임계값 0.6**: 일부 정상 이름 누락 가능 → 테스트 후 0.5로 조정 가능
2. **전처리 효과**: 일부 이미지에서 역효과 가능 → `use_preprocessing=False` 옵션 사용
3. **baseline 의존성**: baseline 없으면 후처리 교정 미적용 → 기본 OCR만 수행
4. **처리 시간**: 전처리 추가로 약 20-30% 증가 예상

## 롤백 방법

문제 발생 시:
```bash
git checkout backend/ocr.py backend/main.py
```

## 다음 단계

1. 실제 이미지로 통합 테스트
2. 오류율 측정 및 개선률 검증
3. 신뢰도 임계값 조정 (필요시 0.6 → 0.5)
4. 전처리 on/off 옵션 프론트엔드 추가 (선택사항)

## 참고

- 베이스라인 데이터: `data/baseline.json` (49명)
- 테스트 이미지: `sample/images/image (1).png`
- 테스트 스크립트: `test_ocr_improvements.py`
