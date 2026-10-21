from pathlib import Path
import json
import subprocess
import sys
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Prefetch
from django.core.management import call_command
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .models import Category, Channel, Comment, Playlist, Video, media_file_path
from .forms import CommentForm


def local_video_file(video):
    return media_file_path(video.video_loc)


def youtube_embed_url(video_url):
    parsed = urlparse(video_url or "")
    host = (parsed.hostname or "").lower()
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] in {"embed", "shorts", "live"}:
                video_id = parts[1]
    if video_id and video_id.isascii() and all(char.isalnum() or char in "_-" for char in video_id):
        return f"https://www.youtube-nocookie.com/embed/{video_id}"
    return ""


@login_required(login_url="login")
def library_import(request):
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)
    status_path = media_root / f".import-status-{request.user.pk}.json"
    history_path = media_root / f".import-history-{request.user.pk}.json"
    if request.method == "POST":
        try:
            current_status = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            current_status = {}
        if current_status.get("state") == "running":
            messages.error(request, "An import is already running. Check this page again in a moment.")
            return redirect("library-import")
        uploaded = request.FILES.get("url_file")
        if uploaded:
            if not uploaded.name.lower().endswith(".txt"):
                messages.error(request, "Choose a .txt file with one YouTube link per line.")
                return redirect("library-import")
            links = uploaded.read().decode("utf-8-sig", errors="replace")
            url_path = media_root / f".import-urls-{request.user.pk}.txt"
            url_path.write_text(links, encoding="utf-8")
            args = [sys.executable, str(settings.BASE_DIR / "manage.py"), "import_youtube",
                    "--urls", str(url_path), "--status-file", str(status_path),
                    "--history-file", str(history_path)]
        elif request.POST.get("import_existing"):
            args = [sys.executable, str(settings.BASE_DIR / "manage.py"), "import_youtube",
                    "--no-download", "--status-file", str(status_path),
                    "--history-file", str(history_path)]
        else:
            messages.error(request, "Choose a URL list, or import files already in media/.")
            return redirect("library-import")
        status_path.write_text(json.dumps({
            "run_id": uuid4().hex,
            "started_at": timezone.now().isoformat(),
            "state": "running",
            "message": "Import starting",
        }), encoding="utf-8")
        log_path = media_root / f".import-{request.user.pk}.log"
        with log_path.open("ab") as log_file:
            subprocess.Popen(args, cwd=settings.BASE_DIR, stdin=subprocess.DEVNULL,
                             stdout=log_file, stderr=subprocess.STDOUT,
                             start_new_session=True, close_fds=True)
        messages.success(request, "Import started. This page will update while downloads and database loading run.")
        return redirect("library-import")

    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        status = None
    try:
        import_history = json.loads(history_path.read_text(encoding="utf-8"))
        if not isinstance(import_history, list):
            import_history = []
    except (OSError, json.JSONDecodeError):
        import_history = []
    for entry in import_history:
        finished_at = parse_datetime(entry.get("finished_at", ""))
        entry["finished_at_display"] = (
            timezone.localtime(finished_at).strftime("%b %d, %Y · %I:%M %p")
            if finished_at
            else ""
        )
    return render(request, "videos/library_import.html", {
        "status": status,
        "import_history": import_history,
        "video_count": Video.objects.count(),
        "playlist_count": Playlist.objects.count(),
        "channel_count": Channel.objects.count(),
    })


class VideoListView(ListView):
    model = Video
    template_name = "videos/video_list.html"
    paginate_by = 16

    def get_queryset(self):
        items = self.video_cards(Video.objects.all())

        self.search_query = self.request.GET.get("q", "").strip()
        if self.search_query:
            query = self.search_query.casefold()
            items = [item for item in items if query in item["title"].casefold()]

        self.sort_order = self.request.GET.get("sort", "latest")
        self.sort_items(items)
        self.listing_title = ""
        self.listing_type = "home"
        self.listing_id = None
        return items

    @staticmethod
    def video_cards(queryset):
        return [
            {
                "kind": "video",
                "id": row["id"],
                "title": row["title"],
                "thumbnail_loc": row["thumbnail_loc"],
                "local_thumbnail_available": media_file_path(row["thumbnail_loc"]) is not None,
                "thumbnail_url": row["thumbnail_url"],
                "view_count": row["view_count"],
                "duration": row["duration"],
                "date": row["upload_date"],
                "channel_id": row["channel_id"],
                "channel_name": row["channel__name"],
                "channel_url": row["channel__url"],
            }
            for row in queryset.values(
                "id",
                "title",
                "thumbnail_loc",
                "thumbnail_url",
                "view_count",
                "duration",
                "upload_date",
                "channel_id",
                "channel__name",
                "channel__url",
            )
        ]

    def sort_items(self, items):
        if self.sort_order == "popular":
            items.sort(
                key=lambda item: (item["view_count"], item["date"]),
                reverse=True,
            )
        else:
            items.sort(
                key=lambda item: (
                    item["date"],
                    item["kind"] == "playlist",
                    item["id"],
                ),
                reverse=self.sort_order == "latest",
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            search_query=self.search_query,
            sort_order=self.sort_order,
            listing_title=self.listing_title,
            listing_type=self.listing_type,
            listing_id=self.listing_id,
            sidebar_categories=Category.objects.filter(video__isnull=False).distinct().order_by("name"),
            sidebar_channels=Channel.objects.filter(video__isnull=False).distinct().order_by("name"),
            sidebar_playlists=Playlist.objects.all().order_by("name"),
        )
        return context


class CategoryVideosView(VideoListView):
    def get_queryset(self):
        category = get_object_or_404(Category, pk=self.kwargs["pk"])
        self.listing_title = category.name
        self.listing_type = "category"
        self.listing_id = category.pk
        self.search_query = self.request.GET.get("q", "").strip()
        self.sort_order = self.request.GET.get("sort", "latest")
        items = self.video_cards(Video.objects.filter(categories=category).distinct())
        self.filter_and_sort(items)
        return items

    def filter_and_sort(self, items):
        if self.search_query:
            query = self.search_query.casefold()
            items[:] = [item for item in items if query in item["title"].casefold()]
        self.sort_items(items)


class ChannelVideosView(CategoryVideosView):
    def get_queryset(self):
        channel = get_object_or_404(Channel, pk=self.kwargs["pk"])
        self.listing_title = channel.name
        self.listing_type = "channel"
        self.listing_id = channel.pk
        self.search_query = self.request.GET.get("q", "").strip()
        self.sort_order = self.request.GET.get("sort", "latest")
        items = self.video_cards(Video.objects.filter(channel=channel))
        self.filter_and_sort(items)
        return items


class VideoDetailView(DetailView):
    model = Video

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("channel", "playlist")
            .prefetch_related("categories", "tags")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        video = self.object
        context["local_video_available"] = video.local_video_available
        context["local_thumbnail_available"] = video.local_thumbnail_available
        context["youtube_embed_url"] = youtube_embed_url(video.video_url)
        context["comment_form"] = CommentForm()
        context["comments_count"] = video.comment_set.count()
        replies = Comment.objects.select_related("author__account").order_by(
            "-timestamp"
        )
        context["root_comments"] = (
            video.comment_set.filter(parent__isnull=True)
            .select_related("author__account")
            .prefetch_related(
                Prefetch("replies", queryset=replies, to_attr="reply_list")
            )
            .order_by("-timestamp")
        )
        if self.request.user.is_authenticated:
            context["video_watched"] = video.watched_by.filter(
                pk=self.request.user.pk
            ).exists()
            context["video_to_watch"] = video.to_watch_by.filter(
                pk=self.request.user.pk
            ).exists()
        return context


class PlaylistDetailView(DetailView):
    model = Playlist

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["video_list"] = self.object.video_set.select_related(
            "channel"
        ).order_by("position_in_playlist", "pk")
        return context


def stream_video(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video_path = local_video_file(video)
    if not video_path:
        return HttpResponse(status=404)

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range", "")
    if range_header:
        try:
            unit, bounds = range_header.split("=", 1)
            start_text, end_text = bounds.split("-", 1)
            if unit != "bytes" or not start_text:
                raise ValueError
            start = int(start_text)
            end = min(int(end_text), file_size - 1) if end_text else file_size - 1
            if start < 0 or end < start or start >= file_size:
                raise ValueError
        except ValueError:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            return response

        length = end - start + 1
        response = StreamingHttpResponse(
            _read_file(video_path, start, length),
            status=206,
            content_type=(
                "video/webm" if video_path.suffix.lower() == ".webm" else "video/mp4"
            ),
        )
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = str(length)
    else:
        response = StreamingHttpResponse(
            _read_file(video_path, 0, file_size),
            content_type=(
                "video/webm" if video_path.suffix.lower() == ".webm" else "video/mp4"
            ),
        )
        response["Content-Length"] = str(file_size)
    response["Accept-Ranges"] = "bytes"
    return response


def _read_file(path, start, length, chunk_size=64 * 1024):
    with path.open("rb") as video_file:
        video_file.seek(start)
        remaining = length
        while remaining:
            chunk = video_file.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@login_required(login_url="login")
@require_POST
def toggle_video_watch_status(request, pk):
    video = get_object_or_404(Video, pk=pk)
    status = request.POST.get("status")
    statuses = {
        "watched": (video.watched_by, video.to_watch_by),
        "to-watch": (video.to_watch_by, video.watched_by),
    }
    if status in statuses:
        selected, other = statuses[status]
        if selected.filter(pk=request.user.pk).exists():
            selected.remove(request.user)
        else:
            other.remove(request.user)
            selected.add(request.user)
    return redirect("video-detail", pk=video.pk)


@login_required(login_url="login")
@require_POST
def add_video_comment(request, pk):
    video = get_object_or_404(Video, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.video = video
        comment.author = request.user
        comment.source_id = str(uuid4())
        comment.timestamp = timezone.now()
        comment.save()
        messages.success(request, "Your comment has been posted.")
    else:
        messages.error(request, "Enter a comment before submitting.")
    return redirect("video-detail", pk=video.pk)
