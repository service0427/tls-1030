# TLS-1030 Mobile Collector (BrowserStack Local + Appium)

모바일 디바이스에서 TLS 핑거프린트와 쿠키를 수집하는 도구

## 핵심 기능

- ✅ **BrowserStack Local 터널**: IP 일관성 유지 (쿠키 재사용 가능)
- ✅ **실제 모바일 디바이스**: Samsung Galaxy S23/S24 (Android)
- ✅ **TLS 핑거프린트 수집**: browserleaks.com
- ✅ **쿠키 수집**: Coupang mobile
- ✅ **DB 저장**: main-pc.py와 동일한 형식

## 설치

### 1. Appium-Python-Client 설치

```bash
pip install Appium-Python-Client
```

### 2. BrowserStack Local 바이너리

**자동 다운로드**: 첫 실행 시 자동으로 다운로드됩니다.

**수동 다운로드** (선택):
- URL: https://www.browserstack.com/local-testing/automate
- 저장 위치: `tls-1030/tools/BrowserStackLocal.exe`

### 3. 환경 변수 설정

`.env` 파일 또는 시스템 환경 변수:

```bash
export BROWSERSTACK_USERNAME="bsuser_wHW2oU"
export BROWSERSTACK_ACCESS_KEY="fuymXXoQNhshiN5BsZhp"
```

## 사용법

### 디바이스 목록 보기

```bash
python main-mobile.py --list
```

출력 예시:
```
[1] Samsung Galaxy S23
    OS: Android 13.0
    Browser: Chrome latest
    ID: samsung-galaxy-s23

[2] Samsung Galaxy S24
    OS: Android 14.0
    Browser: Chrome latest
    ID: samsung-galaxy-s24
```

### TLS + 쿠키 수집 (기본)

```bash
# Galaxy S23
python main-mobile.py --device s23

# Galaxy S24
python main-mobile.py --device s24
```

### 검색 포함 수집

```bash
python main-mobile.py --device s23 --search 노트북
```

## 실행 흐름

```
[1/5] BrowserStack Local 터널 시작
      ↓
[2/5] Appium 세션 생성 (실제 모바일 디바이스)
      ↓
[3/5] TLS 핑거프린트 수집 (browserleaks.com)
      ↓
[4/5] 쿠키 수집 (m.coupang.com)
      ↓
[5/5] 데이터베이스 저장
```

## 왜 BrowserStack Local이 필요한가?

### IP 일관성이 중요한 이유

```
❌ 일반 BrowserStack (IP 불일치):
  로컬 PC IP: 123.45.67.89
  BrowserStack Device IP: 98.76.54.32  ← 다른 IP!
  → Akamai가 쿠키 재사용 차단

✅ BrowserStack Local (IP 일치):
  로컬 PC IP: 123.45.67.89
  BrowserStack Device → Local Tunnel → 123.45.67.89  ← 같은 IP!
  → Akamai가 정상 요청으로 인식
```

### 터널 동작 방식

```
[Local PC] ←→ [BrowserStack Local Tunnel] ←→ [BrowserStack Cloud]
                                                      ↓
                                            [Mobile Device (Chrome)]
                                                      ↓
                                            [Coupang Server]
                                            (sees: Local PC IP)
```

## 주요 클래스

### BrowserStackLocalManager

BrowserStack Local 터널 관리

```python
manager = BrowserStackLocalManager(access_key)
manager.start()         # 터널 시작
manager.check_status()  # 상태 확인
manager.stop()          # 터널 중지
```

### MobileCollector

Appium을 통한 데이터 수집

```python
collector = MobileCollector(device_config, hub_url)
collector.create_driver()              # 세션 생성
collector.collect_tls_fingerprint()    # TLS 수집
collector.collect_cookies()            # 쿠키 수집
collector.close()                      # 세션 종료
```

## 디바이스 설정

### 지원 디바이스 (config/mobile.devices.json)

**Android (✅ 지원)**:
- Samsung Galaxy S23 (Android 13)
- Samsung Galaxy S24 (Android 14)

**iOS (❌ 차단됨)**:
- iPhone 15/15 Pro Max
- 이유: Safari TLS 핑거프린트가 Coupang에서 차단 (0% 성공률)

### 새 디바이스 추가

`config/mobile.devices.json`:

```json
{
  "android_devices": [
    {
      "device": "Samsung Galaxy S25",
      "os_version": "14.0",
      "browser": "Chrome",
      "browser_version": "latest",
      "bs_device_name": "Samsung Galaxy S25"
    }
  ]
}
```

## 데이터베이스 스키마

### TLS Fingerprints 테이블

```sql
INSERT INTO tls_fingerprints (
    device_name,        -- "Samsung Galaxy S23 (Chrome)"
    browser,            -- "chrome"
    os_version,         -- "Android 13.0"
    tls_data,           -- JSON (cipher_suites, extensions, etc.)
    http2_data,         -- JSON (SETTINGS, WINDOW_UPDATE, HEADERS)
    ja3_hash,           -- "abc123..."
    akamai_fingerprint, -- "def456..."
    collected_at        -- TIMESTAMP
)
```

### Cookies 테이블

```sql
INSERT INTO cookies (
    device_name,        -- "Samsung Galaxy S23 (Chrome)"
    browser,            -- "chrome"
    os_version,         -- "Android 13.0"
    tls_fingerprint_id, -- FK to tls_fingerprints
    cookie_data,        -- JSON {"key": "value", ...}
    collected_at,       -- TIMESTAMP
    cookie_type         -- "mobile"
)
```

## 트러블슈팅

### BrowserStack Local 터널 연결 실패

**증상**: "Tunnel connection timeout (30s)"

**해결**:
1. 방화벽 확인: BrowserStackLocal.exe 허용
2. 프록시 설정: `--proxy-host`, `--proxy-port` 추가
3. 포트 충돌: 다른 Local 인스턴스 종료

### Appium 세션 생성 실패

**증상**: "Failed to create Appium session"

**해결**:
1. BrowserStack 계정 확인: https://automate.browserstack.com
2. 디바이스 가용성 확인: 다른 디바이스 시도
3. 인증 정보 확인: `.env` 파일 또는 환경 변수

### TLS 데이터 수집 실패

**증상**: "Failed to extract TLS data"

**해결**:
1. 페이지 로딩 시간 증가: `time.sleep(10)` 시도
2. browserleaks.com 접속 확인: 브라우저에서 수동 테스트
3. 디바이스 재시작: 새 세션으로 재시도

### 쿠키 수집 실패

**증상**: "Cookie collection failed"

**해결**:
1. Coupang 접속 확인: m.coupang.com 수동 테스트
2. 모바일 UA 확인: Desktop UA 사용 여부 확인
3. 세션 타임아웃: 대기 시간 증가

## 비교: main-pc.py vs main-mobile.py

| 항목 | main-pc.py | main-mobile.py |
|------|------------|----------------|
| 브라우저 제어 | nodriver (CDP) | Appium (WebDriver) |
| 브라우저 소스 | 로컬 Chrome | BrowserStack 실기기 |
| TLS 수집 | ✅ | ✅ |
| 쿠키 수집 | ✅ (CDP) | ✅ (WebDriver + JS) |
| IP 일관성 | N/A (로컬) | ✅ (Local Tunnel) |
| 디바이스 타입 | PC (Windows) | Mobile (Android) |

## 참고 문서

- main-pc.py: PC용 Chrome 수집
- docs/MOBILE_ANSWER.md: 모바일 UA 차단 분석
- docs/MULTI_DEVICE_TEST_RESULT.md: 멀티 디바이스 테스트 결과
- config/mobile.devices.json: 디바이스 설정

## 라이선스

Internal use only
