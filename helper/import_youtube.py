"""Download URLs from a text file (optional) and import yt-dlp metadata."""
import json
import argparse
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from accounts.models import Account
from videos.models import Category, Channel, Comment, Playlist, Tag, Video


def safe_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def metadata_files(media_root):
    return sorted(media_root.rglob("*.info.json"))


def local_file(info_path, suffixes):
    stem = info_path.name[:-len(".info.json")]
    for suffix in suffixes:
        candidate = info_path.with_name(stem + suffix)
        if candidate.is_file():
            return candidate
    return None


def relative_media_path(path):
    return path.relative_to(settings.BASE_DIR).as_posix() if path else ""


def upload_day(value):
    if value:
        try:
            return datetime.strptime(str(value)[:8], "%Y%m%d").date()
        except ValueError:
            pass
    return date.today()


class Command(BaseCommand):
    help = "Download a URL list with yt-dlp and import all media/*.info.json metadata."

    IMPORT_STEPS = [
        ("prepare", "Prepare import"),
        ("download", "Download videos and metadata"),
        ("structure", "Clean and normalize media folders"),
        ("model_data", "Build helper model JSON files"),
        ("scan", "Find metadata files"),
        ("channels", "Prepare channels and playlists"),
        ("videos", "Add videos to the library"),
        ("comments", "Add comments and replies"),
        ("reconcile", "Remove videos no longer in media/"),
        ("finish", "Finish up"),
    ]

    def add_arguments(self, parser):
        parser.add_argument("--urls", type=Path, help="Text file with one video/channel/playlist URL per line")
        parser.add_argument("--no-download", action="store_true", help="Import existing media without downloading")
        parser.add_argument("--status-file", type=Path, help=argparse.SUPPRESS)
        parser.add_argument("--history-file", type=Path, help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        media_root.mkdir(parents=True, exist_ok=True)
        status_file = options.get("status_file")
        self.history_file = options.get("history_file")
        self.write_status(
            status_file,
            state="running",
            message="Preparing import",
            current_step="prepare",
            activity="Starting the import process.",
            steps=[{"key": key, "label": label, "state": "pending", "detail": ""}
                   for key, label in self.IMPORT_STEPS],
        )
        self.set_stage(status_file, "prepare", "Checking the selected import source.")
        if options["urls"] and not options["no_download"]:
            url_file = options["urls"].expanduser().resolve()
            if not url_file.is_file():
                self.write_status(status_file, state="failed", message="The uploaded URL list is missing; submit it again.")
                raise CommandError(f"URL list not found: {url_file}")
            urls = [line.strip() for line in url_file.read_text(encoding="utf-8-sig").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")]
            if not urls:
                self.write_status(status_file, state="failed", message="The uploaded text file did not contain any links.")
                raise CommandError("The URL list has no links.")
            command = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-warnings",
                       "--write-info-json", "--write-thumbnail", "--convert-thumbnails", "jpg",
                       "--write-comments", "--no-overwrites", "--merge-output-format", "mp4", "--yes-playlist",
                       "-o", str(media_root / "%(uploader)s" / "%(title)s [%(id)s]" / "%(title)s [%(id)s].%(ext)s"),
                       "-a", str(url_file)]
            self.set_stage(status_file, "download", f"Starting yt-dlp for {len(urls)} link(s).")
            self.stdout.write("Downloading media with yt-dlp…")
            process = subprocess.Popen(
                command, cwd=settings.BASE_DIR, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            last_activity = "yt-dlp is starting."
            for line in process.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self.stdout.write(line)
                last_activity = line[-300:]
                self.update_stage(status_file, "download", last_activity)
            result_code = process.wait()
            url_file.unlink(missing_ok=True)
            if result_code:
                self.write_status(status_file, state="failed", message="yt-dlp failed; see the local server log for details")
                raise CommandError("yt-dlp failed. Check the URLs and your yt-dlp installation, then retry; existing files were kept.")
            self.update_stage(status_file, "download", "yt-dlp finished downloading the requested items.", state="complete")
        else:
            self.update_stage(status_file, "download", "Skipped; importing files already present in media/.", state="complete")

        try:
            self.set_stage(status_file, "structure", "Cleaning metadata and incomplete or duplicate media files.")
            self.run_helper_script("folder_structuring.py")
            self.update_stage(status_file, "structure", "Cleaned media files and normalized JSON metadata.", state="complete")

            self.set_stage(status_file, "model_data", "Generating helper/data model JSON files from media metadata.")
            self.run_helper_script("get_data.py")
            self.update_stage(status_file, "model_data", "Generated users, channels, playlists, videos, and comments model JSON files.", state="complete")
        except Exception as error:
            self.write_status(status_file, state="failed", message=f"Media preparation failed: {error}")
            raise

        self.set_stage(status_file, "scan", "Searching media/ for yt-dlp .info.json files.")
        infos = metadata_files(media_root)
        if not infos:
            self.write_status(status_file, state="failed", message="No yt-dlp .info.json files were found under media/.")
            raise CommandError(f"No yt-dlp .info.json files found under {media_root}.")
        self.update_stage(status_file, "scan", f"Found {len(infos)} metadata file(s).", state="complete")
        try:
            result = self.import_metadata(infos, status_file=status_file)
        except Exception as error:
            self.write_status(status_file, state="failed", message=f"Database import failed: {error}")
            raise
        self.set_stage(status_file, "finish", "The database updates are committed.")
        self.update_stage(status_file, "finish", "Import complete.", state="complete")
        self.write_status(status_file, state="complete", message=f"Imported {result['videos']} videos and {result['playlists']} playlists",
                          current_step="finish", activity="All selected media and metadata have been processed.", result=result)
        self.stdout.write(self.style.SUCCESS(
            f"Imported {result['videos']} videos, {result['playlists']} playlists, "
            f"{result['channels']} channels, and {result['comments']} comments."
        ))

    @staticmethod
    def run_helper_script(script_name):
        script_path = settings.BASE_DIR / "helper" / script_name
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=settings.BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if result.returncode:
            raise CommandError(
                f"{script_name} failed (exit {result.returncode}):\n{result.stdout[-4000:]}"
            )

    def write_status(self, path, **data):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                current = {}
            current.update(data)
            if data.get("state") == "failed":
                for step in current.get("steps", []):
                    if step.get("state") == "active":
                        step["state"] = "failed"
                        step["detail"] = data.get("message", "This step failed.")
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(json.dumps(current), encoding="utf-8")
            temporary.replace(path)
            if self.history_file and data.get("state") in {"complete", "failed"}:
                self.history_file.parent.mkdir(parents=True, exist_ok=True)
                try:
                    history = json.loads(self.history_file.read_text(encoding="utf-8"))
                    if not isinstance(history, list):
                        history = []
                except (OSError, json.JSONDecodeError):
                    history = []
                run_id = current.get("run_id")
                entry = {
                    "run_id": run_id,
                    "started_at": current.get("started_at"),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "state": current.get("state"),
                    "message": current.get("message", ""),
                    "result": current.get("result", {}),
                }
                if run_id:
                    history = [item for item in history if item.get("run_id") != run_id]
                history.insert(0, entry)
                history = history[:50]
                history_temp = self.history_file.with_suffix(self.history_file.suffix + ".tmp")
                history_temp.write_text(json.dumps(history, indent=2), encoding="utf-8")
                history_temp.replace(self.history_file)

    @classmethod
    def update_stage(cls, path, key, detail, state="active"):
        if not path:
            return
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        steps = current.get("steps", [])
        for step in steps:
            if step["key"] == key:
                step["state"] = state
                step["detail"] = detail
        current.update(current_step=key, activity=detail, steps=steps)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(current), encoding="utf-8")
        temporary.replace(path)

    @classmethod
    def set_stage(cls, path, key, detail):
        if not path:
            return
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current = {}
        steps = current.get("steps", [])
        for step in steps:
            if step["state"] == "active":
                step["state"] = "complete"
            if step["key"] == key:
                step["state"] = "active"
                step["detail"] = detail
        current.update(current_step=key, activity=detail, steps=steps)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(current), encoding="utf-8")
        temporary.replace(path)

    @transaction.atomic
    def import_metadata(self, paths, status_file=None):
        User = get_user_model()
        parsed = []
        self.set_stage(status_file, "channels", f"Reading up to {len(paths)} metadata file(s).")
        for path in paths:
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(item, dict) and item.get("duration") is not None and item.get("webpage_url"):
                parsed.append((path, item))

        self.update_stage(status_file, "channels", f"Prepared {len(parsed)} valid video record(s); resolving channels and playlists.")

        channel_by_url, playlist_by_url, video_by_url = {}, {}, {}
        for index, (path, item) in enumerate(parsed, start=1):
            uploader = (item.get("uploader_id") or item.get("channel_id") or
                        item.get("uploader") or item.get("channel") or "unknown-channel")
            username = re.sub(r"[^\w.@+-]", "_", str(uploader).lstrip("@"))[:150] or "youtube-user"
            owner, _ = User.objects.get_or_create(username=username)
            Account.objects.get_or_create(user=owner)
            channel_url = item.get("channel_url") or item.get("uploader_url") or ""
            channel_key = channel_url or f"owner:{owner.pk}"
            if not channel_url:
                channel_url = f"https://www.youtube.com/@{username}"
            channel, _ = Channel.objects.update_or_create(
                owner=owner,
                defaults={"name": (item.get("channel") or item.get("uploader") or username)[:200],
                          "follower_count": safe_int(item.get("channel_follower_count")),
                          "is_verified": item.get("channel_is_verified") is True,
                          "url": channel_url},
            )
            channel_by_url[channel_key] = (channel, owner)

            playlist_url = item.get("playlist_webpage_url")
            if playlist_url and playlist_url not in playlist_by_url:
                playlist_title = (item.get("playlist_title") or item.get("playlist") or item.get("title") or "Playlist")[:200]
                playlist, _ = Playlist.objects.update_or_create(
                    url=playlist_url,
                    defaults={"name": playlist_title,
                              "description": item.get("playlist_description") or "",
                              "modified_date": upload_day(item.get("release_date") or item.get("upload_date")),
                              "view_count": safe_int(item.get("playlist_view_count")),
                              "video_count": safe_int(item.get("playlist_count") or item.get("n_entries")),
                              "thumbnail_loc": relative_media_path(local_file(path, (".jpg", ".jpeg", ".png", ".webp"))),
                              "creator": owner},
                )
                playlist_by_url[playlist_url] = playlist
            if index % 25 == 0 or index == len(parsed):
                self.update_stage(status_file, "channels", f"Resolved channels and playlists for {index} of {len(parsed)} records.")

        self.set_stage(status_file, "videos", f"Adding {len(parsed)} video record(s) to the library.")
        for index, (path, item) in enumerate(parsed, start=1):
            uploader = (item.get("uploader_id") or item.get("channel_id") or item.get("uploader") or item.get("channel") or "unknown-channel")
            username = re.sub(r"[^\w.@+-]", "_", str(uploader).lstrip("@"))[:150] or "youtube-user"
            owner = User.objects.get(username=username)
            channel = Channel.objects.get(owner=owner)
            video_url = item["webpage_url"]
            video_path = local_file(path, (".mp4", ".webm", ".mkv", ".mov", ".m4v"))
            thumb_path = local_file(path, (".jpg", ".jpeg", ".png", ".webp"))
            playlist_url = item.get("playlist_webpage_url")
            playlist = playlist_by_url.get(playlist_url)
            fields = {"title": (item.get("title") or video_url)[:200],
                      "video_loc": relative_media_path(video_path),
                      "thumbnail_loc": relative_media_path(thumb_path),
                      "thumbnail_url": item.get("thumbnail") or "https://www.youtube.com/img/desktop/yt_1200.png",
                      "description": item.get("description") or "", "duration": safe_int(item.get("duration")),
                      "view_count": safe_int(item.get("view_count")), "video_url": video_url,
                      "comment_count": safe_int(item.get("comment_count")), "like_count": safe_int(item.get("like_count")),
                      "channel": channel, "playlist": playlist, "upload_date": upload_day(item.get("upload_date")),
                      "position_in_playlist": safe_int(item.get("playlist_index"), 0) or None,
                      "resolution": item.get("resolution") or ""}
            video, _ = Video.objects.update_or_create(video_url=video_url, defaults=fields)
            video.categories.set([Category.objects.get_or_create(name=name[:100])[0]
                                  for name in item.get("categories") or [] if name])
            video.tags.set([Tag.objects.get_or_create(name=name[:200])[0]
                            for name in item.get("tags") or [] if name])
            video_by_url[video_url] = video
            if index % 25 == 0 or index == len(parsed):
                self.update_stage(status_file, "videos", f"Saved {index} of {len(parsed)} video record(s).")

        comments_count = 0
        self.set_stage(status_file, "comments", "Adding comments and linking replies.")
        for index, (path, item) in enumerate(parsed, start=1):
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
                    video=video, source_id=source_id,
                    defaults={"author": author, "text": comment_data.get("text") or "",
                              "like_count": safe_int(comment_data.get("like_count")), "timestamp": when},
                )
                comment_map[source_id] = comment
                comments_count += 1
                if comments_count % 500 == 0:
                    self.update_stage(status_file, "comments", f"Saved {comments_count} comments so far.")
            for comment_data in item.get("comments") or []:
                source_id = str(comment_data.get("id") or "")
                parent_id = str(comment_data.get("parent") or "")
                if source_id in comment_map:
                    comment_map[source_id].parent = comment_map.get(parent_id)
                    comment_map[source_id].save(update_fields=["parent"])
            if index % 25 == 0 or index == len(parsed):
                self.update_stage(status_file, "comments", f"Processed comments for {index} of {len(parsed)} videos ({comments_count} comments).")

        if not video_by_url:
            raise CommandError("No valid videos were generated from media/; database records were left unchanged.")
        self.set_stage(status_file, "reconcile", "Removing database videos whose metadata is no longer present in media/.")
        stale_videos = Video.objects.exclude(video_url__in=video_by_url)
        removed_count = stale_videos.count()
        stale_videos.delete()
        self.update_stage(status_file, "reconcile", f"Removed {removed_count} stale video(s).", state="complete")
        self.update_stage(status_file, "channels", f"Prepared {len(channel_by_url)} channel(s) and {len(playlist_by_url)} playlist(s).", state="complete")
        self.update_stage(status_file, "videos", f"Saved {len(video_by_url)} video(s).", state="complete")
        self.update_stage(status_file, "comments", f"Processed {comments_count} comment(s).", state="complete")
        return {"videos": len(video_by_url), "playlists": len(playlist_by_url),
                "channels": len(channel_by_url), "comments": comments_count,
                "removed_videos": removed_count}
