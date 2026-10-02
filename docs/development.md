# Windows 10 · macOS 개발 환경

두 기기는 같은 Git 저장소를 사용합니다. 런타임, 패키지 매니저, 제품 기능은 공유 대화의 요구사항을 확인한 뒤 정합니다. 현재는 운영체제에 공통으로 필요한 작업 환경을 준비합니다.

## 최초 설정

Git을 설치하고 `git --version`으로 확인합니다. 편집기는 VS Code를 사용할 수 있습니다. Windows 10에서는 PowerShell, macOS에서는 터미널을 사용합니다. 다음 명령은 두 환경에서 동일합니다.

```sh
git clone https://github.com/Twibap/YoutubeDescriptionParse.git
cd YoutubeDescriptionParse
git config --local core.autocrlf false
git status
git pull --ff-only
```

각 기기에서 Git 작성자 이름과 이메일도 설정합니다. 기존 설정이 있다면 그대로 사용합니다.

```sh
git config --global user.name "작성자 이름"
git config --global user.email "작성자 이메일"
```

텍스트 파일은 UTF-8과 LF 줄바꿈으로 저장합니다. Windows 명령 스크립트(`.bat`, `.cmd`)는 CRLF를 사용합니다. 저장소의 `.gitattributes`와 `.editorconfig`를 기준으로 편집기 설정을 맞춥니다. `core.autocrlf false`는 각 체크아웃에서 한 번 설정합니다.

## 기기를 옮길 때

작업을 시작하기 전에 `git status`로 로컬 변경을 확인하고 `git pull --ff-only`로 최신 커밋을 가져옵니다. 변경이 남아 있으면 먼저 커밋하거나 별도로 보관합니다. Pull이 실패하면 원인을 확인한 뒤 진행합니다.

작업을 마친 기기에서는 변경 파일을 확인하고 커밋합니다. 다음 예시의 `README.md`를 실제 변경 파일로 바꿉니다.

```sh
git diff
git add README.md
git diff --cached
git commit
git push origin master
```

다른 기기에서는 같은 저장소에서 `git pull --ff-only`를 실행합니다. 기기 간 이동은 Git으로 관리하는 파일을 커밋하고 푸시한 뒤 풀하는 방식으로 합니다. 이 환경의 자동 작업에서 원격 푸시는 사용자가 요청했을 때 실행합니다.

`.env`와 인증 정보는 기기마다 따로 준비합니다. 의존성 폴더, 캐시, 가상 환경, 빌드 출력, 로컬 데이터는 직접 복사하거나 클라우드 동기화하지 않고 해당 기기에서 설치·생성합니다. 런타임이 정해지면 설치 명령과 필요한 환경 변수 이름을 이 문서에 추가합니다.

## 호환 규칙

- 파일 이름과 import 경로의 대소문자를 정확히 맞추고, 대소문자만 다른 파일을 만들지 않습니다.
- Windows에서 사용할 수 없는 파일 이름(`CON`, `NUL` 등)과 문자(`:`, `*`, `?` 등)를 피합니다.
- 문서와 설정에는 저장소 기준 상대 경로와 `/`를 사용합니다. 사용자 이름이 들어간 절대 경로는 저장하지 않습니다.
- 공통 작업 명령은 PowerShell과 macOS 터미널 양쪽에서 실행 가능하게 작성합니다. 셸 전용 문법이 필요한 명령은 운영체제별로 표시합니다.
- 실행 자동화가 필요해지면 선택한 런타임으로 작성해 운영체제별 셸 차이를 줄입니다.

## 커밋 메시지

첫 줄은 작업을 설명하는 짧은 제목으로 쓰고, 빈 줄 뒤에 주요 변경을 짧게 적습니다. 예시:

```text
Windows와 macOS 공통 개발 환경 구성

- UTF-8과 LF 줄바꿈 기준 추가
- 기기 간 Git 작업 절차 문서화
- 로컬 설정과 생성 파일 제외
```
