"""외부 네트워크와 다운로드 없이 수집기 계약을 검증한다."""

import builtins
import json

import pytest

from youtube_description_parse.models import PlaylistEntry, PlaylistInfo, VideoRecord
from youtube_description_parse.pipeline import collect_playlist
from youtube_description_parse.storage import load_videos
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

    def extract_info(self, url, *, download, process=True):
        self.calls.append((url, download, process))
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
    assert fake.calls == [(PLAYLIST_URL, False, True)]
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
    assert fake.calls == [(VIDEO_URL, False, False)]
    options = fake.options[0]
    assert options["noplaylist"] is True
    assert options["skip_download"] is True
    assert options["extract_flat"] is False
    assert options["ignore_no_formats_error"] is False
    assert not options.get("nocheckcertificate")


def test_missing_description_is_a_valid_empty_description():
    fake = FakeYoutubeDL({"id": VIDEO_ID, "title": "설명 없는 영상"})
    video = YoutubeMetadataSource(youtube_dl_factory=fake).get_video(
        PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID
    )
    assert video.description == ""
    assert video.video_url == VIDEO_URL


@pytest.fixture
def offline_youtube_source(monkeypatch):
    """실제 yt-dlp 추출/오류 처리를 사용하고 YouTube 응답만 고정한다."""
    from yt_dlp import YoutubeDL
    from yt_dlp.extractor.youtube import YoutubeIE

    class FixtureYoutubeIE(YoutubeIE):
        def __init__(self, responses):
            super().__init__()
            self.responses = responses

        @classmethod
        def ie_key(cls):
            # 같은 키로 등록해 YoutubeDL의 기본 YouTube 추출기를 교체한다.
            return "Youtube"

        def _initial_extract(self, url, smuggled_data, webpage_url, webpage_client, video_id):
            return (
                '<meta property="og:title" content="YouTube">',
                {},
                None,
                False,
                [self.responses[video_id]],
                None,
            )

        def _extract_formats_and_subtitles(self, *_args):
            # 재생 형식이 없어도 공개 영상의 설명을 사용할 수 있다.
            yield {}

        def _extract_storyboard(self, *_args):
            return []

        def mark_watched(self, *_args):
            pass

    def fail_network(*_args, **_kwargs):
        raise AssertionError("오프라인 YouTube 회귀 테스트에서 네트워크를 요청했습니다.")

    monkeypatch.setattr(YoutubeDL, "urlopen", fail_network)

    def make_source(responses):
        def factory(options):
            client = YoutubeDL(options)
            client.add_info_extractor(FixtureYoutubeIE(responses))
            return client

        return YoutubeMetadataSource(youtube_dl_factory=factory)

    return make_source


def test_real_extractor_preserves_description_without_playable_formats(
    offline_youtube_source,
):
    description = "  [식당정보]\r\n맛집\n서울 강남구 테헤란로 10\nhttps://naver.me/test  \n"
    source = offline_youtube_source(
        {
            VIDEO_ID: {
                "playabilityStatus": {"status": "OK"},
                "videoDetails": {
                    "videoId": VIDEO_ID,
                    "title": "설명 있는 공개 영상",
                    "shortDescription": description,
                    "isPrivate": False,
                },
            }
        }
    )

    video = source.get_video(PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID)

    assert video.video_title == "설명 있는 공개 영상"
    assert video.description == description


def test_real_extractor_rejects_private_video_with_fallback_title(offline_youtube_source):
    from yt_dlp.utils import DownloadError

    source = offline_youtube_source(
        {VIDEO_ID: {"playabilityStatus": {"status": "LOGIN_REQUIRED", "reason": "Private video"}}}
    )

    # 이전 설정은 HTML의 "YouTube" 제목과 없는 설명을 정상 영상으로 반환했다.
    with pytest.raises(DownloadError, match="Private video"):
        source.get_video(PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), DEFAULT_PLAYLIST_ID)


def test_private_video_is_logged_without_polluting_success_cache(
    offline_youtube_source, monkeypatch, tmp_path
):
    private_id = "12345678901"
    source = offline_youtube_source(
        {
            VIDEO_ID: {
                "playabilityStatus": {"status": "OK"},
                "videoDetails": {
                    "videoId": VIDEO_ID,
                    "title": "공개 영상",
                    "shortDescription": "[식당정보] 맛집 서울 강남구 테헤란로 10 https://naver.me/test",
                    "isPrivate": False,
                },
            },
            private_id: {
                "playabilityStatus": {"status": "LOGIN_REQUIRED", "reason": "Private video"}
            },
        }
    )
    playlist = PlaylistInfo(
        DEFAULT_PLAYLIST_ID,
        [
            PlaylistEntry(VIDEO_ID, VIDEO_URL, 1),
            PlaylistEntry(private_id, f"https://www.youtube.com/watch?v={private_id}", 2),
        ],
    )
    monkeypatch.setattr(source, "iter_playlist", lambda _playlist: playlist)

    summary = collect_playlist(source, DEFAULT_PLAYLIST_ID, tmp_path)

    assert (summary.collected, summary.errors, summary.mentions) == (1, 1, 1)
    assert [video.video_id for video in load_videos(tmp_path / "videos.jsonl")] == [VIDEO_ID]
    errors = [
        json.loads(line)
        for line in (tmp_path / "collection_errors.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(errors) == 1
    assert errors[0]["video_id"] == private_id
    assert errors[0]["playlist_id"] == DEFAULT_PLAYLIST_ID
    assert "Private video" in errors[0]["error"]


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
