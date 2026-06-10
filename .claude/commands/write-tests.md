# 테스트 코드 작성

주어진 파일 또는 모듈에 대한 pytest 테스트 코드를 작성합니다.

## 규칙

이 프로젝트의 테스트 작성 규칙:

1. **파일 위치**: `tests/test_<모듈명>.py` (예: `core/storage.py` → `tests/test_storage.py`)
2. **프레임워크**: pytest (unittest 스타일 클래스 사용 가능)
3. **외부 의존성 격리**:
   - `storage.py` 테스트: `monkeypatch.setattr(storage, "DATA_DIR", tmp_path)` 로 임시 디렉토리 사용
   - Selenium 드라이버: `unittest.mock.MagicMock()` 으로 대체
   - 구글 시트 API: `core.sheets._get_client` 를 patch
4. **테스트 클래스**: 기능 단위로 클래스로 묶기 (예: `class TestParseFollowers`, `class TestExcluded`)
5. **파라미터화**: 입력값 다양성이 중요한 경우 `@pytest.mark.parametrize` 사용
6. **커버리지 우선순위**: 정상 경로 → 엣지 케이스(빈 입력, None, 잘못된 형식) → 예외 경로

## 작업 절차

$ARGUMENTS 를 분석해 다음을 수행합니다:

1. 대상 파일(`$ARGUMENTS`)을 읽어 공개 함수/클래스/메서드 파악
2. 기존 테스트 파일이 있으면 읽어서 중복 방지
3. 테스트가 없거나 커버리지가 부족한 항목 식별
4. `tests/test_<모듈명>.py` 에 테스트 작성 (기존 파일이 있으면 추가)
5. 작성 후 `.venv/bin/pytest tests/test_<모듈명>.py -v` 로 실행 확인

## 실행 예시

```
/write-tests core/storage.py
/write-tests core/scraper.py
/write-tests ui/widgets/follower_filter.py
```

인수 없이 실행하면 현재 변경된 파일(git diff 기준)에 대한 테스트를 작성합니다.
