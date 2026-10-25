from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from videos.models import Video, media_file_path


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


def stream_video(request, pk):
    video = get_object_or_404(Video, pk=pk)
    video_path = media_file_path(video.video_loc)
    if not video_path:
        return HttpResponse(status=404)

    file_size = video_path.stat().st_size
    range_header = request.headers.get("Range", "")
    start, end = 0, file_size - 1
    status = 200
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
        status = 206

    length = end - start + 1
    content_type = "video/webm" if video_path.suffix.lower() == ".webm" else "video/mp4"
    response = StreamingHttpResponse(
        _read_file(video_path, start, length),
        status=status,
        content_type=content_type,
    )
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return response
