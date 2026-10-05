"""Windows와 macOS에서 같은 명령으로 실행하는 CLI."""

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from .pipeline import collect_playlist, reparse
from .youtube import DEFAULT_PLAYLIST_ID, YoutubeMetadataSource


def _positive_integer(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요")
    return number


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube 영상 설명의 [식당정보] 수집")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="재생목록 또는 채널 일반 동영상 메타데이터 수집")
    collect.add_argument(
        "source", nargs="?", default=DEFAULT_PLAYLIST_ID, help="재생목록 URL·ID 또는 채널 URL·@핸들"
    )
    collect.add_argument("--output-dir", type=Path, default=Path("data"))
    collect.add_argument("--limit", type=_positive_integer, help="앞에서 N개 항목만 대상으로 지정")
    collect.add_argument("--refresh", action="store_true", help="저장된 영상도 다시 수집")
    parse = commands.add_parser("parse", help="저장한 원문을 네트워크 없이 재파싱")
    parse.add_argument("--input", type=Path, default=Path("data/videos.jsonl"))
    parse.add_argument("--output-dir", type=Path, default=Path("data"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    try:
        if args.command == "parse":
            result = reparse(args.input, args.output_dir)
            print(f"식당 언급 {len(result.mentions)}건, 검토 필요 {len(result.reviews)}건")
            return 0
        # 목록 열거는 별도 요청이며 진행 바에는 영상별 처리만 표시한다.
        with tqdm(desc="영상 처리", unit="영상", file=sys.stderr) as progress:
            summary = collect_playlist(
                YoutubeMetadataSource(),
                args.source,
                args.output_dir,
                limit=args.limit,
                refresh=args.refresh,
                on_progress=lambda _: progress.update(),
                on_start=lambda total: progress.reset(total=total),
            )
        print(
            f"수집 {summary.collected}건, 건너뜀 {summary.skipped}건, 실패 {summary.errors}건; "
            f"식당 언급 {summary.mentions}건, 검토 필요 {summary.reviews}건"
        )
        if summary.errors:
            print(f"수집 실패 내역: {args.output_dir / 'collection_errors.jsonl'}", file=sys.stderr)
        return 1 if summary.errors else 0
    except KeyboardInterrupt:
        print(
            "\n수집을 중단했습니다. 같은 명령으로 저장된 영상부터 이어갈 수 있습니다.",
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
