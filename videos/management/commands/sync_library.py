import json
import re
from datetime import date, datetime, timezone as utc

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import Account
from videos.models import Category, Channel, Comment, Video


VIDEO_EXTENSIONS = {".mp4", ".m4v", ".webm", ".mov", ".mkv", ".avi"}
THUMBNAIL_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
INFO_KEYS = (
    "title", "thumbnail", "description", "duration", "view_count", "webpage_url",
    "comment_count", "like_count", "channel", "channel_follower_count",
    "channel_is_verified", "uploader_id", "uploader_url", "upload_date",
    "resolution", "categories", "comments",
)
COMMENT_KEYS = ("id", "parent", "text", "like_count", "author", "author_thumbnail", "timestamp")


def number(value):
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def upload_day(info):
    for value in (info.get("upload_date"), info.get("release_date"), info.get("timestamp")):
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value, utc.utc).date()
            except (OverflowError, OSError, ValueError):
                continue
        try:
            return date.fromisoformat(str(value)[:10])
        except (TypeError, ValueError):
            try:
                return datetime.strptime(str(value)[:8], "%Y%m%d").date()
            except (TypeError, ValueError):
                continue


def clean_info(raw):
    info = {key: raw.get(key) for key in INFO_KEYS}
    info["comments"] = [
        {key: item.get(key) for key in COMMENT_KEYS}
        for item in raw.get("comments") or [] if isinstance(item, dict)
    ]
    info["categories"] = [name for name in raw.get("categories") or [] if isinstance(name, str)]
    info["title"] = raw.get("title") or ""
    info["thumbnail"] = raw.get("thumbnail") or ""
    info["description"] = raw.get("description") or ""
    info["duration"] = number(raw.get("duration"))
    info["view_count"] = number(raw.get("view_count"))
    info["webpage_url"] = raw.get("webpage_url") or ""
    info["comment_count"] = number(raw.get("comment_count"))
    if info["comment_count"] is None:
        info["comment_count"] = len(info["comments"])
    info["like_count"] = number(raw.get("like_count"))
    info["channel"] = raw.get("channel") or raw.get("uploader") or ""
    info["channel_follower_count"] = number(raw.get("channel_follower_count"))
    info["uploader_id"] = raw.get("uploader_id") or ""
    info["uploader_url"] = raw.get("uploader_url") or ""
    day = upload_day(raw)
    info["upload_date"] = day.isoformat() if day else None
    info["resolution"] = raw.get("resolution") or ""
    if not info["resolution"] and raw.get("width") and raw.get("height"):
        info["resolution"] = f"{raw['width']}x{raw['height']}"
    return info


def username(value):
    return re.sub(r"[^\w.@+-]", "_", str(value or "youtube-user"))[:150] or "youtube-user"


def batches(items, size=500):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start : start + size]


def comment_time(value):
    if isinstance(value, (int, float)) or str(value or "").isdigit():
        try:
            return datetime.fromtimestamp(float(value), utc.utc)
        except (OverflowError, OSError, ValueError):
            return timezone.now()
    value = parse_datetime(str(value or ""))
    if value is None:
        return timezone.now()
    return timezone.make_aware(value, utc.utc) if timezone.is_naive(value) else value


def info_for(video, info_by_file, by_folder):
    path = video.with_suffix(".info.json")
    if path not in info_by_file:
        siblings = by_folder.get(video.parent, [])
        path = siblings[0] if len(siblings) == 1 else None
    return path, info_by_file.get(path, {})


def thumbnail_for(video, info_file):
    for base in (video, info_file):
        if base is not None:
            stem = base.name.removesuffix(".info.json") if base == info_file else base.stem
            for ext in THUMBNAIL_EXTENSIONS:
                path = base.with_name(stem + ext)
                if path.is_file():
                    return path


def load_users(infos):
    names = {username(info["uploader_id"]) for _, info in infos if info.get("uploader_id")}
    names.update(username(c.get("author")) for _, info in infos for c in info.get("comments", []))
    names = sorted(names)
    existing = set()
    for group in batches(names):
        existing.update(User.objects.filter(username__in=group).values_list("username", flat=True))
    User.objects.bulk_create(
        [User(username=name) for name in names if name not in existing],
        ignore_conflicts=True, batch_size=500,
    )
    users = {}
    for group in batches(names):
        users.update({user.username: user for user in User.objects.filter(username__in=group)})
    return users


def sync_accounts(infos, users):
    avatars = {
        username(c.get("author")): c["author_thumbnail"]
        for _, info in infos for c in info.get("comments", []) if c.get("author_thumbnail")
    }
    accounts = {}
    for group in batches(user.pk for user in users.values()):
        accounts.update({a.user_id: a for a in Account.objects.filter(user_id__in=group)})
    Account.objects.bulk_create(
        [Account(user=u, image_url=avatars.get(u.username)) for u in users.values() if u.pk not in accounts],
        ignore_conflicts=True, batch_size=500,
    )
    names = {u.pk: u.username for u in users.values()}
    changed = []
    for account in accounts.values():
        avatar = avatars.get(names[account.user_id])
        if avatar and account.image_url != avatar:
            account.image_url = avatar
            changed.append(account)
    Account.objects.bulk_update(changed, ("image_url",), batch_size=500)


def get_channel(info, users, channels):
    name = (info.get("channel") or "YourTube Library")[:200]
    owner_name = username(info["uploader_id"]) if info.get("uploader_id") else None
    key = owner_name or name
    if key not in channels:
        owner = users.get(owner_name) if owner_name else None
        lookup = {"owner": owner} if owner else {"owner__isnull": True, "name": name}
        channel, _ = Channel.objects.get_or_create(
            **lookup,
            defaults={"name": name, "follower_count": 0, "is_verified": False, "url": ""},
        )
        channel.name = name
        if info.get("channel_follower_count") is not None:
            channel.follower_count = info["channel_follower_count"]
        if info.get("channel_is_verified") is not None:
            channel.is_verified = info["channel_is_verified"] is True
        channel.url = info.get("uploader_url") or channel.url or ""
        channel.save()
        channels[key] = channel
    return channels[key]


def sync_comments(video, comments, users):
    rows = [Comment(
        video=video, source_id=str(c["id"]), author=users[username(c.get("author"))],
        text=c.get("text") or "", like_count=number(c.get("like_count")) or 0,
        timestamp=comment_time(c.get("timestamp")),
    ) for c in comments if c.get("id")]
    if not rows:
        return 0
    Comment.objects.bulk_create(
        rows, update_conflicts=True, unique_fields=("video", "source_id"),
        update_fields=("author", "text", "like_count", "timestamp"), batch_size=500,
    )
    saved = {c.source_id: c for c in Comment.objects.filter(
        video=video, source_id__in=[row.source_id for row in rows]
    )}
    parents = []
    for data in comments:
        comment = saved.get(str(data.get("id") or ""))
        parent = saved.get(str(data.get("parent") or ""))
        if comment and comment.parent_id != (parent.pk if parent else None):
            comment.parent = parent
            parents.append(comment)
    Comment.objects.bulk_update(parents, ("parent",), batch_size=500)
    return len(rows)


class Command(BaseCommand):
    help = "Sync videos and metadata from DATA_ROOT."

    @transaction.atomic
    def handle(self, *args, **options):
        root = settings.DATA_ROOT
        if not root.is_dir():
            raise CommandError(f"Media folder not found: {root}")

        info_by_file = {}
        for path in root.rglob("*.info.json"):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    info = clean_info(raw)
                    if info != raw:
                        path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
                    info_by_file[path] = info
            except (OSError, json.JSONDecodeError) as error:
                raise CommandError(f"Could not sync {path}: {error}") from error

        videos = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
        by_folder = {}
        for path in info_by_file:
            by_folder.setdefault(path.parent, []).append(path)
        infos = [info_for(path, info_by_file, by_folder) for path in videos]
        users = load_users(infos)
        sync_accounts(infos, users)

        channels, categories = {}, {}
        added = comments_synced = 0
        for path, (info_file, info) in zip(videos, infos):
            rel = path.relative_to(root).as_posix()
            channel = get_channel(info, users, channels)
            video = Video.objects.filter(video_loc=rel).first()
            if video is None and info.get("webpage_url"):
                video = Video.objects.filter(video_url=info["webpage_url"]).first()
            created = video is None
            if created:
                video = Video(channel=channel)

            thumb = thumbnail_for(path, info_file)
            video.title = (info.get("title") or path.stem)[:200]
            video.video_loc = rel
            video.thumbnail_loc = thumb.relative_to(root).as_posix() if thumb else ""
            video.thumbnail_url = info.get("thumbnail") or video.thumbnail_url or ""
            video.description = info.get("description") or video.description or ""
            for field in ("duration", "view_count", "comment_count", "like_count"):
                value = info.get(field)
                if value is not None:
                    setattr(video, field, value)
            video.duration = 0 if video.duration is None else video.duration
            video.view_count = 0 if video.view_count is None else video.view_count
            video.comment_count = len(info.get("comments", [])) if video.comment_count is None else video.comment_count
            video.like_count = 0 if video.like_count is None else video.like_count
            video.video_url = info.get("webpage_url") or video.video_url or ""
            video.channel = channel
            video.upload_date = upload_day(info) or video.upload_date or date.fromtimestamp(path.stat().st_mtime)
            video.resolution = info.get("resolution") or video.resolution or ""
            video.save()

            linked = []
            for name in info.get("categories", []):
                if name not in categories:
                    categories[name], _ = Category.objects.get_or_create(name=name[:100])
                linked.append(categories[name])
            video.categories.set(linked)
            comments_synced += sync_comments(video, info.get("comments", []), users)
            added += created

        self.stdout.write(
            f"Cleaned {len(info_by_file)} info files; added {added} videos; "
            f"synced {comments_synced} comments from {root}."
        )
