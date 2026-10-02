"""수집 원문과 식당 언급을 구분하는 데이터 모델."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class VideoRecord:
    video_id: str
    video_title: str
    video_url: str
    playlist_id: str
    playlist_index: int | None
    description: str


@dataclass(frozen=True, slots=True)
class RestaurantMention:
    mention_id: str
    name: str
    address: str
    map_url: str
    video_id: str
    video_title: str
    video_url: str
    playlist_id: str
    playlist_index: int | None
    order_in_video: int


@dataclass(frozen=True, slots=True)
class ParseReview:
    video_id: str
    playlist_id: str
    status: str
    reason: str
    raw_text: str


@dataclass(slots=True)
class ParseResult:
    mentions: list[RestaurantMention] = field(default_factory=list)
    reviews: list[ParseReview] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    video_id: str
    video_url: str
    playlist_index: int | None


@dataclass(frozen=True, slots=True)
class PlaylistInfo:
    playlist_id: str
    entries: list[PlaylistEntry]


@dataclass(frozen=True, slots=True)
class CollectionError:
    video_id: str
    playlist_id: str
    error: str
