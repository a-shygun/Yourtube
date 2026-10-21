from django.urls import path
from .views import (
    library_import,
    stream_video,
    PlaylistDetailView,
    VideoListView,
    CategoryVideosView,
    ChannelVideosView,
    add_video_comment,
    toggle_video_watch_status,
    VideoDetailView,
)

urlpatterns = [
    path("library/import/", library_import, name="library-import"),
    path("", VideoListView.as_view(), name="home"),
    path("category/<int:pk>/", CategoryVideosView.as_view(), name="category-videos"),
    path("channel/<int:pk>/", ChannelVideosView.as_view(), name="channel-videos"),
    path("video/<int:pk>/", VideoDetailView.as_view(), name="video-detail"),
    path("video/<int:pk>/stream/", stream_video, name="video-stream"),
    path("video/<int:pk>/watch-status/", toggle_video_watch_status, name="video-watch-status"),
    path("video/<int:pk>/comment/", add_video_comment, name="video-comment"),
    path("playlist/<int:pk>/", PlaylistDetailView.as_view(), name="playlist-detail"),
]
