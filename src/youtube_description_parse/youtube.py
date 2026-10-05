"""영상 파일 없이 YouTube 재생목록·채널의 일반 영상과 설명을 가져온다."""

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from .models import PlaylistEntry, PlaylistInfo, VideoRecord

DEFAULT_PLAYLIST_ID = "PLCNYoGrzVJuUWTlwZ2CH9nfQF08959pIj"

_PLAYLIST_ID = re.compile(r"(?:(?:PL|UU|FL|LL|RD|OL|UL|PU)[A-Za-z0-9_-]{10,100}|WL|LL)\Z")
_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
_CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
_HANDLE = re.compile(r"@[\w.-]{1,100}\Z")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


def normalize_playlist(playlist: str) -> tuple[str, str]:
    """YouTube URL 또는 재생목록 ID를 ID와 정규 URL로 변환한다."""
    if not isinstance(playlist, str) or not playlist.strip():
        raise ValueError("YouTube 재생목록 URL 또는 ID가 필요합니다.")

    value = playlist.strip()
    if _PLAYLIST_ID.fullmatch(value):
        playlist_id = value
    else:
        if value.startswith(tuple(f"{host}/" for host in _YOUTUBE_HOSTS)):
            value = f"https://{value}"
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"https", "http"}
            or parsed.hostname not in _YOUTUBE_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.netloc.lower() != parsed.hostname
            or parsed.path.rstrip("/") not in {"/playlist", "/watch"}
        ):
            raise ValueError("YouTube 재생목록 URL 또는 올바른 재생목록 ID를 입력하세요.")

        lists = parse_qs(parsed.query, keep_blank_values=True).get("list", [])
        if len(lists) != 1 or not _PLAYLIST_ID.fullmatch(lists[0]):
            raise ValueError("URL에 올바른 YouTube 재생목록 list 값이 필요합니다.")
        playlist_id = lists[0]

    return playlist_id, f"https://www.youtube.com/playlist?list={playlist_id}"


def normalize_channel(channel: str) -> tuple[str | None, str]:
    """채널 주소를 일반 동영상 탭으로 고정한다. 핸들은 API 응답에서 UC ID를 얻는다."""
    if not isinstance(channel, str) or not channel.strip():
        raise ValueError("YouTube 재생목록 또는 채널 주소가 필요합니다.")
    value = channel.strip()
    if value.startswith("@"):
        value = f"https://www.youtube.com/{value}"
    elif value.startswith(tuple(f"{host}/" for host in _YOUTUBE_HOSTS)):
        value = f"https://{value}"
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"https", "http"}
        or parsed.hostname not in _YOUTUBE_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.netloc.lower() != parsed.hostname
    ):
        raise ValueError("YouTube 재생목록 또는 올바른 채널 주소를 입력하세요.")
    parts = unquote(parsed.path).strip("/").split("/")
    if parts and _HANDLE.fullmatch(parts[0]) and parts[1:] in ([], ["videos"]):
        return None, f"https://www.youtube.com/{quote(parts[0], safe='@._-')}/videos"
    if (
        len(parts) in {2, 3}
        and parts[0] == "channel"
        and _CHANNEL_ID.fullmatch(parts[1])
        and parts[2:] in ([], ["videos"])
    ):
        return parts[1], f"https://www.youtube.com/channel/{parts[1]}/videos"
    raise ValueError("일반 동영상 수집에는 @채널 또는 /channel/UC…/videos 주소를 입력하세요.")


def _collection_id(value: str) -> str:
    if isinstance(value, str) and value.startswith("channel:"):
        if not _CHANNEL_ID.fullmatch(value.removeprefix("channel:")):
            raise ValueError("채널 수집 출처의 UC ID가 올바르지 않습니다.")
        return value
    return normalize_playlist(value)[0]


def _response_channel_id(metadata: Mapping[str, Any], expected: str | None) -> str:
    channel_id = metadata.get("channel_id")
    metadata_id = metadata.get("id")
    if channel_id is None:
        channel_id = metadata_id
    if not isinstance(channel_id, str) or not _CHANNEL_ID.fullmatch(channel_id):
        raise ValueError("채널 메타데이터에 올바른 UC ID가 없습니다.")
    if isinstance(metadata_id, str) and _CHANNEL_ID.fullmatch(metadata_id):
        if metadata_id != channel_id:
            raise ValueError("채널 메타데이터의 id와 channel_id가 다릅니다.")
    if expected is not None and channel_id != expected:
        raise ValueError("요청한 채널과 응답의 채널 ID가 다릅니다.")
    return f"channel:{channel_id}"


def _required_text(metadata: Mapping[str, Any], field: str, context: str) -> str:
    value = metadata.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} 메타데이터에 올바른 {field} 값이 없습니다.")
    return value


def _video_id(metadata: Mapping[str, Any]) -> str:
    video_id = _required_text(metadata, "id", "영상")
    if not _VIDEO_ID.fullmatch(video_id):
        raise ValueError("영상 메타데이터의 YouTube ID가 올바르지 않습니다.")
    return video_id


class YoutubeMetadataSource:
    """yt-dlp를 필요한 순간에만 불러오는 메타데이터 수집기."""

    def __init__(self, *, youtube_dl_factory: Callable[[dict[str, Any]], Any] | None = None):
        self._youtube_dl_factory = youtube_dl_factory

    def _client(self, *, extract_flat: bool, noplaylist: bool):
        factory = self._youtube_dl_factory
        if factory is None:
            try:
                from yt_dlp import YoutubeDL
            except ModuleNotFoundError as error:
                raise RuntimeError(
                    "YouTube 수집에는 yt-dlp가 필요합니다. uv sync를 실행하세요."
                ) from error
            factory = YoutubeDL

        # TLS 인증서 검사와 시스템 프록시 설정은 yt-dlp의 기본 동작을 유지한다.
        return factory(
            {
                "extract_flat": extract_flat,
                "noplaylist": noplaylist,
                "skip_download": True,
                "ignore_no_formats_error": False,
                "ignoreerrors": False,
                "quiet": True,
                "noprogress": True,
                "retries": 3,
                "extractor_retries": 3,
                "socket_timeout": 30,
            }
        )

    def iter_playlist(self, playlist: str) -> PlaylistInfo:
        """재생목록 또는 채널 일반 동영상 탭을 끝까지 열거한다."""
        is_channel = False
        try:
            playlist_id, playlist_url = normalize_playlist(playlist)
        except ValueError:
            playlist_id, playlist_url = normalize_channel(playlist)
            is_channel = True
        client_context = self._client(extract_flat=True, noplaylist=False)
        try:
            with client_context as client:
                metadata = client.extract_info(playlist_url, download=False)
        except Exception as error:
            label = "채널" if is_channel else "재생목록"
            raise ValueError(f"{label} 메타데이터를 가져오지 못했습니다: {error}") from error

        if not isinstance(metadata, Mapping) or metadata.get("_type") != "playlist":
            raise ValueError("YouTube에서 올바른 재생목록 메타데이터를 받지 못했습니다.")
        if is_channel:
            playlist_id = _response_channel_id(metadata, playlist_id)
        elif metadata.get("id") != playlist_id:
            raise ValueError("요청한 재생목록과 응답의 재생목록 ID가 다릅니다.")

        raw_entries = metadata.get("entries")
        if not isinstance(raw_entries, Iterable) or isinstance(raw_entries, (str, bytes, Mapping)):
            raise ValueError("재생목록 메타데이터에 올바른 영상 목록이 없습니다.")

        entries = []
        for position, metadata_entry in enumerate(raw_entries, start=1):
            if not isinstance(metadata_entry, Mapping):
                raise ValueError(f"재생목록 {position}번째 영상 메타데이터가 올바르지 않습니다.")
            video_id = _video_id(metadata_entry)
            index = metadata_entry.get("playlist_index", position)
            if index is None:
                index = position
            if isinstance(index, bool) or not isinstance(index, int) or index < 1:
                raise ValueError("재생목록 영상의 playlist_index가 올바르지 않습니다.")
            video_url = metadata_entry.get("webpage_url") or metadata_entry.get("url")
            if not isinstance(video_url, str) or not video_url.startswith(("https://", "http://")):
                video_url = f"https://www.youtube.com/watch?v={video_id}"
            entries.append(PlaylistEntry(video_id, video_url, index))

        return PlaylistInfo(playlist_id, entries)

    def get_video(self, entry: PlaylistEntry, playlist_id: str) -> VideoRecord:
        """개별 영상의 원문 설명을 조회한다. 추출 오류는 호출자가 기록한다."""
        playlist_id = _collection_id(playlist_id)
        if not isinstance(entry.video_id, str) or not _VIDEO_ID.fullmatch(entry.video_id):
            raise ValueError("올바른 YouTube 영상 ID가 필요합니다.")
        # entry URL의 list 파라미터와 무관하게 항상 영상 한 개만 추출한다.
        video_url = f"https://www.youtube.com/watch?v={entry.video_id}"
        with self._client(extract_flat=False, noplaylist=True) as client:
            # 형식 선택은 생략하되 비공개·삭제 등 추출 단계의 접근 오류는 유지한다.
            metadata = client.extract_info(video_url, download=False, process=False)

        if not isinstance(metadata, Mapping) or metadata.get("_type", "video") != "video":
            raise ValueError("YouTube에서 올바른 영상 메타데이터를 받지 못했습니다.")
        video_id = _video_id(metadata)
        if video_id != entry.video_id:
            raise ValueError("요청한 영상과 응답의 영상 ID가 다릅니다.")
        title = _required_text(metadata, "title", "영상")
        description = metadata.get("description")
        if description is None:
            description = ""
        if not isinstance(description, str):
            raise ValueError("영상 메타데이터의 description은 문자열이어야 합니다.")
        webpage_url = metadata.get("webpage_url", video_url)
        if not isinstance(webpage_url, str) or not webpage_url.strip():
            raise ValueError("영상 메타데이터의 webpage_url이 올바르지 않습니다.")
        parsed_url = urlparse(webpage_url)
        if parsed_url.scheme not in {"https", "http"} or not parsed_url.hostname:
            raise ValueError("영상 메타데이터의 webpage_url은 올바른 웹 주소여야 합니다.")

        return VideoRecord(
            video_id=video_id,
            video_title=title,
            video_url=webpage_url,
            playlist_id=playlist_id,
            playlist_index=entry.playlist_index,
            description=description,
        )
