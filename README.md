# Discord 멤버 체커

이미지에서 OCR로 이름을 추출하고 Discord 서버 멤버 목록과 비교하는 웹앱

## 기능

- 📸 이미지 업로드 → OCR로 한글 이름 추출
- 👥 Discord 봇으로 서버 멤버 목록 가져오기
- 🔍 비교 결과 표시
  - ✅ 둘 다 있음
  - ⚠️ 이미지에만 있음
  - ❌ Discord에만 있음

## 설치

### 1. 의존성 설치

```bash
cd discord-member-checker
pip install -r requirements.txt
```

### 2. 환경변수 설정

```bash
cp .env.example .env
nano .env
# DISCORD_TOKEN=봇토큰입력
```

### 3. Discord 봇 실행

```bash
cd bot
python discord_bot.py
```

### 4. 웹서버 실행

```bash
cd backend
python main.py
```

또는 uvicorn으로:
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 접속

http://localhost:8000

## Discord 봇 명령어

- `!멤버` - 현재 서버 멤버 목록 출력
- `!목록저장` - 멤버 목록 JSON 파일로 저장

## 사용 방법

1. Discord 서버에서 `!멤버` 명령어로 멤버 목록 가져오기
2. 웹앱에 멤버 목록 캡처 이미지 업로드
3. Discord 멤버 목록 텍스트 붙여넣기
4. "비교하기" 클릭

## 기술 스택

- **백엔드**: FastAPI
- **OCR**: EasyOCR (한글 지원)
- **Discord Bot**: discord.py
- **프론트엔드**: Vanilla JS + CSS
