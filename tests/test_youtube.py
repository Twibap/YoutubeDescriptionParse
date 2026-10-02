"""외부 네트워크와 다운로드 없이 수집기 계약을 검증한다."""

import builtins

import pytest

from youtube_description_parse.models import PlaylistEntry, VideoRecord
from youtube_description_parse.youtube import (
    DEFAULT_PLAYLIST_ID,
    YoutubeMetadataSource,
    normalize_playlist,
)

VIDEO_ID = "abcdefghijk"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
PLAYLIST_URL = f"https://www.youtube.com/playlist?list={DEFAULT_PLAYLIST_ID}"


class FakeYoutubeDL:
    def __init__(self, result):
        self.result = result
        self.options = []
        self.calls = []

    def __call__(self, options):
        self.options.append(options)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def extract_info(self, url, *, download):
        self.calls.append((url, download))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    "value",
    [
        DEFAULT_PLAYLIST_ID,
        f" {DEFAULT_PLAYLIST_ID} ",
        PLAYLIST_URL,
        f"https://www.youtube.com/watch?v={VIDEO_ID}&list={DEFAULT_PLAYLIST_ID}&index=8",
        f"https://music.youtube.com/playlist?list={DEFAULT_PLAYLIST_ID}",
        f"youtube.com/playlist?list={DEFAULT_PLAYLIST_ID}",
    ],
)
def test_normalize_playlist_accepts_ids_and_youtube_urls(value):
    assert normalize_playlist(value) == (DEFAULT_PLAYLIST_ID, PLAYLIST_URL)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "  ",
        None,
        "not-a-playlist",
        "PLtoo_short",
        VIDEO_ID,
        f"https://example.com/playlist?list={DEFAULT_PLAYLIST_ID}",
        f"https://youtube.com.evil.example/playlist?list={DEFAULT_PLAYLIST_ID}",
        f"https://user@youtube.com/playlist?list={DEFAULT_PLAYLIST_ID}",
        f"https://youtube.com:443/playlist?list={DEFAULT_PLAYLIST_ID}",
        f"https://youtube.com/channel?list={DEFAULT_PLAYLIST_ID}",
        "https://youtube.com/playlist",
        "https://youtube.com/playlist?list=",
        "https://youtube.com/watch?v=abcdefghijk",
        f"https://youtube.com/playlist?list={DEFAULT_PLAYLIST_ID}&list=WL",
    ],
)
def test_normalize_playlist_rejects_missing_invalid_or_foreign_lists(value):
    with pytest.raises(ValueError):
        normalize_playlist(value)


def test_flat_playlist_metadata_is_collected_without_downloading():
    fake = FakeYoutubeDL(
        {
            "_type": "playlist",
            "id": DEFAULT_PLAYLIST_ID,
            "entries": [
                {"id": VIDEO_ID, "url": VIDEO_URL, "playlist_index": 8},
                {"id": "12345678901", "url": "12345678901"},
            ],
        }
    )
    playlist = YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(
        f"https://youtube.com/watch?v={VIDEO_ID}&list={DEFAULT_PLAYLIST_ID}"
    )

    assert playlist.playlist_id == DEFAULT_PLAYLIST_ID
    assert playlist.entries == [
        PlaylistEntry(VIDEO_ID, VIDEO_URL, 8),
        PlaylistEntry("12345678901", "https://www.youtube.com/watch?v=12345678901", 2),
    ]
    assert fake.calls == [(PLAYLIST_URL, False)]
    options = fake.options[0]
    assert options["extract_flat"] is True
    assert options["skip_download"] is True
    assert options["ignoreerrors"] is False
    assert options["extractor_retries"] == 3
    assert not options.get("nocheckcertificate")
    assert "proxy" not in options


def test_video_source_fields_and_description_are_preserved_exactly():
    description = "  식당 이름\r\n주소: 서울시 종로구\n\nhttps://example.com  \n"
    source_url = f"https://www.youtube.com/watch?v={VIDEO_ID}&feature=shared"
    fake = FakeYoutubeDL(
        {
            "id": VIDEO_ID,
            "title": "영상 제목",
            "description": description,
            "webpage_url": source_url,
        }
    )
    entry = PlaylistEntry(VIDEO_ID, f"{VIDEO_URL}&list={DEFAULT_PLAYLIST_ID}", 12)
    video = YoutubeMetadataSource(youtube_dl_factory=fake).get_video(entry, DEFAULT_PLAYLIST_ID)

    assert video == VideoRecord(
        VIDEO_ID, "영상 제목", source_url, DEFAULT_PLAYLIST_ID, 12, description
    )
    assert fake.calls == [(VIDEO_URL, False)]
    options = fake.options[0]
    assert options["noplaylist"] is True
    assert options["skip_download"] is True
    assert options["extract_flat"] is False
    assert options["ignore_no_formats_error"] is True
    assert not options.get("nocheckcertificate")


def test_missing_description_is_a_valid_empty_description():
    fake = FakeYoutubeDL({"id": VIDEO_ID, "title": "설명 없는 영상"})
    video = YoutubeMetadataSource(youtube_dl_factory=fake).get_video(
        PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID
    )
    assert video.description == ""
    assert video.video_url == VIDEO_URL


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        [],
        {"_type": "video", "id": DEFAULT_PLAYLIST_ID, "entries": []},
        {"_type": "playlist", "id": "WL", "entries": []},
        {"_type": "playlist", "id": DEFAULT_PLAYLIST_ID},
        {"_type": "playlist", "id": DEFAULT_PLAYLIST_ID, "entries": "invalid"},
        {"_type": "playlist", "id": DEFAULT_PLAYLIST_ID, "entries": [None]},
        {"_type": "playlist", "id": DEFAULT_PLAYLIST_ID, "entries": [{"id": "bad"}]},
        {
            "_type": "playlist",
            "id": DEFAULT_PLAYLIST_ID,
            "entries": [{"id": VIDEO_ID, "playlist_index": False}],
        },
    ],
)
def test_invalid_playlist_metadata_is_an_error(metadata):
    source = YoutubeMetadataSource(youtube_dl_factory=FakeYoutubeDL(metadata))
    with pytest.raises(ValueError):
        source.iter_playlist(DEFAULT_PLAYLIST_ID)


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        [],
        {},
        {"id": "12345678901", "title": "다른 영상"},
        {"id": VIDEO_ID, "title": None},
        {"_type": "playlist", "id": VIDEO_ID, "title": "영상"},
        {"id": VIDEO_ID, "title": "영상", "description": 42},
        {"id": VIDEO_ID, "title": "영상", "webpage_url": None},
        {"id": VIDEO_ID, "title": "영상", "webpage_url": "invalid"},
    ],
)
def test_invalid_video_metadata_is_an_error(metadata):
    source = YoutubeMetadataSource(youtube_dl_factory=FakeYoutubeDL(metadata))
    with pytest.raises(ValueError):
        source.get_video(PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID)


@pytest.mark.parametrize("operation", ["playlist", "video"])
def test_extraction_errors_propagate_for_pipeline_recording(operation):
    error = RuntimeError("비공개 또는 삭제된 영상")
    source = YoutubeMetadataSource(youtube_dl_factory=FakeYoutubeDL(error))
    error_type = ValueError if operation == "playlist" else RuntimeError
    with pytest.raises(error_type, match="비공개 또는 삭제된 영상"):
        if operation == "playlist":
            source.iter_playlist(DEFAULT_PLAYLIST_ID)
        else:
            source.get_video(PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID)


def test_parser_and_source_construction_work_without_yt_dlp(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "yt_dlp":
            raise ModuleNotFoundError("yt_dlp")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    source = YoutubeMetadataSource()
    assert normalize_playlist(DEFAULT_PLAYLIST_ID) == (DEFAULT_PLAYLIST_ID, PLAYLIST_URL)
    with pytest.raises(RuntimeError, match="uv sync"):
        source.iter_playlist(DEFAULT_PLAYLIST_ID)


def test_invalid_input_is_rejected_before_constructing_network_client():
    fake = FakeYoutubeDL(None)
    source = YoutubeMetadataSource(youtube_dl_factory=fake)
    with pytest.raises(ValueError):
        source.iter_playlist("invalid")
    with pytest.raises(ValueError):
        source.get_video(PlaylistEntry("invalid", "invalid", 1), DEFAULT_PLAYLIST_ID)
    assert fake.options == []
