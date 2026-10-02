"""메타데이터 수집, 영상별 체크포인트, 오프라인 재파싱."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import CollectionError, ParseResult, PlaylistEntry, PlaylistInfo, VideoRecord
from .parser import parse_description
from .storage import load_videos, save_collection_errors, save_results, save_videos


class MetadataSource(Protocol):
    def iter_playlist(self, playlist: str) -> PlaylistInfo: ...

    def get_video(self, entry: PlaylistEntry, playlist_id: str) -> VideoRecord: ...


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    collected: int
    skipped: int
    errors: int
    mentions: int
    reviews: int


def parse_videos(videos: Iterable[VideoRecord]) -> ParseResult:
    result = ParseResult()
    for video in videos:
        parsed = parse_description(video)
        result.mentions.extend(parsed.mentions)
        result.reviews.extend(parsed.reviews)
    return result


def reparse(input_path: Path, output_dir: Path) -> ParseResult:
    videos = load_videos(input_path)
    result = parse_videos(videos)
    save_results(output_dir, result)
    return result


def collect_playlist(
    source: MetadataSource,
    playlist: str,
    output_dir: Path,
    *,
    limit: int | None = None,
    refresh: bool = False,
    on_progress: Callable[[str], None] | None = None,
    on_start: Callable[[int], None] | None = None,
) -> CollectionSummary:
    if limit is not None and limit < 1:
        raise ValueError("limit은 1 이상이어야 합니다")
    raw_path = output_dir / "videos.jsonl"
    videos = {(v.playlist_id, v.video_id): v for v in load_videos(raw_path, missing_ok=True)}
    playlist_info = source.iter_playlist(playlist)
    targets = playlist_info.entries if limit is None else playlist_info.entries[:limit]
    collected = skipped = 0
    errors: list[CollectionError] = []
    seen: set[tuple[str, str]] = set()
    output_dir.mkdir(parents=True, exist_ok=True)
    if on_start:
        on_start(len(targets))
    try:
        for entry in targets:
            key = (playlist_info.playlist_id, entry.video_id)
            if key in seen or (key in videos and not refresh):
                skipped += 1
                if on_progress:
                    on_progress("skipped")
                continue
            seen.add(key)
            try:
                video = source.get_video(entry, playlist_info.playlist_id)
            except Exception as error:
                errors.append(
                    CollectionError(entry.video_id, playlist_info.playlist_id, str(error))
                )
                if on_progress:
                    on_progress("error")
                continue
            updated = videos | {key: video}
            # 영상 하나마다 완전한 JSONL 스냅샷을 교체해 중단 시 부분 줄을 남기지 않는다.
            save_videos(raw_path, updated.values())
            videos = updated
            collected += 1
            if on_progress:
                on_progress("collected")
    finally:
        result = parse_videos(videos.values())
        save_results(output_dir, result)
        save_collection_errors(output_dir, errors)
    return CollectionSummary(
        collected, skipped, len(errors), len(result.mentions), len(result.reviews)
    )
