import pytest

from youtube_description_parse.storage import load_videos, write_jsonl


def test_atomic_write_failure_leaves_original_file_and_no_temporary_files(tmp_path):
    raw = tmp_path / "videos.jsonl"
    write_jsonl(raw, [{"original": "보존"}])
    before = raw.read_bytes()
    with pytest.raises(TypeError):
        write_jsonl(raw, [{"invalid": object()}])
    assert raw.read_bytes() == before
    assert list(tmp_path.iterdir()) == [raw]


@pytest.mark.parametrize("bad_index", [True, -1, "2"])
def test_invalid_playlist_index_is_rejected(tmp_path, bad_index):
    record = {
        "video_id": "video",
        "video_title": "제목",
        "video_url": "https://example.com",
        "playlist_id": "playlist",
        "playlist_index": bad_index,
        "description": "원문",
    }
    write_jsonl(tmp_path / "videos.jsonl", [record])
    with pytest.raises(ValueError, match="playlist_index"):
        load_videos(tmp_path / "videos.jsonl")
