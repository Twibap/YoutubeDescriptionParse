"""채널 일반 동영상 탭 수집을 실제 네트워크 없이 검증한다."""

import csv
from urllib.parse import quote

import pytest

from youtube_description_parse.models import PlaylistEntry, VideoRecord
from youtube_description_parse.pipeline import collect_playlist
from youtube_description_parse.storage import load_videos
from youtube_description_parse.youtube import YoutubeMetadataSource, normalize_channel

CHANNEL_ID = "UC1234567890123456789012"
OTHER_CHANNEL_ID = "UCabcdefghijklmnopqrstuv"
CHANNEL_URL = "https://www.youtube.com/@kim3meals/videos"
SOURCE_ID = f"channel:{CHANNEL_ID}"
VIDEO_ID = "abcdefghijk"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
SECOND_VIDEO_ID = "12345678901"
SECOND_VIDEO_URL = f"https://www.youtube.com/watch?v={SECOND_VIDEO_ID}"


class FixtureYoutubeDL:
    def __init__(self, responses):
        self.responses = responses
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
        return self.responses[url]


def channel_metadata(**changes):
    metadata = {
        "_type": "playlist",
        "id": CHANNEL_ID,
        "channel_id": CHANNEL_ID,
        "entries": [{"id": VIDEO_ID, "url": VIDEO_ID}],
    }
    return metadata | changes


def video_metadata(video_id=VIDEO_ID, *, channel_id=CHANNEL_ID):
    return {
        "id": video_id,
        "channel_id": channel_id,
        "title": f"영상 {video_id}",
        "description": "[식당정보]\n맛집\n서울 중랑구 망우로 10\nhttps://naver.me/test",
    }


@pytest.mark.parametrize(
    "value",
    [
        CHANNEL_URL,
        "https://www.youtube.com/@kim3meals",
        "youtube.com/@kim3meals/videos",
        "@kim3meals",
        " @kim3meals ",
    ],
)
def test_handle_targets_always_select_the_regular_videos_tab(value):
    assert normalize_channel(value) == (None, CHANNEL_URL)


@pytest.mark.parametrize("suffix", ["", "/videos"])
def test_channel_id_urls_preserve_the_expected_channel_identity(suffix):
    assert normalize_channel(f"https://youtube.com/channel/{CHANNEL_ID}{suffix}") == (
        CHANNEL_ID,
        f"https://www.youtube.com/channel/{CHANNEL_ID}/videos",
    )


@pytest.mark.parametrize("handle", ["@김세끼", f"@{quote('김세끼')}"])
def test_unicode_handles_have_one_canonical_encoded_url(handle):
    expected = f"https://www.youtube.com/@{quote('김세끼')}/videos"
    assert normalize_channel(f"https://youtube.com/{handle}") == (None, expected)


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/@kim3meals/videos",
        "https://user@youtube.com/@kim3meals/videos",
        "https://youtube.com:443/@kim3meals/videos",
        "https://youtube.com/@kim3meals/shorts",
        "https://youtube.com/@kim3meals/streams",
        f"https://youtube.com/watch?v={VIDEO_ID}",
        "https://youtube.com/channel/not-a-channel/videos",
        "https://youtube.com/channel/UCtoo_short/videos",
        "not-a-channel",
        "",
        None,
    ],
)
def test_non_channel_and_other_tab_targets_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_channel(value)


def test_channel_collection_requests_only_the_videos_tab_without_downloads():
    fake = FixtureYoutubeDL({CHANNEL_URL: channel_metadata()})
    playlist = YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist("@kim3meals")

    assert playlist.playlist_id == SOURCE_ID
    assert playlist.entries == [PlaylistEntry(VIDEO_ID, VIDEO_URL, 1)]
    assert fake.calls == [(CHANNEL_URL, False, True)]
    options = fake.options[0]
    assert options["extract_flat"] is True
    assert options["noplaylist"] is False
    assert options["skip_download"] is True
    assert options["ignoreerrors"] is False
    assert not options.get("nocheckcertificate")
    assert "proxy" not in options


def test_channel_id_metadata_takes_priority_over_tab_specific_id():
    fake = FixtureYoutubeDL({CHANNEL_URL: channel_metadata(id=f"{CHANNEL_ID}_videos")})
    playlist = YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(CHANNEL_URL)
    assert playlist.playlist_id == SOURCE_ID


def test_valid_channel_id_is_used_when_channel_id_field_is_absent():
    metadata = channel_metadata()
    del metadata["channel_id"]
    fake = FixtureYoutubeDL({CHANNEL_URL: metadata})
    playlist = YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(CHANNEL_URL)
    assert playlist.playlist_id == SOURCE_ID


def test_empty_channel_videos_tab_is_valid():
    fake = FixtureYoutubeDL({CHANNEL_URL: channel_metadata(entries=[])})
    playlist = YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(CHANNEL_URL)
    assert playlist.playlist_id == SOURCE_ID
    assert playlist.entries == []


@pytest.mark.parametrize(
    "metadata",
    [
        {"_type": "playlist", "id": "@kim3meals", "entries": []},
        channel_metadata(channel_id="invalid"),
        channel_metadata(_type="video"),
    ],
)
def test_channel_metadata_must_provide_a_valid_channel_identity(metadata):
    fake = FixtureYoutubeDL({CHANNEL_URL: metadata})
    with pytest.raises(ValueError):
        YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(CHANNEL_URL)


def test_channel_id_target_rejects_metadata_from_another_channel():
    target = f"https://www.youtube.com/channel/{CHANNEL_ID}/videos"
    fake = FixtureYoutubeDL(
        {target: channel_metadata(channel_id=OTHER_CHANNEL_ID, id=OTHER_CHANNEL_ID)}
    )
    with pytest.raises(ValueError):
        YoutubeMetadataSource(youtube_dl_factory=fake).iter_playlist(target)


def test_channel_video_preserves_raw_description_and_source_fields():
    description = "  [식당정보]\r\n맛집\n서울 광진구 능동로 10\nhttps://naver.me/test  \n"
    metadata = video_metadata() | {"description": description, "webpage_url": VIDEO_URL}
    fake = FixtureYoutubeDL({VIDEO_URL: metadata})
    video = YoutubeMetadataSource(youtube_dl_factory=fake).get_video(
        PlaylistEntry(VIDEO_ID, VIDEO_URL, 7), SOURCE_ID
    )

    assert video == VideoRecord(VIDEO_ID, metadata["title"], VIDEO_URL, SOURCE_ID, 7, description)
    assert fake.calls == [(VIDEO_URL, False, False)]
    assert fake.options[0]["noplaylist"] is True
    assert fake.options[0]["skip_download"] is True


@pytest.mark.parametrize("source_id", ["channel:", "channel:UCshort", "channel:@kim3meals"])
def test_malformed_channel_source_is_rejected_before_client_creation(source_id):
    fake = FixtureYoutubeDL({})
    with pytest.raises(ValueError):
        YoutubeMetadataSource(youtube_dl_factory=fake).get_video(
            PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), source_id
        )
    assert fake.options == []
    assert fake.calls == []


@pytest.mark.parametrize("owner", [None, OTHER_CHANNEL_ID])
def test_channel_source_is_the_listing_origin_not_the_video_owner(owner):
    metadata = video_metadata(channel_id=owner)
    if owner is None:
        del metadata["channel_id"]
    fake = FixtureYoutubeDL({VIDEO_URL: metadata})
    video = YoutubeMetadataSource(youtube_dl_factory=fake).get_video(
        PlaylistEntry(VIDEO_ID, VIDEO_URL, 1), SOURCE_ID
    )
    assert video.playlist_id == SOURCE_ID
    assert video.video_id == VIDEO_ID


def test_channel_collection_keeps_csv_contract_and_resumes_from_raw_cache(tmp_path):
    fake = FixtureYoutubeDL(
        {
            CHANNEL_URL: channel_metadata(entries=[{"id": VIDEO_ID}, {"id": SECOND_VIDEO_ID}]),
            VIDEO_URL: video_metadata(),
            SECOND_VIDEO_URL: video_metadata(SECOND_VIDEO_ID),
        }
    )
    source = YoutubeMetadataSource(youtube_dl_factory=fake)
    summary = collect_playlist(source, CHANNEL_URL, tmp_path)

    assert (summary.collected, summary.skipped, summary.errors, summary.mentions) == (2, 0, 0, 2)
    assert {video.playlist_id for video in load_videos(tmp_path / "videos.jsonl")} == {SOURCE_ID}
    with (tmp_path / "restaurants.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        restaurants = list(reader)
    assert len(reader.fieldnames) == 10
    assert [row["mention_id"] for row in restaurants] == [
        f"{SOURCE_ID}:{VIDEO_ID}:1",
        f"{SOURCE_ID}:{SECOND_VIDEO_ID}:1",
    ]
    assert {row["playlist_id"] for row in restaurants} == {SOURCE_ID}
    assert {row["address"] for row in restaurants} == {"서울 중랑구 망우로 10"}

    cache_before = (tmp_path / "videos.jsonl").read_bytes()
    fake.calls.clear()
    resumed = collect_playlist(source, "@kim3meals", tmp_path)
    assert (resumed.collected, resumed.skipped, resumed.errors) == (0, 2, 0)
    assert fake.calls == [(CHANNEL_URL, False, True)]
    assert (tmp_path / "videos.jsonl").read_bytes() == cache_before


def test_conflicting_channel_id_metadata_cannot_pollute_cache(tmp_path):
    fake = FixtureYoutubeDL(
        {
            CHANNEL_URL: channel_metadata(id=OTHER_CHANNEL_ID),
        }
    )
    with pytest.raises(ValueError):
        collect_playlist(YoutubeMetadataSource(youtube_dl_factory=fake), CHANNEL_URL, tmp_path)
    assert load_videos(tmp_path / "videos.jsonl", missing_ok=True) == []
    assert fake.calls == [(CHANNEL_URL, False, True)]
