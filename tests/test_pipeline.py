import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from youtube_description_parse.models import PlaylistEntry, PlaylistInfo, VideoRecord
from youtube_description_parse.pipeline import collect_playlist, reparse
from youtube_description_parse.storage import load_videos


def video(number: int, *, playlist_id: str = "test-playlist") -> VideoRecord:
    return VideoRecord(
        video_id=f"example{number:04d}",
        video_title=f"영상 {number}",
        video_url=f"https://www.youtube.com/watch?v=example{number:04d}",
        playlist_id=playlist_id,
        playlist_index=number,
        description=f"[식당정보]\n식당 {number}\n서울 강남구 테헤란로 {number}\nhttps://example.com/{number}",
    )


class FakeSource:
    def __init__(
        self, videos: list[VideoRecord], *, failure: Exception | BaseException | None = None
    ):
        self.videos = videos
        self.failure = failure
        self.calls: list[str] = []

    def iter_playlist(self, playlist: str) -> PlaylistInfo:
        return PlaylistInfo(
            self.videos[0].playlist_id,
            [PlaylistEntry(v.video_id, v.video_url, v.playlist_index) for v in self.videos],
        )

    def get_video(self, entry: PlaylistEntry, playlist_id: str) -> VideoRecord:
        self.calls.append(entry.video_id)
        if entry.video_id == self.videos[-1].video_id and self.failure:
            raise self.failure
        return next(v for v in self.videos if v.video_id == entry.video_id)


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_collect_resume_and_csv_roundtrip(tmp_path):
    source = FakeSource([video(1), video(2)])
    progress = []
    started = []
    summary = collect_playlist(
        source, "playlist", tmp_path, on_progress=progress.append, on_start=started.append
    )
    assert (summary.collected, summary.skipped, summary.errors, summary.mentions) == (2, 0, 0, 2)
    assert progress == ["collected", "collected"]
    assert started == [2]
    assert load_videos(tmp_path / "videos.jsonl") == source.videos
    assert (tmp_path / "restaurants.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    with (tmp_path / "restaurants.csv").open(encoding="utf-8-sig", newline="") as stream:
        restaurants = list(csv.DictReader(stream))
    assert [r["name"] for r in restaurants] == ["식당 1", "식당 2"]

    source.calls.clear()
    resumed = collect_playlist(source, "playlist", tmp_path)
    assert (resumed.collected, resumed.skipped) == (0, 2)
    assert source.calls == []
    assert len(rows(tmp_path / "videos.jsonl")) == 2
    assert len(rows(tmp_path / "restaurant_mentions.jsonl")) == 2


def test_repeated_playlist_entry_is_not_collected_twice_even_on_refresh(tmp_path):
    source = FakeSource([video(1), video(1), video(2)])
    summary = collect_playlist(source, "playlist", tmp_path, refresh=True)
    assert summary.collected == 2
    assert summary.skipped == 1
    assert source.calls == [video(1).video_id, video(2).video_id]


def test_failed_video_is_logged_and_retried_without_refetching_success(tmp_path):
    source = FakeSource([video(1), video(2)], failure=RuntimeError("unavailable video"))
    summary = collect_playlist(source, "playlist", tmp_path)
    assert (summary.collected, summary.errors, summary.mentions) == (1, 1, 1)
    assert rows(tmp_path / "collection_errors.jsonl") == [
        {
            "video_id": video(2).video_id,
            "playlist_id": "test-playlist",
            "error": "unavailable video",
        }
    ]
    source.failure = None
    source.calls.clear()
    resumed = collect_playlist(source, "playlist", tmp_path)
    assert (resumed.collected, resumed.skipped, resumed.errors) == (1, 1, 0)
    assert source.calls == [video(2).video_id]
    assert rows(tmp_path / "collection_errors.jsonl") == []


def test_interruption_preserves_checkpoint_and_exports(tmp_path):
    source = FakeSource([video(1), video(2)], failure=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        collect_playlist(source, "playlist", tmp_path)
    assert load_videos(tmp_path / "videos.jsonl") == [video(1)]
    assert len(rows(tmp_path / "restaurant_mentions.jsonl")) == 1
    source.failure = None
    source.calls.clear()
    resumed = collect_playlist(source, "playlist", tmp_path)
    assert (resumed.collected, resumed.skipped) == (1, 1)
    assert source.calls == [video(2).video_id]


def test_refresh_replaces_raw_and_mentions_without_duplicates(tmp_path):
    source = FakeSource([video(1)])
    collect_playlist(source, "playlist", tmp_path)
    source.videos[0] = replace(
        video(1), description=video(1).description.replace("식당 1", "새 이름")
    )
    refreshed = collect_playlist(source, "playlist", tmp_path, refresh=True)
    assert refreshed.collected == 1
    assert len(load_videos(tmp_path / "videos.jsonl")) == 1
    mentions = rows(tmp_path / "restaurant_mentions.jsonl")
    assert len(mentions) == 1
    assert mentions[0]["name"] == "새 이름"
    assert mentions[0]["mention_id"] == "test-playlist:example0001:1"


def test_same_video_in_different_playlists_retains_both_sources(tmp_path):
    collect_playlist(FakeSource([video(1, playlist_id="first")]), "playlist", tmp_path)
    collect_playlist(FakeSource([video(1, playlist_id="second")]), "playlist", tmp_path)
    assert len(load_videos(tmp_path / "videos.jsonl")) == 2
    assert {r["mention_id"] for r in rows(tmp_path / "restaurant_mentions.jsonl")} == {
        "first:example0001:1",
        "second:example0001:1",
    }


def test_limit_selects_first_entries_and_reparse_is_repeatable(tmp_path):
    source = FakeSource([video(1), video(2)])
    collect_playlist(source, "playlist", tmp_path, limit=1)
    assert source.calls == [video(1).video_id]
    raw = (tmp_path / "videos.jsonl").read_bytes()
    first = reparse(tmp_path / "videos.jsonl", tmp_path / "parsed")
    csv_before = (tmp_path / "parsed/restaurants.csv").read_bytes()
    second = reparse(tmp_path / "videos.jsonl", tmp_path / "parsed")
    assert first == second
    assert (tmp_path / "parsed/restaurants.csv").read_bytes() == csv_before
    assert (tmp_path / "videos.jsonl").read_bytes() == raw


def test_corrupt_cache_is_reported_without_overwriting_it(tmp_path):
    raw = tmp_path / "videos.jsonl"
    raw.write_text("{bad json}\n", encoding="utf-8")
    source = FakeSource([video(1)])
    with pytest.raises(ValueError, match="videos.jsonl:1"):
        collect_playlist(source, "playlist", tmp_path)
    assert raw.read_text(encoding="utf-8") == "{bad json}\n"
    assert source.calls == []
