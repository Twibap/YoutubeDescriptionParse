# YoutubeDescriptionParse

YouTube 재생목록과 채널 일반 동영상의 설명에서 식당 정보를 추출하는 Python CLI입니다. [이전 대화](https://chatgpt.com/share/6abfb435-a59c-83ee-ad72-2b0e67f33d95)의 요구사항을 반영했습니다. 수집한 설명 원문을 보관하므로 파싱 규칙을 바꿔도 영상을 다시 수집하지 않고 결과를 갱신할 수 있습니다.

## 시작하기

Windows 10과 macOS에서 Git과 [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치합니다. Python 버전은 `.python-version`의 3.12.14, 의존성은 `uv.lock`으로 고정합니다. 운영체제별 설치와 기기 간 이동은 [개발 가이드](docs/development.md)를 참고하세요.

다음 명령은 Windows PowerShell과 macOS 터미널에서 동일합니다.

```text
git clone https://github.com/Twibap/YoutubeDescriptionParse.git
cd YoutubeDescriptionParse
git config --local core.autocrlf false
uv sync --frozen
```

`uv sync`가 필요한 Python과 `.venv` 환경을 준비합니다. YouTube 추출에 필요한 Deno와 EJS도 함께 설치하므로 별도의 JavaScript 런타임 설치는 필요하지 않습니다. 아래의 `uv run` 명령에는 가상 환경을 직접 활성화할 필요가 없습니다.

## 영상 수집과 식당 추출

기본 재생목록은 `PLCNYoGrzVJuUWTlwZ2CH9nfQF08959pIj`입니다. 우선 앞의 세 항목만 대상으로 실행합니다.

```text
uv run --frozen youtube-description-parse collect --output-dir data --limit 3
```

재생목록 URL 또는 ID를 `collect` 뒤에 지정할 수도 있습니다. URL에 `&`가 있으면 큰따옴표로 감쌉니다.

```text
uv run --frozen youtube-description-parse collect PLCNYoGrzVJuUWTlwZ2CH9nfQF08959pIj --output-dir data --limit 3
```

`--limit 3`은 재생목록의 앞 세 항목을 수집 대상으로 정합니다. 성공한 영상 세 개를 채우는 옵션은 아닙니다. 생략하면 전체 재생목록을 대상으로 합니다. 저장된 영상 메타데이터는 캐시로 재사용하며, `--refresh`를 추가하면 기존 메타데이터도 다시 수집합니다.

```text
uv run --frozen youtube-description-parse collect --output-dir data --refresh
```

YouTube 접속 제한이나 봇 확인으로 수집이 실패할 수 있습니다. 비공개·삭제 등 접근할 수 없는 영상은 실패로 기록하고 다음 영상을 처리합니다. 개별 영상의 실패 내역은 `collection_errors.jsonl`에서 확인합니다. 영상 재생 형식의 선택은 생략하므로, 다운로드 가능한 형식이 없어도 설명을 얻은 공개 영상은 수집할 수 있습니다.

수집 중 표시되는 경고는 다음과 같이 구분합니다.

| 경고 | 의미와 확인 방법 |
| --- | --- |
| `unable to extract yt initial data` / `Incomplete data ... re-fetching using API` | 웹페이지의 초기 데이터가 부족해 API로 재시도합니다. 경고 이후 성공할 수 있으며, 실패 여부는 최종 요약과 실패 파일에서 확인합니다. |
| `No supported JavaScript runtime could be found` | 실행 중인 환경에서 Deno를 찾지 못했습니다. 최신 소스에서 `uv sync --frozen`을 실행하고 아래 명령으로 설치를 확인합니다. |
| `Private video` | 비공개 영상에 접근할 수 없습니다. 실패 파일에 영상 ID를 남기고 나머지 수집을 계속합니다. |

```text
uv sync --frozen
uv run --frozen deno --version
```

`수집`은 이번 실행에서 새로 저장한 영상, `건너뜀`은 캐시 또는 중복 항목, `실패`는 이번 실행의 수집 오류입니다. `검토 필요`는 저장한 설명을 해석할 때 확인이 필요한 건수이며, 수집 실패와 별개입니다. 경고만으로 설명 누락을 단정하지 말고 검토 파일의 `reason`, `video_id`, `raw_text`를 확인하세요.

이전 버전은 일부 비공개 응답을 빈 설명으로 저장할 수 있었습니다. 이미 저장된 원문은 자동 삭제하지 않으며, `--refresh`로 다시 수집하면 접근 실패가 실패 파일에 기록됩니다. 다시 수집에 실패한 영상의 기존 캐시도 보존합니다.

네트워크 없이 추출 기능을 확인하려면 포함된 예제를 사용합니다.

```text
uv run --frozen youtube-description-parse parse --input examples/videos.jsonl --output-dir data/demo
```

예제는 실제 첫 영상의 설명 핵심 구간과 가상 영상 두 개로 구성되어 있습니다. 기대 결과는 식당 언급 세 건과 검토 한 건입니다.

실제로 수집한 원문도 같은 방식으로 다시 파싱합니다.

```text
uv run --frozen youtube-description-parse parse --input data/videos.jsonl --output-dir data
```

## 채널의 일반 동영상 전체 수집

채널 URL이나 `@핸들`도 `collect`에 지정할 수 있습니다. 다음 명령은 PowerShell, WSL, macOS에서 같으며, `--limit`을 생략하면 `/videos` 탭의 공개된 목록을 끝까지 탐색합니다.

```text
uv run --frozen youtube-description-parse collect "https://www.youtube.com/@kim3meals/videos" --output-dir data/kim3meals
```

처음 접속을 확인할 때는 같은 명령에 `--limit 3`을 추가합니다. 짧은 형태도 사용할 수 있습니다.

```text
uv run --frozen youtube-description-parse collect "@kim3meals" --output-dir data/kim3meals --limit 3
```

핸들이나 채널 기본 URL도 `/videos`로 연결합니다. Shorts와 라이브 탭은 포함하지 않습니다. `/channel/UC…/videos` 형태도 지원하며, YouTube 목록에서 공개적으로 조회할 수 없는 비공개·삭제 영상까지 찾는 기능은 아닙니다.

중단했다면 같은 명령을 다시 실행합니다. 채널의 고유 UC ID를 캐시 출처로 사용하므로 핸들 URL 대신 UC URL을 입력해도 성공한 영상을 다시 수집하지 않습니다. 채널별 출력 폴더를 사용하면 기존 재생목록 결과와 따로 관리할 수 있습니다.

결과 파일과 CSV 열은 재생목록 수집과 같습니다. 채널 수집의 `playlist_id`에는 호환성을 위해 `channel:UC…` 형태의 출처 ID를 저장합니다. `playlist_index`는 해당 영상을 수집했을 때의 목록 순번입니다. 식당 정보의 `mention_id`도 이 채널 출처 ID를 사용하며 가게나 영상 출처를 자동으로 병합하지 않습니다.

생성된 `data/kim3meals/restaurants.csv`를 Google 내 지도에 가져와 사용할 수 있습니다. 기존 지도를 갱신하려면 레이어에서 CSV를 다시 가져옵니다.

## 결과 파일

`collect`는 원문 캐시와 수집 실패 내역을 저장하고, `collect`와 `parse`는 식당 JSONL·CSV·검토 파일을 생성하거나 갱신합니다. `parse`는 입력 원문 파일과 기존 수집 실패 내역을 변경하지 않습니다.

| 파일 | 내용 |
| --- | --- |
| `videos.jsonl` | 영상 메타데이터와 설명 전체 원문 캐시 |
| `restaurant_mentions.jsonl` | 식당명·주소·지도 URL과 영상·재생목록 출처 |
| `restaurants.csv` | 같은 식당 언급을 Excel에서 열기 쉬운 UTF-8 BOM으로 저장 |
| `parse_review.jsonl` | 해석이 불명확하거나 지원하지 않는 식당 정보 패턴 |
| `collection_errors.jsonl` | 개별 영상 수집 실패 내역 |

설명 원문은 별도로 보존하고, 식당 결과 파일에는 식당 정보와 출처 필드만 담습니다. 결과의 `mention_id`는 `재생목록ID:영상ID:영상내순서`로 구성되는 출처 식별자입니다. 식당의 영구 ID가 아니며, 같은 식당이 여러 영상에 등장해도 자동 병합하지 않습니다. 주소도 정규화하지 않고 추출한 값을 유지합니다.

같은 `--output-dir`로 여러 재생목록을 수집하면 저장된 원문과 식당 결과가 함께 유지됩니다. 재생목록별로 결과를 나누려면 각각 다른 출력 폴더를 지정합니다.

설명의 `[식당정보]` 표식 뒤에서 식당명, 주소, 지도 URL을 추출합니다. 기본 형태는 다음과 같으며 표식 하나에 여러 식당이 있는 설명, 여러 표식, 한 줄 표기, Markdown 링크도 처리합니다.

```text
[식당정보]
노무토모
서울 송파구 백제고분로39길 22 1층
https://naver.me/FoEN86nJ
```

광고·촬영·BGM 등의 구간은 식당 추출 대상에서 제외합니다. 해석이 불명확한 내용은 검토 파일에 남기므로 `parse_review.jsonl`도 함께 확인하세요.

## 네이버 지도에서 공유하기

`restaurants.csv`의 `map_url`에 있는 네이버 지도 링크를 공유하면 해당 가게 위치를 바로 열 수 있습니다. 여러 가게를 링크 하나로 공유하려면 네이버 지도의 저장 목록 공유 기능을 사용합니다. 별도 웹사이트나 API 키는 필요하지 않습니다. 스프레드시트 링크 수식과 저장 목록 만드는 순서는 [네이버 지도 공유 안내](docs/naver-map.md)를 참고하세요.

## 개발 확인

```text
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv build
```

GitHub Actions는 Windows, macOS, Linux에서 같은 검사를 실행하도록 구성했습니다. 테스트는 오프라인에서 파싱과 수집 흐름을 검증하며, 실제 YouTube 접속 성공 여부는 별도로 확인해야 합니다.
