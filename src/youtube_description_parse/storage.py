"""UTF-8 원문 보존과 원자적 결과 파일 교체."""

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, fields
from pathlib import Path
from typing import TextIO

from .models import CollectionError, ParseResult, RestaurantMention, VideoRecord


@contextmanager
def _atomic_text(path: Path, *, encoding: str = "utf-8") -> Iterator[TextIO]:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding=encoding, newline="") as stream:
            yield stream
            stream.flush()
            os.fsync(stream.fileno())
        # Windows에서도 대상 파일을 열린 상태로 교체하지 않는다.
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with _atomic_text(path) as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_videos(path: Path, *, missing_ok: bool = False) -> list[VideoRecord]:
    if missing_ok and not path.exists():
        return []
    records: dict[tuple[str, str], VideoRecord] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("JSON 객체가 필요합니다")
                video = VideoRecord(**row)
                for name in ("video_id", "video_title", "video_url", "playlist_id", "description"):
                    if not isinstance(getattr(video, name), str):
                        raise ValueError(f"{name}은 문자열이어야 합니다")
                if not video.video_id or not video.playlist_id or not video.video_url:
                    raise ValueError("출처 ID와 영상 URL은 비어 있을 수 없습니다")
                if video.playlist_index is not None and (
                    type(video.playlist_index) is not int or video.playlist_index < 1
                ):
                    raise ValueError("playlist_index는 양의 정수 또는 null이어야 합니다")
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line_number}: 잘못된 영상 원문: {error}") from error
            records[(video.playlist_id, video.video_id)] = video
    return list(records.values())


def save_videos(path: Path, videos: Iterable[VideoRecord]) -> None:
    write_jsonl(path, (asdict(video) for video in videos))


def save_results(output_dir: Path, result: ParseResult) -> None:
    write_jsonl(
        output_dir / "restaurant_mentions.jsonl",
        (asdict(mention) for mention in result.mentions),
    )
    write_jsonl(output_dir / "parse_review.jsonl", (asdict(review) for review in result.reviews))
    column_names = [field.name for field in fields(RestaurantMention)]
    with _atomic_text(output_dir / "restaurants.csv", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=column_names, lineterminator="\n")
        writer.writeheader()
        writer.writerows(asdict(mention) for mention in result.mentions)


def save_collection_errors(output_dir: Path, errors: Iterable[CollectionError]) -> None:
    write_jsonl(output_dir / "collection_errors.jsonl", (asdict(error) for error in errors))
