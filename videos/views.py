import mimetypes
import shutil
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils._os import safe_join
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView
from django.views.static import serve

from .models import Category, Channel, Comment, Video


def serve_media(request, path):
    range_header = request.headers.get("Range")
    if range_header and range_header.startswith("bytes="):
        file_path = Path(safe_join(settings.DATA_ROOT, path))
        file_size = file_path.stat().st_size
        start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
        if start_text:
            start = int(start_text)
            end = min(int(end_text), file_size - 1) if end_text else file_size - 1
        else:
            start = max(0, file_size - int(end_text))
            end = file_size - 1

        if start >= file_size or start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            return response

        length = end - start + 1

        def read_range():
            with open(file_path, "rb") as media_file:
                media_file.seek(start)
                remaining = length
                while remaining:
                    chunk = media_file.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        response = StreamingHttpResponse(
            read_range(), status=206, content_type=content_type
        )
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(length)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        return response

    return serve(request, path, document_root=settings.DATA_ROOT)


class VideoListView(ListView):
    model = Video
    template_name = "videos/video_list.html"
    paginate_by = 24
    listing_type = "home"
    listing_title = ""
    listing_id = None

    def get_listing_queryset(self):
        return super().get_queryset()

    def get_queryset(self):
        videos = self.get_listing_queryset()

        self.search_query = self.request.GET.get("q", "")
        self.sort_order = self.request.GET.get("sort", "latest")
        if self.search_query:
            videos = videos.filter(
                Q(title__icontains=self.search_query)
                | Q(channel__name__icontains=self.search_query)
            )

        order_by = {
            "popular": ("-view_count", "-upload_date", "-pk"),
            "oldest": ("upload_date", "pk"),
            "shortest": ("duration", "pk"),
            "longest": ("-duration", "pk"),
        }.get(self.sort_order, ("-upload_date", "-pk"))

        return videos.select_related("channel").order_by(*order_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            search_query=self.search_query,
            sort_order=self.sort_order,
            listing_title=self.listing_title,
            listing_type=self.listing_type,
            listing_id=self.listing_id,
            sidebar_categories=Category.objects.filter(video__isnull=False)
            .distinct()
            .order_by("name"),
            sidebar_channels=Channel.objects.filter(video__isnull=False)
            .distinct()
            .order_by("name"),
        )
        return context


class CategoryVideosView(VideoListView):
    listing_type = "category"

    def get_listing_queryset(self):
        category = get_object_or_404(Category, pk=self.kwargs["pk"])
        self.listing_title = category.name
        self.listing_id = category.pk
        return Video.objects.filter(categories=category).distinct()


class ChannelVideosView(VideoListView):
    listing_type = "channel"

    def get_listing_queryset(self):
        channel = get_object_or_404(Channel, pk=self.kwargs["pk"])
        self.listing_title = channel.name
        self.listing_id = channel.pk
        return Video.objects.filter(channel=channel)


class VideoDetailView(DetailView):
    model = Video

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("channel")
            .prefetch_related("categories")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        video = self.object
        context["root_comments"] = (
            video.comment_set.filter(parent__isnull=True)
            .select_related("author__account")
            .prefetch_related(
                Prefetch(
                    "replies",
                    queryset=Comment.objects.select_related("author__account").order_by(
                        "-timestamp"
                    ),
                    to_attr="reply_list",
                )
            )
            .order_by("-timestamp")
        )

        if self.request.user.is_authenticated:
            context["video_status"] = video.watch_status
            context["video_favorite"] = video.is_fav
        return context


@login_required(login_url="login")
@require_POST
def set_video_status(request, pk):
    video = get_object_or_404(Video, pk=pk)
    status = request.POST.get("status", "none") or "none"
    video.watch_status = status
    video.save()
    return JsonResponse({"status": status})


@login_required(login_url="login")
@require_POST
def toggle_video_favorite(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video.is_fav = not video.is_fav
    video.save()
    return JsonResponse({"favorited": video.is_fav})


@login_required(login_url="login")
@require_POST
def delete_video(request, pk):
    video = get_object_or_404(Video, pk=pk)

    media_root = settings.DATA_ROOT.resolve()
    path = (media_root / video.video_loc).resolve()
    if path.is_relative_to(media_root) and path.is_file():
        delete_path = path.parent if path.parent != media_root else path
        try:
            if delete_path.is_dir():
                shutil.rmtree(delete_path)
            else:
                delete_path.unlink()
        except OSError as error:
            return JsonResponse(
                {"error": f"Could not delete video files: {error}"}, status=400
            )

    video.delete()
    return JsonResponse({"deleted": True})


@login_required(login_url="login")
@require_POST
def add_video_comment(request, pk):
    video = get_object_or_404(Video, pk=pk)
    Comment.objects.create(
        video=video,
        author=request.user,
        source_id=str(uuid4()),
        timestamp=timezone.now(),
        text=request.POST.get("text", ""),
    )
    messages.success(request, "Your comment has been posted.")
    return redirect("video-detail", pk=video.pk)
