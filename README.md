# TLS-1030 - TLS 지문 수집 및 크롤링

TLS 지문 수집과 curl-cffi 기반 웹 크롤링을 위한 모듈화 아키텍처

## 주요 기능

- **모듈화 설계**: DB, TLS, 쿠키, 파일 관리를 위한 재사용 가능한 모듈
- **main-pc.py**: nodriver를 사용한 TLS 지문 및 쿠키 수집
- **curlcffi.py**: 수집된 TLS 데이터를 사용한 멀티페이지 크롤링
- **깔끔한 출력**: 모든 임시 파일은 `output/` 디렉토리에 정리
- **Session 관리**: curl-cffi Session을 통한 자동 쿠키 관리
- **DB 통합**: 쿠키 타입(browser/crawled) 구분 저장

## 디렉토리 구조

```
tls-1030/
├── main-pc.py          # TLS 및 쿠키 수집기
├── curlcffi.py         # 멀티페이지 크롤러
├── config.py           # 설정 파일
├── requirements.txt    # Python 의존성
├── .env                # 환경 변수 (.env.example에서 생성)
│
├── modules/            # 공유 모듈
│   ├── db_manager.py       # 데이터베이스 작업
│   ├── tls_config.py       # TLS 설정 빌더
│   ├── cookie_handler.py   # 쿠키 형식 변환
│   └── file_manager.py     # 파일 입출력
│
├── utils/              # 유틸리티
│   ├── traceid.py          # TraceID 생성기
│   └── chrome_detector.py  # Chrome 버전 감지
│
├── collectors/         # 데이터 수집기
│   ├── cookie_collector.py # 메인 수집 로직
│   └── tls_extractor.py    # TLS 데이터 추출
│
├── output/             # 모든 출력 저장 위치
│   ├── html/               # HTML/RSC 응답
│   ├── json/               # JSON 결과 및 쿠키
│   └── logs/               # 요청 헤더 및 로그
│
└── user/               # 사용자 데이터 디렉토리
    └── {version}/          # 버전별 사용자 프로필
```

## 설치

1. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

2. **환경 설정**
   ```bash
   cp .env.example .env
   # 데이터베이스 인증 정보로 .env 파일 편집
   ```

3. **Chrome 버전 확인**
   ```bash
   python main-pc.py --list
   ```

## 사용법

### 1. TLS 지문 및 쿠키 수집

```bash
# 시스템 Chrome 사용 (기본값)
python main-pc.py

# 특정 버전 사용
python main-pc.py --version 142

# 검색 포함 (멀티페이지)
python main-pc.py --search 노트북 --page 3

# 사용 가능한 Chrome 버전 목록
python main-pc.py --list
```

### 2. curl-cffi로 크롤링

```bash
# 3페이지 크롤링 (DB에서 최신 TLS 데이터 사용)
python curlcffi.py 노트북 3

# 다른 키워드로 5페이지 크롤링
python curlcffi.py 마우스 5
```

## 출력 파일

모든 출력은 정리된 디렉토리에 저장됩니다:

- **HTML/RSC**: `output/html/page_{num}_chrome{ver}.{ext}`
- **결과**: `output/json/results_chrome{ver}.json`
- **쿠키**: `output/json/cookies_chrome{ver}_{timestamp}.json`
- **로그**: `output/logs/request_headers_chrome{ver}_{timestamp}.json`

## 설정 관리 (config.py)

### 타임아웃 설정
```python
TIMEOUTS = {
    'total_collection': 120,    # 전체 수집 최대 시간 (초)
    'page_load': 10,            # 페이지 로드
    'search_load': 15,          # 검색 로드
    'blocking_check': 2,        # 차단 확인
    'cookie_collection': 5,     # 쿠키 수집
}
```

### 대기 시간 설정
```python
WAIT_TIMES = {
    'main_page': 2,             # 메인 페이지 로드 후
    'search_page': 3,           # 검색 페이지 로드 후
    'between_pages': (3, 5),    # 페이지 간 랜덤 대기 (초)

    # 페이지 이동 설정 (navigate_to_next_page)
    'button_stabilize': 0.5,      # 버튼 찾기 전 대기
    'button_find_attempts': 3,    # 버튼 찾기 최대 시도 횟수
    'button_retry_interval': 0.2, # 시도 간격
    'after_click': 0.3,           # 클릭 후 대기
}
```

## 모듈 사용 예제

### DbManager

```python
from modules import DbManager

db = DbManager()

# 최신 TLS 지문 가져오기
data = db.get_latest_fingerprint()

# TLS 지문 저장
tls_id = db.save_tls_fingerprint(
    device_name="Chrome 142.0.7444.60",
    browser='chrome',
    os_version='Windows 10',
    tls_data=tls_data,
    http2_data=http2_data,
    ja3_hash=ja3_hash,
    akamai_fingerprint=akamai_fp,
    collected_at=datetime.now()
)

# 쿠키 저장 (타입 지정)
cookie_id = db.save_cookies(
    device_name=device_name,
    browser='chrome',
    os_version='Windows 10',
    tls_fingerprint_id=tls_id,
    cookie_data=cookies,
    collected_at=datetime.now(),
    cookie_type='browser'  # 또는 'crawled'
)
```

### TlsConfig

```python
from modules import TlsConfig

# curl-cffi용 extra_fp 빌드
extra_fp = TlsConfig.build_extra_fp(tls_data)

# 페이지 1용 헤더 빌드 (HTML)
headers = TlsConfig.build_headers(
    chrome_version="142.0.7444.60",
    page_num=1,
    cookie_header=''  # Session이 관리하므로 빈 문자열
)

# 페이지 2+ 헤더 빌드 (RSC)
headers = TlsConfig.build_headers(
    chrome_version="142.0.7444.60",
    page_num=2,
    referer=previous_url,
    cookie_header=''
)
```

### CookieHandler

```python
from modules import CookieHandler

# 헤더 문자열로 변환
cookie_header = CookieHandler.to_header_string(cookies)

# 딕셔너리로 변환
cookie_dict = CookieHandler.to_dict(cookies)
```

### Session 쿠키 관리 (curl-cffi)

```python
from curl_cffi import requests

# Session 생성
session = requests.Session()

# 쿠키 설정 (올바른 방법)
for name, value in cookie_dict.items():
    session.cookies.set(name, value, domain='.coupang.com', path='/')

# 요청 (Session이 자동으로 쿠키 관리)
response = session.get(url, headers=headers, extra_fp=extra_fp)

# Session이 Set-Cookie를 자동으로 처리
# 다음 요청에서 업데이트된 쿠키 사용
```

## tls-1029와의 차이점

1. **모듈화 아키텍처**: 모든 공통 로직을 재사용 가능한 모듈로 추출
2. **깔끔한 출력**: 루트 디렉토리에 임시 파일 없음
3. **간소화된 스크립트**: main-pc.py와 curlcffi.py가 훨씬 깔끔함
4. **더 나은 분리**: DB, TLS, 쿠키, 파일이 모두 별도 모듈
5. **쉬운 테스트**: 각 모듈을 독립적으로 테스트 가능
6. **Session 관리**: curl-cffi Session을 통한 자동 쿠키 관리
7. **Config 기반**: 모든 타이밍을 config.py에서 중앙 관리
8. **DB 쿠키 타입**: browser/crawled 구분 저장

## 주의사항

- curl_cffi 0.13.0 사용 (제한된 `extra_fp` 지원)
- `tls_min_version`, `tls_grease`, `tls_permute_extensions`만 사용
- 페이지 2+ Next.js RSC (React Server Components) 형식 사용
- DB에서 최신 TLS 데이터 자동 선택
- Session이 쿠키를 자동 관리 (수동 파싱 불필요)
- 쿠키는 DB에만 저장 (jar 파일 불필요)

## 문제 해결

### 페이지 2가 차단되는 경우

**원인**: Session 쿠키가 제대로 설정되지 않음

**해결**:
```python
# ❌ 잘못된 방법
session.cookies.update(cookie_dict)

# ✅ 올바른 방법
for name, value in cookie_dict.items():
    session.cookies.set(name, value, domain='.coupang.com', path='/')
```

### 페이지 이동이 느린 경우

**config.py**에서 대기 시간 조정:
```python
WAIT_TIMES = {
    'button_stabilize': 0.1,      # 빠르게
    'button_find_attempts': 2,    # 시도 횟수 감소
    'button_retry_interval': 0.1, # 간격 단축
    'after_click': 0.1,           # 클릭 후 대기 단축
    'search_page': 1,             # 페이지 로드 대기 단축
}
```

## 라이센스

MIT License
