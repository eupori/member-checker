"""
FastAPI 백엔드 - 카카오톡 멤버 체커 API
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import os
import json
import re

try:
    from .ocr import extract_and_clean_names
except ImportError:
    from ocr import extract_and_clean_names

app = FastAPI(title="카카오톡 멤버 체커")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 (프론트엔드)
frontend_path = os.path.join(os.path.dirname(__file__), '..', 'frontend')
data_path = os.path.join(os.path.dirname(__file__), '..', 'data')

if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# 데이터 디렉토리 생성
os.makedirs(data_path, exist_ok=True)

BASELINE_FILE = os.path.join(data_path, 'baseline.json')


# ========== Models ==========

class BaselineData(BaseModel):
    guildName: str = "HERMES 길드"
    baselineDate: str
    baselineCount: int
    members: List[str]
    updatedAt: Optional[str] = None


class ChatLogResult(BaseModel):
    joins: List[Dict[str, str]]
    leaves: List[Dict[str, str]]
    netChange: int
    expectedCount: int
    expectedMembers: List[str]


class CompareRequest(BaseModel):
    ocr_names: List[str]
    chat_members: List[str]


class CompareResult(BaseModel):
    matched: List[str]
    only_in_screenshot: List[str]
    only_in_chatlog: List[str]
    total_screenshot: int
    total_chatlog: int


class FullAnalysisResult(BaseModel):
    baseline: Dict
    chatlog: Dict
    screenshot: Dict
    comparison: Dict
    summary: Dict


# ========== Baseline API ==========

def load_baseline() -> Optional[dict]:
    """기준 데이터 로드"""
    if os.path.exists(BASELINE_FILE):
        with open(BASELINE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_baseline(data: dict):
    """기준 데이터 저장"""
    data['updatedAt'] = datetime.now().isoformat()
    with open(BASELINE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.get("/api/baseline")
async def get_baseline():
    """현재 기준 데이터 조회"""
    data = load_baseline()
    if not data:
        return {"exists": False, "data": None}
    return {"exists": True, "data": data}


@app.post("/api/baseline")
async def set_baseline(baseline: BaselineData):
    """기준 데이터 설정"""
    save_baseline(baseline.dict())
    return {"success": True, "message": "기준 데이터가 저장되었습니다"}


@app.delete("/api/baseline")
async def delete_baseline():
    """기준 데이터 삭제"""
    if os.path.exists(BASELINE_FILE):
        os.remove(BASELINE_FILE)
    return {"success": True}


# ========== Helper Functions ==========

def extract_nickname(full_name: str) -> str:
    """닉네임 추출 (/ 기준 첫 번째 부분)"""
    return full_name.split('/')[0].strip()


# ========== Chat Log Parsing ==========

def parse_kakao_date(date_str: str) -> Optional[datetime]:
    """카카오톡 날짜 문자열 파싱 (예: '2025년 9월 15일')"""
    match = re.match(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return datetime(year, month, day)
    return None


def parse_chat_log(content: str, baseline_date: str, baseline_members: List[str]) -> ChatLogResult:
    """채팅 로그 파싱하여 입장/퇴장 추출"""
    cutoff_date = datetime.strptime(baseline_date, '%Y-%m-%d')
    
    lines = content.split('\n')
    current_date = None
    joins = []
    leaves = []
    
    for line in lines:
        # 날짜 라인 체크
        date_match = re.match(r'^-+\s*(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)', line)
        if date_match:
            current_date = parse_kakao_date(date_match.group(1))
            continue
        
        # 기준일 이전 스킵
        if not current_date or current_date <= cutoff_date:
            continue
        
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 입장 체크
        join_match = re.match(r'^(.+?)님이 들어왔습니다', line)
        if join_match:
            name = join_match.group(1).strip()
            joins.append({"name": name, "date": date_str})
            continue
        
        # 퇴장 체크
        leave_match = re.match(r'^(.+?)님이 나갔습니다', line)
        if leave_match:
            name = leave_match.group(1).strip()
            leaves.append({"name": name, "date": date_str})
            continue
    
    # 예상 멤버 계산 (닉네임 기준으로 추적)
    # baseline_members는 전체 이름, 닉네임으로 변환하여 관리
    expected_nicknames = set(extract_nickname(m) for m in baseline_members)
    nickname_to_full = {extract_nickname(m): m for m in baseline_members}
    
    for j in joins:
        nick = extract_nickname(j['name'])
        expected_nicknames.add(nick)
        nickname_to_full[nick] = j['name']
    
    for l in leaves:
        nick = extract_nickname(l['name'])
        expected_nicknames.discard(nick)
    
    # 전체 이름으로 다시 변환
    expected_members = set()
    for nick in expected_nicknames:
        if nick in nickname_to_full:
            expected_members.add(nickname_to_full[nick])
        else:
            expected_members.add(nick)
    
    net_change = len(joins) - len(leaves)
    
    return ChatLogResult(
        joins=joins,
        leaves=leaves,
        netChange=net_change,
        expectedCount=len(expected_members),
        expectedMembers=sorted(list(expected_members))
    )


@app.post("/api/parse-chatlog")
async def parse_chatlog_file(file: UploadFile = File(...)):
    """
    카카오톡 채팅 로그 파싱
    기준일 이후의 입장/퇴장 추출
    """
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail=".txt 파일만 업로드 가능합니다")
    
    baseline = load_baseline()
    if not baseline:
        raise HTTPException(status_code=400, detail="먼저 기준 데이터를 설정해주세요")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    result = parse_chat_log(
        content,
        baseline['baselineDate'],
        baseline.get('members', [])
    )
    
    return {
        "success": True,
        "baseline": {
            "date": baseline['baselineDate'],
            "count": baseline['baselineCount']
        },
        "result": result.dict()
    }


# ========== OCR API ==========

@app.post("/api/ocr")
async def ocr_image(file: UploadFile = File(...)):
    """이미지에서 이름 추출 (OCR) - baseline 보정 포함"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")

    image_bytes = await file.read()

    # 베이스라인 로드 (후처리 교정용)
    baseline = load_baseline()
    baseline_members = baseline.get('members', []) if baseline else None

    try:
        names = extract_and_clean_names(image_bytes, baseline_members)
        return {
            "success": True,
            "names": names,
            "count": len(names)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR 처리 실패: {str(e)}")


@app.post("/api/ocr-multiple")
async def ocr_multiple_images(files: List[UploadFile] = File(...)):
    """여러 이미지에서 이름 추출 (OCR) - baseline 보정 포함"""
    # 베이스라인 로드 (후처리 교정용)
    baseline = load_baseline()
    baseline_members = baseline.get('members', []) if baseline else None

    all_names = []

    for file in files:
        if not file.content_type.startswith('image/'):
            continue

        image_bytes = await file.read()
        try:
            names = extract_and_clean_names(image_bytes, baseline_members)
            all_names.extend(names)
        except Exception as e:
            print(f"OCR 실패 ({file.filename}): {e}")

    # 중복 제거
    unique_names = list(dict.fromkeys(all_names))

    return {
        "success": True,
        "names": unique_names,
        "count": len(unique_names)
    }


# ========== Compare API ==========

@app.post("/api/compare")
async def compare_members(request: CompareRequest):
    """스크린샷 OCR 결과와 채팅로그 예상 멤버 비교"""
    screenshot_set = set(request.ocr_names)
    chatlog_set = set(request.chat_members)
    
    matched = list(screenshot_set & chatlog_set)
    only_screenshot = list(screenshot_set - chatlog_set)
    only_chatlog = list(chatlog_set - screenshot_set)
    
    return CompareResult(
        matched=sorted(matched),
        only_in_screenshot=sorted(only_screenshot),
        only_in_chatlog=sorted(only_chatlog),
        total_screenshot=len(screenshot_set),
        total_chatlog=len(chatlog_set)
    )


# ========== Full Analysis API ==========

@app.post("/api/analyze")
async def full_analysis(
    chatlog: UploadFile = File(...),
    screenshots: List[UploadFile] = File(...)
):
    """
    전체 분석: 채팅로그 + 스크린샷 비교
    1. 채팅로그에서 입장/퇴장 파싱
    2. 스크린샷에서 현재 멤버 OCR
    3. 두 결과 비교
    """
    # 기준 데이터 로드
    baseline = load_baseline()
    if not baseline:
        raise HTTPException(status_code=400, detail="먼저 기준 데이터를 설정해주세요")
    
    # 1. 채팅로그 파싱
    if not chatlog.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="채팅로그는 .txt 파일이어야 합니다")
    
    chatlog_content = await chatlog.read()
    chatlog_content = chatlog_content.decode('utf-8')
    
    chatlog_result = parse_chat_log(
        chatlog_content,
        baseline['baselineDate'],
        baseline.get('members', [])
    )
    
    # 2. 스크린샷 OCR (baseline 기반 교정 포함)
    baseline_members = baseline.get('members', [])
    all_names = []
    for file in screenshots:
        if not file.content_type.startswith('image/'):
            continue
        image_bytes = await file.read()
        try:
            names = extract_and_clean_names(image_bytes, baseline_members)
            all_names.extend(names)
        except Exception as e:
            print(f"OCR 실패: {e}")
    
    screenshot_names = list(dict.fromkeys(all_names))  # 중복 제거
    
    # 3. 비교 (닉네임만 추출해서 비교)
    # 스크린샷: 이미 닉네임만 있음
    screenshot_nicknames = set(extract_nickname(n) for n in screenshot_names)
    
    # 예상 멤버: 전체 이름에서 닉네임 추출
    expected_nickname_map = {extract_nickname(n): n for n in chatlog_result.expectedMembers}
    expected_nicknames = set(expected_nickname_map.keys())
    
    matched_nicknames = screenshot_nicknames & expected_nicknames
    only_screenshot_nicknames = screenshot_nicknames - expected_nicknames
    only_expected_nicknames = expected_nicknames - screenshot_nicknames
    
    # 결과 (전체 이름으로 반환)
    matched = sorted(list(matched_nicknames))
    only_screenshot = sorted(list(only_screenshot_nicknames))
    only_expected = sorted([expected_nickname_map[n] for n in only_expected_nicknames])
    
    # 결과 조합
    return {
        "success": True,
        "baseline": {
            "date": baseline['baselineDate'],
            "count": baseline['baselineCount'],
            "guildName": baseline.get('guildName', 'Unknown')
        },
        "chatlog": {
            "joins": chatlog_result.joins,
            "leaves": chatlog_result.leaves,
            "netChange": chatlog_result.netChange,
            "expectedCount": chatlog_result.expectedCount
        },
        "screenshot": {
            "names": screenshot_names,
            "count": len(screenshot_nicknames)  # 중복 제거된 닉네임 수
        },
        "comparison": {
            "matched": matched,
            "matchedCount": len(matched),
            "onlyInScreenshot": only_screenshot,
            "onlyInScreenshotCount": len(only_screenshot),
            "onlyInExpected": only_expected,
            "onlyInExpectedCount": len(only_expected)
        },
        "summary": {
            "baselineCount": baseline['baselineCount'],
            "expectedCount": chatlog_result.expectedCount,
            "actualCount": len(screenshot_nicknames),
            "discrepancy": len(screenshot_nicknames) - chatlog_result.expectedCount
        }
    }


# ========== Main ==========

@app.get("/")
async def root():
    """메인 페이지"""
    index_path = os.path.join(frontend_path, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "카카오톡 멤버 체커 API"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
