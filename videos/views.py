import mimetypes
from io import StringIO
from pathlib import Path
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import CommandError
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import CharField, F, OuterRef, Prefetch, Subquery, Value
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView
from videos.management.media_location import CONFIG_PATH, get_media_root
from videos.management.import_youtube import Command as ImportYouTubeCommand
from .models import Channel, Category, Comment, Playlist, Video, VideoStatus, media_file_path


@login_required(login_url="login")
def library_import(request):
    if request.method == "POST":
        media_directory = request.POST.get("media_directory", "")
        output = StringIO()
        try:
            media_root = Path(media_directory).expanduser().resolve()
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(str(media_root), encoding="utf-8")
            ImportYouTubeCommand(stdout=output).handle()
        except (CommandError, OSError) as error:
            messages.error(request, f"Import failed: {error} Please check the folder path and try again.")
        else:
            messages.success(request, output.getvalue().strip() or "Your library was refreshed.")

        return redirect("library-import")

    return render(request, "videos/library_import.html", {"media_directory": str(get_media_root() or "")})


@require_GET
def library_media_file(request, relative_path):
    """Serve only thumbnails referenced by a video or playlist record."""
    referenced = Video.objects.filter(thumbnail_loc=relative_path).exists() or Playlist.objects.filter(thumbnail_loc=relative_path).exists()
    if not referenced:
        return HttpResponse(status=404)
    path = media_file_path(relative_path)
    if not path:
        return HttpResponse(status=404)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path.open("rb"), content_type=content_type)


class VideoListView(ListView):
    model = Video
    template_name = "videos/video_list.html"
    paginate_by = 16

    def get_listing(self):
        return Video.objects.all(), "", "home", None

    def get_queryset(self):
        videos, self.listing_title, self.listing_type, self.listing_id = self.get_listing()
        self.search_query = self.request.GET.get("q", "")
        self.sort_order = self.request.GET.get("sort", "latest")
        if self.search_query:
            videos = videos.filter(title__icontains=self.search_query)

        order_by = {
            "popular": ("-view_count", "-upload_date", "-pk"),
            "oldest": ("upload_date", "pk"),
        }.get(self.sort_order, ("-upload_date", "-pk"))

        if self.request.user.is_authenticated:
            videos = videos.annotate(
                user_status=Subquery(
                    VideoStatus.objects.filter(video=OuterRef("pk"), user=self.request.user)
                    .values("status")[:1]
                )
            )
        else:
            videos = videos.annotate(user_status=Value("", output_field=CharField()))

        return videos.order_by(*order_by).values(
            "id",
            "title",
            "thumbnail_loc",
            "view_count",
            "duration",
            "channel_id",
            "user_status",
            date=F("upload_date"),
            channel_name=F("channel__name"),
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
    def get_listing(self):
        category = get_object_or_404(Category, pk=self.kwargs["pk"])
        return Video.objects.filter(categories=category).distinct(), category.name, "category", category.pk


class ChannelVideosView(VideoListView):
    def get_listing(self):
        channel = get_object_or_404(Channel, pk=self.kwargs["pk"])
        return Video.objects.filter(channel=channel), channel.name, "channel", channel.pk


class PlaylistDetailView(DetailView):
    model = Playlist

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        video_list = self.object.video_set.select_related("channel").order_by("position_in_playlist", "pk")
        if self.request.user.is_authenticated:
            video_list = video_list.annotate(
                user_status=Subquery(
                    VideoStatus.objects.filter(video=OuterRef("pk"), user=self.request.user)
                    .values("status")[:1]
                )
            )
        context["video_list"] = video_list
        return context


class VideoDetailView(DetailView):
    model = Video

    def get_queryset(self):
        return super().get_queryset().select_related("channel", "playlist").prefetch_related("categories")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        video = self.object
        replies = Comment.objects.select_related("author__account").order_by("-timestamp")
        root_comments = (
            video.comment_set.filter(parent__isnull=True)
            .select_related("author__account")
            .prefetch_related(Prefetch("replies", queryset=replies, to_attr="reply_list"))
            .order_by("-timestamp")
        )
        context.update(
            local_video_available=media_file_path(video.video_loc) is not None,
            comments_count=video.comment_set.count(),
            root_comments=root_comments,
        )
        if self.request.user.is_authenticated:
            context["video_status"] = VideoStatus.objects.filter(
                video=video,
                user=self.request.user,
            ).values_list("status", flat=True).first() or ""
        return context


@login_required(login_url="login")
@require_POST
def set_video_status(request, pk):
    video = get_object_or_404(Video, pk=pk)
    status = request.POST.get("status", "")
    if status:
        VideoStatus.objects.update_or_create(
            video=video,
            user=request.user,
            defaults={"status": status},
        )
    else:
        VideoStatus.objects.filter(video=video, user=request.user).delete()
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("video-detail", pk=video.pk)


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
