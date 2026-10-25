"""Refresh the database from metadata and media in the selected folder."""

import json
import os
import re
from datetime import date, datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from accounts.models import Account
from videos.management.media_location import get_media_root
from videos.models import Category, Channel, Comment, Playlist, Video


UNUSED_INFO_FIELDS = set(
    """
    automatic_captions formats heatmap age_limit playable_in_embed live_status
    media_type _format_sort_fields subtitles epoch was_live is_live fulltitle
    display_id extractor_key extractor webpage_url_domain webpage_url_basename
    availability format format_id ext protocol language format_note
    filesize_approx tbr width dynamic_range fps height vbr vcodec aspect_ratio
    acodec abr asr audio_channels _type _version duration_string thumbnails
    requested_downloads requested_formats
    """.split()
)
UNUSED_COMMENT_FIELDS = {
    "_time_text",
    "author_is_uploader",
    "author_id",
    "author_is_verified",
    "is_favorited",
    "is_pinned",
}
NESTED_FIELD_ORDER = ("categories", "chapters", "comments")


def _date_string(value):
    if not value:
        return value
    text = str(value)
    for date_value, date_format in ((text[:10], None), (text[:8], "%Y%m%d")):
        try:
            parsed = (
                date.fromisoformat(date_value)
                if date_format is None
                else datetime.strptime(date_value, date_format).date()
            )
            return parsed.isoformat()
        except ValueError:
            continue
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    return value


def _timestamp_string(value):
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            value = int(value)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    return value


def _clean_info(data):
    for key in UNUSED_INFO_FIELDS:
        data.pop(key, None)

    playlist_title = data.get("playlist_title")
    if isinstance(playlist_title, str) and playlist_title.rstrip().lower().endswith(" - videos"):
        for key in tuple(data):
            if key == "playlist" or key.startswith("playlist_"):
                data.pop(key, None)

    for key in ("upload_timestamp", "release_timestamp", "timestamp"):
        if key in data:
            data[key] = _timestamp_string(data[key])

    for date_key, timestamp_key in (
        ("upload_date", "upload_timestamp"),
        ("release_date", "release_timestamp"),
        ("modified_date", "release_timestamp"),
    ):
        if not data.get(date_key) and data.get(timestamp_key):
            data[date_key] = str(data[timestamp_key])[:10]
        if date_key in data:
            data[date_key] = _date_string(data[date_key])

    for comment in data.get("comments", []):
        if isinstance(comment, dict):
            for key in UNUSED_COMMENT_FIELDS:
                comment.pop(key, None)
            if "timestamp" in comment:
                comment["timestamp"] = _timestamp_string(comment["timestamp"])

    scalars = {key: value for key, value in data.items() if not isinstance(value, (list, dict))}
    nested = {
        key: data[key]
        for key in NESTED_FIELD_ORDER
        if isinstance(data.get(key), (list, dict))
    }
    nested.update(
        {
            key: value
            for key, value in data.items()
            if isinstance(value, (list, dict)) and key not in nested
        }
    )
    return {**scalars, **nested}


def clean_media_metadata(media_root):
    cleaned = skipped = 0
    for path in sorted(media_root.rglob("*.info.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        if not isinstance(data, dict):
            skipped += 1
            continue

        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(_clean_info(data), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(path)
        cleaned += 1
    return {"cleaned": cleaned, "skipped": skipped}


def safe_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def metadata_files(media_root):
    return sorted(media_root.rglob("*.info.json"))


def local_file(info_path, suffixes):
    stem = info_path.name[: -len(".info.json")]
    for suffix in suffixes:
        candidate = info_path.with_name(stem + suffix)
        if candidate.is_file():
            return candidate
    return None


def relative_media_path(path):
    media_root = get_media_root()
    return path.relative_to(media_root).as_posix() if path and media_root else ""


def upload_day(value):
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
        try:
            return datetime.strptime(str(value)[:8], "%Y%m%d").date()
        except ValueError:
            pass
    return date.today()


class Command(BaseCommand):
    help = "Refresh the database from metadata in the selected media folder."

    def handle(self, *args, **options):
        media_root = get_media_root()
        if not media_root or not media_root.is_dir():
            raise CommandError("Choose an existing media folder on the import page first.")
        if not os.access(media_root, os.R_OK | os.W_OK):
            raise CommandError("YourTube needs read and write access to the selected folder.")

        try:
            cleanup = clean_media_metadata(media_root)
        except OSError as error:
            raise CommandError(f"Could not clean media metadata: {error}") from error

        infos = metadata_files(media_root)
        if not infos:
            raise CommandError(f"No .info.json metadata files found under {media_root}.")
        result = self.import_metadata(infos)
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleaned {cleanup['cleaned']} metadata files "
                f"({cleanup['skipped']} skipped); imported {result['videos']} videos, "
                f"{result['playlists']} playlists, {result['channels']} channels, "
                f"and {result['comments']} comments; "
                f"removed {result['removed_videos']} stale videos."
            )
        )

    @transaction.atomic
    def import_metadata(self, paths):
        User = get_user_model()
        parsed = []
        for path in paths:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(item, dict) and item.get("duration") is not None and item.get("webpage_url"):
                parsed.append((path, item))

        channels, playlist_by_url, video_by_url = set(), {}, {}
        for path, item in parsed:
            uploader = item.get("uploader_id") or item.get("channel_id") or item.get("uploader") or item.get("channel") or "unknown-channel"
            username = re.sub(r"[^\w.@+-]", "_", str(uploader).lstrip("@"))[:150] or "youtube-user"
            owner, _ = User.objects.get_or_create(username=username)
            Account.objects.get_or_create(user=owner)
            channel_url = item.get("channel_url") or item.get("uploader_url") or ""
            channel_key = channel_url or f"owner:{owner.pk}"
            if not channel_url:
                channel_url = f"https://www.youtube.com/@{username}"
            channel, _ = Channel.objects.update_or_create(
                owner=owner,
                defaults={"name": (item.get("channel") or item.get("uploader") or username)[:200], "follower_count": safe_int(item.get("channel_follower_count")), "is_verified": item.get("channel_is_verified") is True, "url": channel_url},
            )
            channels.add(channel_key)

            playlist_url = item.get("playlist_webpage_url")
            if playlist_url and playlist_url not in playlist_by_url:
                playlist_title = (item.get("playlist_title") or item.get("playlist") or item.get("title") or "Playlist")[:200]
                playlist, _ = Playlist.objects.update_or_create(
                    url=playlist_url,
                    defaults={
                        "name": playlist_title,
                        "description": item.get("playlist_description") or "",
                        "modified_date": upload_day(item.get("release_date") or item.get("upload_date")),
                        "view_count": safe_int(item.get("playlist_view_count")),
                        "video_count": safe_int(item.get("playlist_count") or item.get("n_entries")),
                        "thumbnail_loc": relative_media_path(local_file(path, (".jpg", ".jpeg", ".png", ".webp"))),
                        "creator": owner,
                    },
                )
                playlist_by_url[playlist_url] = playlist
        for path, item in parsed:
            uploader = item.get("uploader_id") or item.get("channel_id") or item.get("uploader") or item.get("channel") or "unknown-channel"
            username = re.sub(r"[^\w.@+-]", "_", str(uploader).lstrip("@"))[:150] or "youtube-user"
            owner = User.objects.get(username=username)
            channel = Channel.objects.get(owner=owner)
            video_url = item["webpage_url"]
            video_path = local_file(path, (".mp4", ".webm", ".mkv", ".mov", ".m4v"))
            thumb_path = local_file(path, (".jpg", ".jpeg", ".png", ".webp"))
            playlist_url = item.get("playlist_webpage_url")
            playlist = playlist_by_url.get(playlist_url)
            fields = {
                "title": (item.get("title") or video_url)[:200],
                "video_loc": relative_media_path(video_path),
                "thumbnail_loc": relative_media_path(thumb_path),
                "thumbnail_url": item.get("thumbnail") or "https://www.youtube.com/img/desktop/yt_1200.png",
                "description": item.get("description") or "",
                "duration": safe_int(item.get("duration")),
                "view_count": safe_int(item.get("view_count")),
                "video_url": video_url,
                "comment_count": safe_int(item.get("comment_count")),
                "like_count": safe_int(item.get("like_count")),
                "channel": channel,
                "playlist": playlist,
                "upload_date": upload_day(item.get("upload_date")),
                "position_in_playlist": safe_int(item.get("playlist_index"), 0) or None,
                "resolution": item.get("resolution") or "",
            }
            video, _ = Video.objects.update_or_create(video_url=video_url, defaults=fields)
            video.categories.set([Category.objects.get_or_create(name=name[:100])[0] for name in item.get("categories") or [] if name])
            video_by_url[video_url] = video
        comments_count = 0
        for path, item in parsed:
            video = video_by_url.get(item["webpage_url"])
            if not video:
                continue
            comment_map = {}
            for comment_data in item.get("comments") or []:
                source_id = str(comment_data.get("id") or "")
                if not source_id:
                    continue
                author_name = re.sub(r"[^\w.@+-]", "_", str(comment_data.get("author") or "youtube-user"))[:150]
                author, _ = User.objects.get_or_create(username=author_name or "youtube-user")
                Account.objects.get_or_create(user=author)
                stamp = comment_data.get("timestamp")
                when = datetime.fromtimestamp(stamp, timezone.utc) if isinstance(stamp, (int, float)) else parse_datetime(str(stamp or ""))
                when = when or datetime.now(timezone.utc)
                comment, _ = Comment.objects.update_or_create(
                    video=video,
                    source_id=source_id,
                    defaults={"author": author, "text": comment_data.get("text") or "", "like_count": safe_int(comment_data.get("like_count")), "timestamp": when},
                )
                comment_map[source_id] = comment
                comments_count += 1
            for comment_data in item.get("comments") or []:
                source_id = str(comment_data.get("id") or "")
                parent_id = str(comment_data.get("parent") or "")
                if source_id in comment_map:
                    comment_map[source_id].parent = comment_map.get(parent_id)
                    comment_map[source_id].save(update_fields=["parent"])
        if not video_by_url:
            raise CommandError("No valid videos were generated from the selected folder; database records were left unchanged.")
        stale_videos = Video.objects.exclude(video_url__in=video_by_url)
        removed_count = stale_videos.count()
        stale_videos.delete()
        return {"videos": len(video_by_url), "playlists": len(playlist_by_url), "channels": len(channels), "comments": comments_count, "removed_videos": removed_count}
