"""식당 블록 경계와 애매한 원문의 검토 분리를 검증한다."""

import pytest

from youtube_description_parse.models import VideoRecord
from youtube_description_parse.parser import parse_description


def video(description: str) -> VideoRecord:
    return VideoRecord(
        video_id="video123456",
        video_title="여러 식당을 소개하는 영상",
        video_url="https://www.youtube.com/watch?v=video123456",
        playlist_id="PL_example",
        playlist_index=7,
        description=description,
    )


def test_single_line_real_description_stops_at_book_advertisement():
    result = parse_description(
        video(
            "[식당정보] 노무토모 서울 송파구 백제고분로39길 22 1층 "
            "https://naver.me/FoEN86nJ 📣[김사원세끼의 노포 투어]는 "
            "서울 맛집이 담긴 책입니다 https://bit.ly/book "
            "서울 서점 서울 종로구 종로 1 https://example.com/book"
        )
    )
    assert [(item.name, item.address, item.map_url) for item in result.mentions] == [
        ("노무토모", "서울 송파구 백제고분로39길 22 1층", "https://naver.me/FoEN86nJ")
    ]
    assert result.reviews == []


def test_multiple_restaurants_in_one_block_and_one_line():
    result = parse_description(
        video(
            "[식당정보] 첫집 서울 종로구 종로 10 https://naver.me/one "
            "둘째집 경기 수원시 팔달구 정조로 20 http://example.com/two"
        )
    )
    assert [item.name for item in result.mentions] == ["첫집", "둘째집"]
    assert [item.order_in_video for item in result.mentions] == [1, 2]
    assert result.reviews == []


def test_repeated_markers_resume_after_non_restaurant_section():
    result = parse_description(
        video(
            "영상 소개\n[식당정보]\n첫집\n서울 종로구 종로 10\nhttps://naver.me/one"
            "\n[BGM]\n서울 음악사 서울 종로구 종로 20 https://example.com/music"
            "\n[식당정보]\n둘째집\n부산 중구 중앙대로 30\nhttps://naver.me/two"
        )
    )
    assert [item.name for item in result.mentions] == ["첫집", "둘째집"]
    assert [item.mention_id for item in result.mentions] == [
        "PL_example:video123456:1",
        "PL_example:video123456:2",
    ]
    assert result.mentions[1].playlist_index == 7
    assert result.mentions[1].video_title == "여러 식당을 소개하는 영상"


@pytest.mark.parametrize(
    "url_text",
    [
        "https://naver.me/abc",
        "[https://naver.me/abc](https://naver.me/abc)",
        "[지도](https://naver.me/abc)",
        "[촬영정보 지도](https://naver.me/abc)",
        "<https://naver.me/abc>",
    ],
)
def test_plain_and_markdown_map_links(url_text):
    result = parse_description(video(f"[식당정보]\n맛집\n서울 종로구 종로 10\n{url_text}"))
    assert len(result.mentions) == 1
    assert result.mentions[0].map_url == "https://naver.me/abc"
    assert result.mentions[0].address == "서울 종로구 종로 10"
    assert result.reviews == []


@pytest.mark.parametrize(
    "url_text",
    [
        "https://example.com/maps/foo_(bar)",
        "[지도](https://example.com/maps/foo_(bar))",
        "<https://example.com/maps/foo_(bar)>",
    ],
)
def test_balanced_url_parentheses_are_preserved(url_text):
    result = parse_description(video(f"[식당정보] 맛집 서울 종로구 종로 10 {url_text}"))
    assert [item.map_url for item in result.mentions] == ["https://example.com/maps/foo_(bar)"]
    assert result.reviews == []


def test_nested_parentheses_in_markdown_url_are_preserved():
    result = parse_description(
        video(
            "[식당정보] 맛집 서울 종로구 종로 10 [지도](https://example.com/maps/foo_(bar_(baz)))"
        )
    )
    assert result.mentions[0].map_url == "https://example.com/maps/foo_(bar_(baz))"
    assert result.reviews == []


@pytest.mark.parametrize(
    "url_text",
    [
        "https://.",
        "https://)",
        "https:///map",
        "https://:80/map",
        "https://./map",
        "https://[invalid]/map",
        "https://example.com:invalid/map",
        "[지도](https://.)",
        "<https://.>",
    ],
)
def test_invalid_map_url_requires_review_and_stops_until_next_marker(url_text):
    first_candidate = f"맛집 서울 종로구 종로 10 {url_text}"
    result = parse_description(
        video(
            f"[식당정보] {first_candidate}\n"
            "끊긴구간 서울 종로구 종로 20 https://naver.me/skipped\n"
            "[식당정보] 다음집 서울 종로구 종로 30 https://naver.me/valid"
        )
    )
    assert [item.name for item in result.mentions] == ["다음집"]
    assert len(result.reviews) == 1
    assert result.reviews[0].reason == "invalid_url"
    assert result.reviews[0].raw_text == first_candidate


@pytest.mark.parametrize(
    "url_text",
    ["http://example.com:8080/map", "HTTPS://naver.me/abc", "https://127.0.0.1/map"],
)
def test_valid_http_links_are_preserved_after_host_validation(url_text):
    result = parse_description(video(f"[식당정보] 맛집 서울 종로구 종로 10 {url_text}"))
    assert [item.map_url for item in result.mentions] == [url_text]
    assert result.reviews == []


def test_name_and_address_preserve_internal_whitespace():
    result = parse_description(
        video(
            "[식당정보]\n  오래된  국수집  \n  서울특별시  종로구\n종로 10  1층  \nhttps://naver.me/a"
        )
    )
    assert result.mentions[0].name == "오래된  국수집"
    assert result.mentions[0].address == "서울특별시  종로구\n종로 10  1층"


@pytest.mark.parametrize(
    "address",
    [
        "서울 송파구 백제고분로39길 22 1층",
        "경기도 성남시 분당구 판교역로 100",
        "부산광역시 중구 중앙대로 10",
        "제주특별자치도 제주시 애월읍 애월리 123-4",
        "강원특별자치도 춘천시 중앙로 10",
        "전북특별자치도 전주시 완산구 전동 123",
        "수원시 팔달구 정조로 20",
        "송파구 석촌동 123-4",
        "테헤란로 123",
        "서울 종로구 종로3가 10",
    ],
)
def test_road_lot_and_shortened_addresses(address):
    result = parse_description(video(f"[식당정보] 맛집 {address} https://naver.me/a"))
    assert [(item.name, item.address) for item in result.mentions] == [("맛집", address)]


def test_name_starting_with_city_word_is_not_an_address():
    result = parse_description(
        video("[식당정보] 서울 국수집 서울 종로구 종로 10 https://naver.me/a")
    )
    assert result.mentions[0].name == "서울 국수집"


@pytest.mark.parametrize(
    "name_text",
    ["소개 문장 맛집", "설명 문장 맛집", "맛집입니다", "오늘 소개합니다 맛집", "추천합니다 맛집"],
)
def test_explicit_introductory_prose_is_not_confirmed_as_a_name(name_text):
    candidate = f"{name_text} 서울 종로구 종로 10 https://naver.me/a"
    result = parse_description(video(f"[식당정보] {candidate}"))
    assert result.mentions == []
    assert len(result.reviews) == 1
    assert result.reviews[0].reason == "ambiguous_fields"
    assert result.reviews[0].raw_text == candidate


def test_name_containing_introductory_word_is_still_supported():
    result = parse_description(video("[식당정보] 소개식당 서울 종로구 종로 10 https://naver.me/a"))
    assert [item.name for item in result.mentions] == ["소개식당"]
    assert result.reviews == []


@pytest.mark.parametrize(
    "address", ["서교동 와우산로 10", "애월리 애월로 20", "명륜3가 성균관로 30"]
)
def test_neighborhood_followed_by_street_starts_the_shortened_address(address):
    result = parse_description(video(f"[식당정보] 맛집 {address} https://naver.me/a"))
    assert [(item.name, item.address) for item in result.mentions] == [("맛집", address)]
    assert result.reviews == []


@pytest.mark.parametrize(
    "section",
    [
        "[광고]",
        "[촬영정보]",
        "[신발정보]",
        "[BGM]",
        "BGM :",
        "촬영 정보:",
        "메일: person@example.com",
        "비즈니스 문의:",
        "책 구매:",
        "---",
    ],
)
def test_metadata_section_does_not_collect_later_address_and_url(section):
    result = parse_description(
        video(
            "[식당정보]\n맛집\n서울 종로구 종로 10\nhttps://naver.me/a\n"
            f"{section}\n광고회사\n서울 종로구 종로 20\nhttps://example.com/advert"
        )
    )
    assert [item.name for item in result.mentions] == ["맛집"]
    assert result.reviews == []


def test_duplicate_restaurant_mentions_are_not_merged():
    result = parse_description(video("[식당정보] 가게 서울 종로구 종로 10 https://naver.me/a " * 2))
    assert len(result.mentions) == 2
    assert result.mentions[0].mention_id != result.mentions[1].mention_id


@pytest.mark.parametrize(
    ("description", "reason"),
    [
        ("", "empty_description"),
        ("맛집 서울 종로구 종로 10 https://naver.me/a", "missing_marker"),
        ("[식당정보]", "empty_block"),
        ("[식당정보] https://naver.me/a", "missing_fields"),
        ("[식당정보] 서울 종로구 종로 10 https://naver.me/a", "missing_name"),
        ("[식당정보] 맛집 위치 미상 https://naver.me/a", "missing_address"),
        ("[식당정보] 맛집 서울 강남구 https://naver.me/a", "missing_address"),
        ("[식당정보] 맛집 서울 종로구 종로 10", "missing_url"),
        (
            "[식당정보] 소개 문장\n맛집\n서울 종로구 종로 10 https://naver.me/a",
            "ambiguous_fields",
        ),
        (
            "[식당정보] 맛집 서울 종로구 종로 10 메뉴: 국수 https://naver.me/a",
            "ambiguous_fields",
        ),
        (
            "[식당정보] 맛집 서울 종로구 종로 10 제가 방문한 곳입니다 https://naver.me/a",
            "ambiguous_fields",
        ),
        (
            "[식당정보] 첫집 서울 종로구 종로 10 둘째집 서울 종로구 종로 20 https://naver.me/a",
            "ambiguous_fields",
        ),
    ],
)
def test_uncertain_data_is_preserved_for_review(description, reason):
    result = parse_description(video(description))
    assert result.mentions == []
    assert len(result.reviews) == 1
    review = result.reviews[0]
    assert review.status == "needs_review"
    assert review.reason == reason
    assert review.video_id == "video123456"
    assert review.playlist_id == "PL_example"
    assert review.raw_text in description


def test_incomplete_last_restaurant_is_kept_separately():
    result = parse_description(
        video(
            "[식당정보] 첫집 서울 종로구 종로 10 https://naver.me/a\n마지막집\n서울 종로구 종로 20"
        )
    )
    assert [item.name for item in result.mentions] == ["첫집"]
    assert result.reviews[0].reason == "missing_url"
    assert result.reviews[0].raw_text == "마지막집\n서울 종로구 종로 20"


def test_broken_pattern_stops_until_next_marker():
    result = parse_description(
        video(
            "[식당정보] 첫집 서울 종로구 종로 10 https://naver.me/a\n"
            "관련 상품 https://example.com/shop\n"
            "상품회사 서울 종로구 종로 20 https://example.com/company\n"
            "[식당정보] 다음집 서울 종로구 종로 30 https://naver.me/b"
        )
    )
    assert [item.name for item in result.mentions] == ["첫집", "다음집"]
    assert len(result.reviews) == 1
    assert result.reviews[0].reason == "missing_address"
    assert result.reviews[0].raw_text == "관련 상품 https://example.com/shop"


def test_email_inline_ends_restaurant_block():
    result = parse_description(
        video(
            "[식당정보] 맛집 서울 종로구 종로 10 https://naver.me/a "
            "person@example.com 홍보회사 서울 종로구 종로 20 https://example.com/mail"
        )
    )
    assert [item.name for item in result.mentions] == ["맛집"]


def test_spaces_in_marker_and_windows_newlines():
    result = parse_description(
        video("[ 식당 정보 ]\r\n가게\r\n서울 종로구 종로 10\r\nhttps://naver.me/a")
    )
    assert [item.name for item in result.mentions] == ["가게"]
