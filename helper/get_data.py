"""Build Django fixture files from yt-dlp metadata in media/."""

import json
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ROOT = PROJECT_ROOT / "media"
DATA_ROOT = PROJECT_ROOT / "helper" / "data"
PASSWORD = "pbkdf2_sha256$1500000$YOno61gdBqm7VlMFeD5BWx$RvuRw2OCywP1stm3HNYJLDfNlKoK3ZyE2kBz/Nd9Hrc="


def username(value):
    return value.removeprefix("@") if value else value


def load_metadata():
    items = []
    for path in sorted(MEDIA_ROOT.rglob("*.info.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            print(f"Skipped invalid JSON: {path}")
            continue
        if isinstance(item, dict):
            items.append((path, item))
    return items


def fixture(model, pk, fields):
    return {"model": model, "pk": pk, "fields": fields}


def normalize_timestamp(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return normalize_timestamp(int(value))
        return value or None
    return None


def write_json(name, records):
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / name).write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def build_fixtures():
    items = load_metadata()
    users = {}
    profiles = {}
    for _, item in items:
        owner = username(item.get("uploader_id"))
        if owner:
            users.setdefault(owner, PASSWORD)
        for comment in item.get("comments") or []:
            author = username(comment.get("author"))
            if author:
                users.setdefault(author, PASSWORD)
                if comment.get("author_thumbnail"):
                    profiles.setdefault(author, comment["author_thumbnail"])

    user_ids = {name: pk for pk, name in enumerate(sorted(users), 1)}
    write_json("users.json", [
        fixture("auth.user", user_ids[name], {"username": name, "password": PASSWORD})
        for name in sorted(users)
    ])
    write_json("users_profiles.json", [
        fixture("accounts.account", pk, {"user": user_ids[name], "image_url": profiles[name]})
        for pk, name in enumerate(sorted(profiles), 1)
    ])

    channels, playlists = {}, {}
    for path, item in items:
        owner = username(item.get("uploader_id"))
        if owner not in user_ids:
            continue
        if item.get("duration") is not None and item.get("webpage_url"):
            channel_url = item.get("channel_url") or item.get("uploader_url")
            if channel_url:
                channels.setdefault(owner, {
                    "name": item.get("channel") or item.get("uploader") or owner,
                    "follower_count": item.get("channel_follower_count") or 0,
                    "is_verified": item.get("channel_is_verified") is True,
                    "url": channel_url,
                    "owner": user_ids[owner],
                })
        playlist_url = item.get("webpage_url")
        if item.get("modified_date") and playlist_url:
            playlists.setdefault(playlist_url, {
                "name": item.get("title") or "Playlist",
                "description": item.get("description") or "",
                "modified_date": item["modified_date"],
                "view_count": item.get("view_count") or 0,
                "video_count": item.get("playlist_count") or item.get("n_entries") or 0,
                "thumbnail_loc": item.get("thumbnail_loc") or "",
                "url": playlist_url,
                "creator": user_ids[owner],
            })

    channel_ids = {owner: pk for pk, owner in enumerate(sorted(channels), 1)}
    playlist_ids = {url: pk for pk, url in enumerate(sorted(playlists), 1)}
    write_json("channels.json", [
        fixture("videos.channel", channel_ids[owner], fields)
        for owner, fields in sorted(channels.items())
    ])
    write_json("playlists.json", [
        fixture("videos.playlist", playlist_ids[url], fields)
        for url, fields in sorted(playlists.items())
    ])

    posts = {}
    for path, item in items:
        if item.get("duration") is not None and item.get("webpage_url"):
            posts.setdefault(item["webpage_url"], (path, item))
    category_names = sorted({name for _, item in posts.values() for name in item.get("categories") or []})
    tag_names = sorted({name for _, item in posts.values() for name in item.get("tags") or []})
    category_ids = {name: pk for pk, name in enumerate(category_names, 1)}
    tag_ids = {name: pk for pk, name in enumerate(tag_names, 1)}
    video_records = [
        fixture("videos.category", category_ids[name], {"name": name}) for name in category_names
    ] + [
        fixture("videos.tag", tag_ids[name], {"name": name}) for name in tag_names
    ]
    video_ids = {}
    for video_url, (path, item) in sorted(posts.items()):
        owner = username(item.get("uploader_id"))
        if owner not in user_ids or owner not in channel_ids:
            continue
        stem = path.name.removesuffix(".info.json")
        video_path = next((path.with_name(stem + ext) for ext in (".mp4", ".webm", ".mkv", ".mov", ".m4v")
                           if path.with_name(stem + ext).is_file()), None)
        thumbnail_path = next((path.with_name(stem + ext) for ext in (".jpg", ".jpeg", ".png", ".webp")
                               if path.with_name(stem + ext).is_file()), None)
        playlist_url = item.get("playlist_webpage_url")
        fields = {
            "title": item.get("title") or video_url,
            "video_loc": video_path.relative_to(PROJECT_ROOT).as_posix() if video_path else "",
            "thumbnail_loc": thumbnail_path.relative_to(PROJECT_ROOT).as_posix() if thumbnail_path else "",
            "thumbnail_url": item.get("thumbnail") or "https://www.youtube.com/img/desktop/yt_1200.png",
            "description": item.get("description") or "",
            "duration": item["duration"],
            "view_count": item.get("view_count") or 0,
            "video_url": video_url,
            "comment_count": item.get("comment_count") or 0,
            "like_count": item.get("like_count") or 0,
            "channel": channel_ids[owner],
            "playlist": playlist_ids.get(playlist_url),
            "upload_date": item.get("upload_date") or "2000-01-01",
            "position_in_playlist": item.get("playlist_index") if playlist_url in playlist_ids else None,
            "resolution": item.get("resolution") or "",
            "categories": [category_ids[name] for name in item.get("categories") or [] if name in category_ids],
            "tags": [tag_ids[name] for name in item.get("tags") or [] if name in tag_ids],
        }
        video_ids[video_url] = len(video_ids) + 1
        video_records.append(fixture("videos.video", video_ids[video_url], fields))
    write_json("videos.json", video_records)

    comments = {}
    for _, item in posts.values():
        video_url = item.get("webpage_url")
        if video_url not in video_ids:
            continue
        for comment in item.get("comments") or []:
            source_id = comment.get("id")
            author = username(comment.get("author"))
            if source_id and author in user_ids:
                key = (video_url, str(source_id))
                comments.setdefault(key, {
                    "video": video_ids[video_url],
                    "author": user_ids[author],
                    "source_id": str(source_id),
                    "parent_source_id": str(comment.get("parent") or ""),
                    "text": comment.get("text") or "",
                    "like_count": comment.get("like_count") or 0,
                    "timestamp": normalize_timestamp(comment.get("timestamp")),
                })
    comment_ids = {key: pk for pk, key in enumerate(sorted(comments), 1)}
    write_json("comments.json", [
        fixture("videos.comment", pk, {
            "source_id": comment["source_id"],
            "video": comment["video"],
            "parent": comment_ids.get((key[0], comment["parent_source_id"])),
            "author": comment["author"],
            "text": comment["text"],
            "like_count": comment["like_count"],
            "timestamp": comment["timestamp"] or "2000-01-01T00:00:00+00:00",
        })
        for key, pk in comment_ids.items()
        for comment in [comments[key]]
    ])
    print(f"Generated fixtures for {len(video_ids)} videos, {len(channels)} channels, {len(playlists)} playlists, and {len(comments)} comments.")


if __name__ == "__main__":
    build_fixtures()
