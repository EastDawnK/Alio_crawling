# ALIO 내부규정 문서 크롤러

공공기관 경영정보 공개시스템(ALIO)에서 기관별 내부규정 첨부파일을 내려받는 Python 프로그램입니다.

기관 목록을 TXT 또는 CSV 파일로 입력하면 기관별 폴더를 만들고 문서를 저장합니다. 처리에 실패한 기관은 완료 처리하지 않으므로 다음 실행에서 다시 시도할 수 있습니다.

## 주요 기능

- TXT 또는 CSV 기관 목록 지원
- 기관별 다운로드 폴더 자동 생성
- PDF, HWPX, HWP 첨부파일 지원
- 실제 API 응답과 다운로드 이벤트를 기준으로 대기
- 페이지 자동 이동 및 중복 페이지 방문 방지
- 오류 발생 시 화면 캡처 저장
- 성공한 기관만 `진행상황.txt`에 기록
- 프로그램 재실행 시 완료된 기관 자동 건너뛰기

## 실행 환경

- Windows
- Python 3.10 이상 권장
- Chromium 기반 Playwright 브라우저
- 인터넷 연결

## 설치

PowerShell을 열고 다음 명령을 실행합니다.

```powershell
pip install playwright
playwright install chromium
```

Python이 여러 개 설치되어 있다면 다음 형식을 사용할 수 있습니다.

```powershell
python -m pip install playwright
python -m playwright install chromium
```

설치 확인:

```powershell
python -c "from playwright.sync_api import sync_playwright; print('Playwright 설치 완료')"
```

## 필요한 폴더 구조

기본 설정은 `C:\ALIO_Data` 폴더를 사용합니다.

```text
C:\ALIO_Data\
├─ 알리오 공공기관 다운로드 리스트.txt
├─ 알리오 공공기관 다운로드 리스트.csv
└─ new\
   ├─ 진행상황.txt
   ├─ 기관명1\
   │  ├─ 1_문서.pdf
   │  └─ error_page_1_item_2.png
   └─ 기관명2\
      └─ 1_문서.pdf
```

다음 항목은 프로그램이 자동으로 생성합니다.

- `C:\ALIO_Data\new`
- 기관별 하위 폴더
- `진행상황.txt`
- 오류 스크린샷

사용자가 준비해야 하는 것은 TXT 또는 CSV 기관 목록 파일입니다.

## 기관 목록 작성

### TXT 형식

파일 경로:

```text
C:\ALIO_Data\알리오 공공기관 다운로드 리스트.txt
```

기관명을 한 줄에 하나씩 입력합니다.

```text
한국전력공사
한국도로공사
한국수자원공사
```

### CSV 형식

파일 경로:

```text
C:\ALIO_Data\알리오 공공기관 다운로드 리스트.csv
```

첫 번째 행은 헤더로 사용하고, 첫 번째 열에 기관명을 입력합니다.

```csv
기관명
한국전력공사
한국도로공사
한국수자원공사
```

TXT와 CSV가 모두 있으면 TXT 파일을 우선 사용합니다. 두 파일이 모두 없으면 코드 내부의 기본 목록을 사용하지만, 현재 기본 목록은 비어 있습니다.

기관명은 ALIO 화면에 표시되는 이름과 정확히 일치해야 합니다.

## 실행 방법

프로그램이 있는 폴더로 이동합니다.

```powershell
cd C:\CSE\인턴
```

다음 명령으로 실행합니다.

```powershell
python .\alio자동화.py
```

현재 코드는 `headless=False`로 설정되어 있어 실행 중 Chromium 창이 표시됩니다. 프로그램이 브라우저를 제어하는 동안 창을 직접 조작하지 않는 것이 좋습니다.

## 다운로드 동작

한 규정에 여러 형식의 첨부파일이 있으면 기본적으로 다음 순서로 한 개를 선택합니다.

1. PDF
2. HWPX
3. HWP

같은 확장자의 파일이 여러 개면 `fileNo`가 큰 파일을 선택합니다.

다운로드 파일명 앞에는 처리 순서가 붙습니다.

```text
1_인사규정.pdf
2_복무규정.pdf
3_직제규정.hwp
```

## 설정 변경

### 기관 목록 파일 경로

`alio자동화.py` 하단의 값을 변경합니다.

```python
txt_file = r"C:\ALIO_Data\알리오 공공기관 다운로드 리스트.txt"
csv_file = r"C:\ALIO_Data\알리오 공공기관 다운로드 리스트.csv"
```

### 다운로드 경로

함수 호출 부분에서 `base_download_dir`를 지정합니다.

```python
scrape_alio_data(
    target_org_list,
    base_download_dir=r"D:\ALIO_Data\new",
)
```

### 파일 형식 우선순위

HWPX 또는 HWP를 우선하려면 함수 호출 부분을 다음과 같이 변경합니다.

```python
scrape_alio_data(
    target_org_list,
    preferred_extensions=('.hwpx', '.hwp', '.pdf'),
)
```

### 백그라운드 실행

브라우저 창을 숨기려면 다음 코드를 변경합니다.

```python
browser = p.chromium.launch(headless=True)
```

처음에는 오류 화면을 확인할 수 있도록 `headless=False` 사용을 권장합니다.

## 진행상황과 재실행

모든 항목이 성공한 기관은 다음 파일에 기록됩니다.

```text
C:\ALIO_Data\new\진행상황.txt
```

프로그램을 다시 실행하면 여기에 기록된 기관은 건너뜁니다.

특정 기관을 다시 처리하려면 다음 순서로 진행합니다.

1. 프로그램을 종료합니다.
2. `진행상황.txt`에서 해당 기관명을 삭제합니다.
3. 필요한 경우 해당 기관의 기존 다운로드 폴더를 확인합니다.
4. 프로그램을 다시 실행합니다.

항목 하나라도 실패한 기관은 `진행상황.txt`에 기록되지 않으며 다음 실행에서 다시 처리됩니다.

## 오류 스크린샷

항목 처리 중 오류가 발생하면 기관 폴더에 다음 형식으로 화면이 저장됩니다.

```text
error_page_페이지번호_item_항목번호.png
```

예시:

```text
error_page_2_item_4.png
```

오류 메시지와 스크린샷을 함께 확인하면 ALIO 화면 구조 변경이나 팝업 로딩 실패를 진단하기 쉽습니다.

## 자주 발생하는 문제

### Playwright를 찾을 수 없음

```text
Playwright가 설치되어 있지 않습니다.
```

다음 명령을 실행합니다.

```powershell
python -m pip install playwright
python -m playwright install chromium
```

### 브라우저 실행 파일을 찾을 수 없음

Playwright 패키지는 설치됐지만 Chromium이 설치되지 않은 상태입니다.

```powershell
python -m playwright install chromium
```

### 실행해도 기관을 건너뜀

`C:\ALIO_Data\new\진행상황.txt`에 해당 기관이 기록돼 있는지 확인합니다. 다시 처리하려면 해당 줄을 삭제합니다.

### 기관을 선택할 수 없음

- 기관명 앞뒤 공백을 제거합니다.
- ALIO에서 사용하는 공식 기관명과 목록의 이름이 같은지 확인합니다.
- TXT 파일이 UTF-8로 저장됐는지 확인합니다.

### 팝업 또는 다운로드 시간 초과

- 인터넷 연결을 확인합니다.
- ALIO 사이트가 정상적으로 열리는지 확인합니다.
- 실행 중인 브라우저 창을 직접 조작하지 않습니다.
- 기관 폴더에 저장된 오류 스크린샷을 확인합니다.

### CSV 한글이 깨짐

현재 프로그램은 CSV 파일을 UTF-8로 읽습니다. Excel에서 저장할 때 `CSV UTF-8` 형식을 선택합니다.

## 주의사항

- 이 프로그램은 ALIO 페이지 구조와 선택자에 의존하므로 사이트 개편 시 수정이 필요할 수 있습니다.
- 다운로드한 문서의 이용 조건과 공개 범위를 확인하세요.
- 짧은 시간에 과도한 요청을 보내지 마세요.
- 실행 중 브라우저를 수동 조작하면 자동화 흐름이 깨질 수 있습니다.
- `진행상황.txt`를 삭제하면 모든 기관을 처음부터 다시 처리합니다.

## 파일

- `alio자동화.py`: ALIO 크롤링 프로그램
- `README.md`: 설치 및 사용 설명서
