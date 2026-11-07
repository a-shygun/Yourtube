from django.urls import path
from .views import (
    VideoListView,
    CategoryVideosView,
    ChannelVideosView,
    add_video_comment,
    set_video_status,
    toggle_video_favorite,
    delete_video,
    VideoDetailView,
    serve_media,
    index_search_category,
    delete_user_category,
    remove_video_from_category,
)

urlpatterns = [
    path("", VideoListView.as_view(), name="home"),
    path("category/index/", index_search_category, name="category-index"),
    path("category/<int:pk>/delete/", delete_user_category, name="category-delete"),
    path("category/<int:pk>/video/<int:video_pk>/remove/", remove_video_from_category, name="category-video-remove"),
    path("category/<int:pk>/", CategoryVideosView.as_view(), name="category-videos"),
    path("channel/<int:pk>/", ChannelVideosView.as_view(), name="channel-videos"),
    path("video/<int:pk>/", VideoDetailView.as_view(), name="video-detail"),
    path("media/<path:path>", serve_media, name="media"),
    path("video/<int:pk>/status/", set_video_status, name="video-status"),
    path("video/<int:pk>/favorite/", toggle_video_favorite, name="video-favorite"),
    path("video/<int:pk>/delete/", delete_video, name="video-delete"),
    path("video/<int:pk>/comment/", add_video_comment, name="video-comment"),
]
