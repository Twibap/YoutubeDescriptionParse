import json
from dataclasses import asdict

import pytest

from youtube_description_parse import cli
from youtube_description_parse.models import VideoRecord
from youtube_description_parse.storage import write_jsonl


def test_parse_command_works_without_a_metadata_source(tmp_path, monkeypatch, capsys):
    def no_network():
        pytest.fail("오프라인 parse에서 수집기를 만들면 안 됩니다")

    monkeypatch.setattr(cli, "YoutubeMetadataSource", no_network)
    raw = tmp_path / "videos.jsonl"
    video = VideoRecord(
        "test0000001",
        "제목",
        "https://www.youtube.com/watch?v=test0000001",
        "test-playlist",
        1,
        "[식당정보]\n노무토모\n서울 송파구 백제고분로39길 22 1층\nhttps://naver.me/FoEN86nJ",
    )
    write_jsonl(raw, [asdict(video)])
    code = cli.main(["parse", "--input", str(raw), "--output-dir", str(tmp_path / "results")])
    assert code == 0
    assert "식당 언급 1건" in capsys.readouterr().out
    mention = json.loads(
        (tmp_path / "results/restaurant_mentions.jsonl").read_text(encoding="utf-8")
    )
    assert mention["name"] == "노무토모"


def test_missing_input_has_friendly_error(tmp_path, capsys):
    assert cli.main(["parse", "--input", str(tmp_path / "missing.jsonl")]) == 2
    assert "오류:" in capsys.readouterr().err


def test_collect_failure_status_is_nonzero(tmp_path, monkeypatch, capsys):
    from youtube_description_parse.pipeline import CollectionSummary

    monkeypatch.setattr(cli, "collect_playlist", lambda *a, **kw: CollectionSummary(1, 0, 1, 1, 0))
    assert cli.main(["collect", "--output-dir", str(tmp_path)]) == 1
    assert "collection_errors.jsonl" in capsys.readouterr().err


def test_collect_interrupt_status_is_130(tmp_path, monkeypatch, capsys):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "collect_playlist", interrupt)
    assert cli.main(["collect", "--output-dir", str(tmp_path)]) == 130
    assert "중단" in capsys.readouterr().err


@pytest.mark.parametrize("limit", ["0", "-1", "wrong"])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(SystemExit) as error:
        cli.main(["collect", "--limit", limit])
    assert error.value.code == 2
