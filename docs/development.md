# Windows 10 · macOS 개발 환경

두 기기는 같은 Git 저장소와 의존성 잠금 파일을 사용합니다. Python 3.12.14를 `.python-version`으로, 의존성을 `uv.lock`으로 고정합니다. 각 기기의 가상 환경은 uv가 `.venv`에 따로 준비합니다.

## 최초 설정

Git을 설치하고 `git --version`으로 확인합니다. 편집기는 VS Code를 사용할 수 있습니다. Windows 10에서는 PowerShell, macOS에서는 터미널을 사용합니다.

uv는 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)에 따라 설치합니다. Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS 터미널:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Homebrew를 사용한다면 대신 `brew install uv`로 설치할 수 있습니다. 설치 후 터미널을 다시 열고 `uv --version`으로 확인합니다.

다음 명령은 두 환경에서 동일합니다.

```sh
git clone https://github.com/Twibap/YoutubeDescriptionParse.git
cd YoutubeDescriptionParse
git config --local core.autocrlf false
git status
git pull --ff-only
uv sync --frozen
```

uv가 필요한 Python 버전과 잠금 파일에 맞는 의존성을 준비합니다. `uv run --frozen`을 사용하면 `.venv`를 직접 활성화하지 않아도 됩니다. VS Code에서는 저장소 폴더를 열고 추천된 확장을 설치합니다.

각 기기에서 Git 작성자 이름과 이메일도 설정합니다. 기존 설정이 있다면 그대로 사용합니다.

```sh
git config --global user.name "작성자 이름"
git config --global user.email "작성자 이메일"
```

텍스트 파일은 UTF-8과 LF 줄바꿈으로 저장합니다. Windows 명령 스크립트(`.bat`, `.cmd`)는 CRLF를 사용합니다. 저장소의 `.gitattributes`와 `.editorconfig`를 기준으로 편집기 설정을 맞춥니다. `core.autocrlf false`는 각 체크아웃에서 한 번 설정합니다.

## 기기를 옮길 때

작업을 시작하기 전에 `git status`로 로컬 변경을 확인하고 `git pull --ff-only`로 최신 커밋을 가져옵니다. 변경이 남아 있으면 먼저 커밋하거나 별도로 보관합니다. Pull이 실패하면 원인을 확인한 뒤 진행합니다. 최신 커밋을 가져온 후 `uv sync --frozen`으로 해당 기기의 의존성을 맞춥니다.

작업을 마친 기기에서는 변경 파일을 확인하고 커밋합니다. 다음 예시의 `README.md`를 실제 변경 파일로 바꿉니다.

```sh
git diff
git add README.md
git diff --cached
git commit
git push origin master
```

다른 기기에서는 같은 저장소에서 `git pull --ff-only`와 `uv sync --frozen`을 실행합니다. 기기 간 이동은 Git으로 관리하는 파일을 커밋하고 푸시한 뒤 풀하는 방식으로 합니다. 이 환경의 자동 작업에서 원격 푸시는 사용자가 요청했을 때 실행합니다.

`.env`와 인증 정보는 기기마다 따로 준비합니다. 의존성 폴더, 패키지 캐시, `.venv`, 빌드 출력은 복사하지 않고 해당 기기에서 설치·생성합니다. 원문 캐시와 수집 결과는 기본적으로 `data/`에 저장되며 Git으로 공유하지 않습니다. 이미 수집한 데이터를 다른 기기에서 재처리하려면 `videos.jsonl`을 별도로 백업·전달하고 `parse` 명령으로 결과를 다시 생성할 수 있습니다.

## 실행과 확인

작게 시작할 때는 기본 재생목록의 앞 세 항목을 수집합니다. `collect` 뒤에 다른 재생목록 URL이나 ID를 지정할 수 있고, `--limit`을 생략하면 전체가 대상입니다. `--refresh`를 추가하면 기존 영상 메타데이터도 다시 수집합니다.

```text
uv run --frozen youtube-description-parse collect --output-dir data --limit 3
```

YouTube 접속이나 봇 확인 때문에 수집을 완료하지 못해도 저장된 원문의 파싱은 네트워크 없이 검증할 수 있습니다.

```text
uv run --frozen youtube-description-parse parse --input examples/videos.jsonl --output-dir data/demo
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv build
```

출력 형식과 파싱 범위는 [README](../README.md)를 참고하세요. CI는 Windows, macOS, Linux에서 위 검사를 실행하도록 구성합니다. Linux 클라우드에서의 검증 결과가 두 로컬 운영체제나 실제 YouTube 접속 검증을 대신하지는 않습니다.

의존성을 변경할 때는 `uv add` 또는 `uv remove`를 사용하고 `pyproject.toml`과 `uv.lock`을 함께 커밋합니다. 일상적인 설치는 `uv sync --frozen`을 사용합니다.

## 호환 규칙

- 파일 이름과 import 경로의 대소문자를 정확히 맞추고, 대소문자만 다른 파일을 만들지 않습니다.
- Windows에서 사용할 수 없는 파일 이름(`CON`, `NUL` 등)과 문자(`:`, `*`, `?` 등)를 피합니다.
- 문서와 설정에는 저장소 기준 상대 경로와 `/`를 사용합니다. 사용자 이름이 들어간 절대 경로는 저장하지 않습니다.
- 공통 작업 명령은 PowerShell과 macOS 터미널 양쪽에서 실행 가능하게 작성합니다. 셸 전용 문법이 필요한 명령은 운영체제별로 표시합니다.
- 실행 자동화는 Python으로 작성해 운영체제별 셸 차이를 줄입니다.

## 커밋 메시지

커밋 메시지의 언어는 자유롭게 선택합니다. 첫 줄은 작업을 설명하는 짧은 제목으로 쓰고, 빈 줄 뒤에 주요 변경을 짧게 적습니다. 예시:

```text
Windows와 macOS 공통 개발 환경 구성

- UTF-8과 LF 줄바꿈 기준 추가
- 기기 간 Git 작업 절차 문서화
- 로컬 설정과 생성 파일 제외
```
