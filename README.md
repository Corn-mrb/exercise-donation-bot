# 🏃 운동 기부 봇 (Exercise Donation Bot)

운동할 때마다 sats가 쌓이고, Lightning Network로 기부하는 Discord 봇입니다!

## ✨ 기능

- 🏋️ **운동 기록**: 걷기, 자전거, 달리기, 수영, 웨이트
- ⚡ **Lightning 기부**: Blink API를 통한 자동 결제
- 📊 **통계 & 리더보드**: 개인/서버 통계 확인
- 🔄 **자동 전송**: 결제 확인 후 기부 지갑으로 자동 전송

## 📋 명령어

### 설정
| 명령어 | 설명 |
|--------|------|
| `/운동설정` | 운동별 기부 금액 설정 (sats/km, sats/kg) |
| `/내설정` | 현재 설정 확인 |

### 운동
| 명령어 | 설명 |
|--------|------|
| `/운동` | 운동 기록 (5종류) |
| `/내통계` | 개인 통계 확인 |

### 기부
| 명령어 | 설명 |
|--------|------|
| `/운동기부` | 누적 sats를 Lightning으로 기부 |
| `/기부내역` | 기부 이력 확인 |

### 리더보드
| 명령어 | 설명 |
|--------|------|
| `/운동순위` | 서버 전체 순위 (7개 카테고리) |

### 도움말
| 명령어 | 설명 |
|--------|------|
| `/사용법` | 전체 명령어 안내 |

## 🚀 설치

### 1. 저장소 클론
```bash
git clone https://github.com/YOUR_USERNAME/exercise-donation-bot.git
cd exercise-donation-bot
```

### 2. 가상환경 생성
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정
```bash
cp .env.example .env
nano .env  # 또는 원하는 에디터로 편집
```

**.env 필수 설정:**
```
DISCORD_TOKEN=your_discord_bot_token
BLINK_API_KEY=your_blink_api_key
DONATION_ADDRESS=your_lightning_address@blink.sv
```

### 5. 데이터 폴더 확인
```bash
# data 폴더가 없으면 자동 생성됩니다
```

### 6. 봇 실행
```bash
python3 bot.py
```

## 🔧 PM2로 운영

```bash
# PM2 설치
npm install -g pm2

# 봇 시작
pm2 start bot.py --name exercise-bot --interpreter python3 --cwd /path/to/bot

# 자동 시작 설정
pm2 save
pm2 startup
```

## ⚙️ 환경변수 설정

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `DISCORD_TOKEN` | ✅ | - | Discord 봇 토큰 |
| `BLINK_API_KEY` | ✅ | - | Blink API 키 |
| `BLINK_API_ENDPOINT` | ❌ | `https://api.blink.sv/graphql` | Blink API 엔드포인트 |
| `DATABASE_PATH` | ❌ | `./data/exercise_bot.db` | DB 파일 경로 |
| `DONATION_ADDRESS` | ❌ | `citadel@blink.sv` | 기부 받을 Lightning Address |
| `MIN_DONATION` | ❌ | `1` | 최소 기부 금액 (sats) |
| `MAX_DONATION` | ❌ | `1000000` | 최대 기부 금액 (sats) |
| `ENVIRONMENT` | ❌ | `development` | 환경 (development/production) |
| `LOG_LEVEL` | ❌ | `INFO` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |
| `PAYMENT_CHECK_INTERVAL` | ❌ | `5` | 결제 확인 간격 (초) |
| `PAYMENT_TIMEOUT` | ❌ | `300` | 결제 타임아웃 (초) |
| `MAX_RETRIES` | ❌ | `3` | API 재시도 횟수 |
| `RETRY_DELAY` | ❌ | `1` | 재시도 대기 시간 (초) |
| `TZ` | ❌ | `Asia/Seoul` | 시간대 |

## ⚡ Blink API 설정

1. [Blink](https://blink.sv) 계정 생성
2. API Key 발급 (권한: `receive`, `read`)
3. Lightning Address 확인 (예: `yourname@blink.sv`)
4. `.env` 파일에 설정

## 📁 파일 구조

```
exercise-donation-bot/
├── bot.py              # 메인 봇
├── config.py           # 설정 및 환경변수 관리
├── database.py         # DB 연결 및 쿼리 관리
├── lightning_blink.py  # Blink Lightning API
├── requirements.txt    # Python 의존성
├── .env.example        # 환경변수 템플릿
├── .gitignore          # Git 제외 파일
├── README.md           # 문서
└── data/               # DB 저장 (Git 제외)
    └── .gitkeep
```

## 🔒 보안

- `.env` 파일은 절대 Git에 올리지 마세요
- Blink API Key는 `receive`, `read` 권한만 사용
- 정기적으로 API Key 재생성 권장
- `LOG_LEVEL=DEBUG`는 프로덕션에서 사용하지 마세요

## 🐛 문제 해결

### 봇이 시작되지 않을 때
```bash
# 환경변수 확인
cat .env

# 로그 레벨 높여서 실행
LOG_LEVEL=DEBUG python3 bot.py
```

### 결제가 확인되지 않을 때
- `PAYMENT_TIMEOUT` 값 증가
- `PAYMENT_CHECK_INTERVAL` 값 감소
- Blink API 연결 상태 확인

### DB 에러
```bash
# data 폴더 권한 확인
ls -la data/

# DB 파일 삭제 후 재시작 (데이터 초기화)
rm data/exercise_bot.db
python3 bot.py
```

## 📄 라이센스

MIT License

## 🤝 기여

이슈와 PR 환영합니다!
