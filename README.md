# YoutubeDescriptionParse

Windows 10과 macOS에서 같은 Git 저장소로 개발하는 프로젝트입니다.

현재는 두 운영체제의 공통 저장소 설정을 준비한 단계입니다. 공유 대화의 요구사항을 확보한 뒤 기술 스택과 기능 구현을 이어갑니다. 아직 애플리케이션, 의존성 설치 명령, 빌드 또는 테스트 명령은 없습니다.

## 개발 시작

Git을 설치한 뒤 Windows에서는 PowerShell, macOS에서는 터미널에서 실행합니다.

```text
git clone https://github.com/Twibap/YoutubeDescriptionParse.git
cd YoutubeDescriptionParse
git config --local core.autocrlf false
git status
```

VS Code를 사용한다면 이 폴더를 열고 추천된 EditorConfig 확장을 설치합니다. 편집기 설정은 저장소에 포함되어 있습니다.

두 컴퓨터 사이의 작업 전환, 줄바꿈 설정, 커밋 형식은 [개발 가이드](docs/development.md)를 참고하세요.

## 공통 설정

- `.editorconfig`: UTF-8, 기본 LF 줄바꿈, 공백 2칸 들여쓰기.
- `.gitattributes`: Git의 텍스트 줄바꿈 통일. Windows 명령 스크립트(`.bat`, `.cmd`)는 CRLF.
- `.gitignore`: 운영체제·편집기 임시 파일과 로컬 환경 파일 제외.
- `.vscode/`: 공통 편집기 설정과 EditorConfig 확장 추천.

## 이어갈 대화

[이전 대화](https://chatgpt.com/share/6abfb435-a59c-83ee-ad72-2b0e67f33d95)의 요구사항을 이어갑니다. 링크 내용은 현재 개발 환경의 네트워크 접근 제한으로 아직 읽지 못했습니다.
