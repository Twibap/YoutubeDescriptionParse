"""설명의 식당정보 구간에서 식당 언급과 검토할 원문을 추출한다."""

import re
from urllib.parse import urlsplit

from .models import ParseResult, ParseReview, RestaurantMention, VideoRecord

_MARKER = re.compile(r"\[\s*식당\s*정보\s*\]")
# 지도 주소의 괄호는 Markdown 링크를 닫는 괄호와 구분한다.
_PARENTHESIZED_URL_PART = r"\((?:[^()\s<>]|\([^()\s<>]*\))*\)"
_URL = re.compile(
    rf"\[[^\]\n]*\]\((?P<markdown>https?://(?:[^\s()<>]|{_PARENTHESIZED_URL_PART})+)\)"
    r"|<(?P<autolink>https?://[^\s>]+)>"
    r"|(?P<plain>https?://[^\s<>]+)",
    re.IGNORECASE,
)
_REGION = (
    r"서울(?:특별시)?|부산(?:광역시)?|대구(?:광역시)?|인천(?:광역시)?"
    r"|광주(?:광역시)?|대전(?:광역시)?|울산(?:광역시)?|세종(?:특별자치시)?"
    r"|경기(?:도)?|강원(?:도|특별자치도)?|충청북도|충북|충청남도|충남"
    r"|전라북도|전북(?:특별자치도)?|전라남도|전남|경상북도|경북"
    r"|경상남도|경남|제주(?:도|특별자치도)?"
)
_LOCATION_TOKEN = r"[가-힣0-9·]+(?:시|군|구|읍|면|동|리|대로|로|길|가)\b"
_ADDRESS_START = re.compile(
    rf"(?<!\S)(?:(?:{_REGION})(?=\s+{_LOCATION_TOKEN})"
    rf"|[가-힣0-9·]+(?:시|군|구|읍|면|동|리|가)(?=\s+(?:{_LOCATION_TOKEN}|\d))"
    r"|[가-힣0-9·]+(?:대로|로|길|동|리|가)(?=\s+\d))"
)
_ROAD_OR_LOT = re.compile(r"[가-힣0-9·]+(?:대로|로|길|동|리|가)\s+\d+(?:-\d+)?")
_METADATA = re.compile(
    r"(?:메뉴|영업\s*시간|휴무|연락처|전화|예약|가격|브레이크\s*타임|라스트\s*오더)"
    r"\s*[:：]|\b\d{2,3}-\d{3,4}-\d{4}\b"
)
_ADDRESS_PROSE = re.compile(
    r"(?:입니다|하세요|드립니다|문의|방문|구매|시청|구독|촬영|소개|영업|예약|메뉴)"
)
_NAME_PROSE = re.compile(r"(?:소개|설명)\s*문장|(?:입니다|소개합니다|추천합니다)(?=\s|[.!?。]|$)")
# 이 표식 이후는 지도 링크가 있어도 식당 후보로 해석하지 않는다.
_SECTION_END = re.compile(
    r"[📣📢📚📖🎧🎶🎵]"
    r"|\[(?=[^\]\n]*(?:광고|협찬|촬영|BGM|음악|메일|문의|도서|책|구매|정보))"
    r"[^\]\n]+\](?!\(https?://)"
    r"|(?:^|\n)[ \t]*(?:[-*#※▶●]+[ \t]*)?"
    r"(?:광고|협찬|촬영\s*정보|촬영|BGM|Music|음악|메일|이메일|비즈니스|문의"
    r"|도서|책|구매|인스타그램|Instagram|구독과\s*좋아요|Copyright|제작)"
    r"(?=\s|[:：\[]|$)"
    r"|(?<!\S)(?:BGM|촬영\s*정보|광고|협찬|메일|이메일|비즈니스\s*문의)\s*[:：]"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    r"|(?:^|\n)[ \t]*[-=_]{3,}[ \t]*(?=\n|$)",
    re.IGNORECASE,
)


def _review(video: VideoRecord, reason: str, raw_text: str) -> ParseReview:
    return ParseReview(
        video_id=video.video_id,
        playlist_id=video.playlist_id,
        status="needs_review",
        reason=reason,
        raw_text=raw_text.strip(),
    )


def _fields(candidate: str) -> tuple[str, str, str | None]:
    """확인 가능한 주소 근거가 있을 때만 이름과 주소를 분리한다."""
    candidate = candidate.strip()
    if not candidate:
        return "", "", "missing_fields"

    address_start = _ADDRESS_START.search(candidate)
    if address_start is None:
        return "", "", "missing_address"

    name = candidate[: address_start.start()].strip()
    address = candidate[address_start.start() :].strip()
    if not name:
        return "", "", "missing_name"
    street_matches = list(_ROAD_OR_LOT.finditer(address))
    if not street_matches:
        return "", "", "missing_address"
    if (
        len(name.splitlines()) != 1
        or len(name) > 100
        or _NAME_PROSE.search(name)
        or _METADATA.search(candidate)
        or len(street_matches) != 1
        or _ADDRESS_PROSE.search(address[street_matches[0].end() :])
    ):
        return "", "", "ambiguous_fields"
    return name, address, None


def _restaurant_part(block: str) -> str:
    """URL 및 Markdown 라벨 내부의 단어를 섹션 제목으로 오인하지 않는다."""
    links = list(_URL.finditer(block))
    for end in _SECTION_END.finditer(block):
        if not any(link.start() <= end.start() < link.end() for link in links):
            return block[: end.start()]
    return block


def _valid_map_url(map_url: str) -> bool:
    """구두점을 제거한 링크에 유효한 HTTP(S) 호스트가 남았는지 확인한다."""
    try:
        parsed = urlsplit(map_url)
        host = parsed.hostname
        # 비숫자 또는 범위를 벗어난 포트도 잘못된 링크로 남긴다.
        parsed.port
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc and host and host.strip("."))


def parse_description(video: VideoRecord) -> ParseResult:
    """URL을 식당 경계로 삼되 패턴이 끊긴 구간은 검토 대상으로 남긴다.

    이름이나 주소를 정규화하지 않는다. 같은 가게라도 영상과 등장 순서에
    따라 별도 언급을 만들며, 다음 식당정보 표식은 새 구간으로 처리한다.
    """
    result = ParseResult()
    markers = list(_MARKER.finditer(video.description))
    if not markers:
        reason = "missing_marker" if video.description.strip() else "empty_description"
        result.reviews.append(_review(video, reason, video.description))
        return result

    for index, marker in enumerate(markers):
        block_end = markers[index + 1].start() if index + 1 < len(markers) else None
        raw_block = video.description[marker.end() : block_end]
        block = _restaurant_part(raw_block)
        if not block.strip():
            result.reviews.append(_review(video, "empty_block", raw_block))
            continue

        cursor = 0
        broken = False
        for link in _URL.finditer(block):
            raw_candidate = block[cursor : link.end()]
            name, address, reason = _fields(block[cursor : link.start()])
            if reason is not None:
                result.reviews.append(_review(video, reason, raw_candidate))
                broken = True
                break

            map_url = link.group("markdown") or link.group("autolink") or link.group("plain")
            map_url = map_url.rstrip(".,!?;:。'\"}>]")
            # 일반 URL 뒤 닫는 괄호는 URL에 여는 괄호가 있을 때만 보존한다.
            while map_url.endswith(")") and map_url.count(")") > map_url.count("("):
                map_url = map_url[:-1]
            if not _valid_map_url(map_url):
                result.reviews.append(_review(video, "invalid_url", raw_candidate))
                broken = True
                break
            order = len(result.mentions) + 1
            result.mentions.append(
                RestaurantMention(
                    mention_id=f"{video.playlist_id}:{video.video_id}:{order}",
                    name=name,
                    address=address,
                    map_url=map_url,
                    video_id=video.video_id,
                    video_title=video.video_title,
                    video_url=video.video_url,
                    playlist_id=video.playlist_id,
                    playlist_index=video.playlist_index,
                    order_in_video=order,
                )
            )
            cursor = link.end()

        if not broken and block[cursor:].strip():
            result.reviews.append(_review(video, "missing_url", block[cursor:]))
    return result
