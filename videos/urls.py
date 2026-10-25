from django.urls import path
from videos.management.video_stream import stream_video
from .views import (
    library_import,
    library_media_file,
    PlaylistDetailView,
    VideoListView,
    CategoryVideosView,
    ChannelVideosView,
    add_video_comment,
    set_video_status,
    VideoDetailView,
)

urlpatterns = [
    path("", VideoListView.as_view(), name="home"),
    path("category/<int:pk>/", CategoryVideosView.as_view(), name="category-videos"),
    path("channel/<int:pk>/", ChannelVideosView.as_view(), name="channel-videos"),
    path("video/<int:pk>/", VideoDetailView.as_view(), name="video-detail"),
    path("playlist/<int:pk>/", PlaylistDetailView.as_view(), name="playlist-detail"),
    
    path("library/import/", library_import, name="library-import"),
    path("library/media/<path:relative_path>/", library_media_file, name="library-media"),
    path("video/<int:pk>/stream/", stream_video, name="video-stream"),
    path("video/<int:pk>/status/", set_video_status, name="video-status"),
    path("video/<int:pk>/comment/", add_video_comment, name="video-comment"),
]
