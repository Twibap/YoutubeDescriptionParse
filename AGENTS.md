# 작업 규칙

- 사용자와의 설명과 개발 문서는 한국어로 작성한다. 커밋 메시지의 언어는 자유롭게 선택한다.
- Windows 10과 macOS에서 같은 소스로 작업할 수 있도록 경로, 파일명 대소문자, 셸 명령의 차이를 고려한다.
- 파일 인코딩과 줄바꿈은 `.editorconfig`와 `.gitattributes`를 따른다.
- 개발 환경과 두 컴퓨터 사이의 작업 전환 방법은 `docs/development.md`를 따른다.
- Python 버전은 `.python-version`, 의존성은 `pyproject.toml`과 `uv.lock`으로 관리한다. 설치는 `uv sync --frozen`, 실행은 `uv run --frozen`을 사용한다.
- Windows와 macOS에서 실행 가능한 설치·실행·테스트 명령을 문서화한다. 검증은 `pytest`, `ruff check .`, `ruff format --check .`, `uv build`를 실행한다.
- 영상 설명 전체 원문은 캐시로 보존하고, 식당 결과에는 식당 정보와 출처 필드만 포함한다. 데이터 모델 계약은 `src/youtube_description_parse/models.py`를 따른다.
- `mention_id`는 식당 언급의 출처 식별자다. 동일 식당 병합이나 주소 정규화는 별도 요구사항 없이 추가하지 않는다.
- 기존 사용자 변경을 보존한다. 클라우드 작업은 이미 격리되어 있으므로 사용자 요청 없이 별도 Git worktree를 만들지 않는다.
- 커밋은 작업을 요약한 제목, 빈 줄, 짧은 세부사항 목록으로 작성한다.
- 원격 push는 사용자가 요청한 경우에 실행한다.
