import json
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
root = project_root / "media"
VIDEO_KEYS_TO_DROP = set("""
automatic_captions formats heatmap id channel_id age_limit playable_in_embed
live_status media_type _format_sort_fields subtitles channel_url epoch was_live
is_live fulltitle display_id
extractor_key extractor webpage_url_domain webpage_url_basename availability
uploader format format_id
ext protocol language format_note filesize_approx tbr width dynamic_range fps
height vbr vcodec aspect_ratio acodec abr asr audio_channels _type _version
n_entries timestamp duration_string thumbnails
""".split())
COMMENT_KEYS_TO_DROP = {"_time_text", "author_is_uploader", "author_id", "author_is_verified", "is_favorited", "is_pinned"}
NESTED_ORDER = ("categories", "tags", "chapters", "comments")

def cleanup_media_files():
  removals = {
    path for path in root.rglob("*")
    if path.is_file() and (path.name == ".DS_Store" or path.name.endswith(".part"))
  }
  duplicate_pairs = 0
  for mp4 in root.rglob("*.mp4"):
    webm = mp4.with_suffix(".webm")
    if not webm.is_file():
      continue
    mp4_size = mp4.stat().st_size
    webm_size = webm.stat().st_size
    if mp4_size > webm_size:
      removals.add(mp4)
      duplicate_pairs += 1
    elif webm_size > mp4_size:
      removals.add(webm)
      duplicate_pairs += 1

  for path in sorted(removals):
    path.unlink()
  print(
    f"Removed {len(removals)} media files: "
    f"{sum(path.name == '.DS_Store' for path in removals)} .DS_Store, "
    f"{sum(path.name.endswith('.part') for path in removals)} .part, "
    f"{duplicate_pairs} larger duplicate video formats"
  )

def format_date(value):
  if not isinstance(value, str):
    return value
  digits = "".join(char for char in value if char.isdigit())
  if len(digits) != 8:
    return value
  try:
    return datetime.strptime(digits, "%Y%m%d").date().isoformat()
  except ValueError:
    return value

cleanup_media_files()

for path in root.rglob("*.json"):
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    print(f"Skipped invalid JSON: {path}")
    continue
  if not isinstance(data, dict):
    print(f"Skipped non-dict JSON: {path}")
    continue

  # yt-dlp treats a channel's /videos page as a playlist. Those entries are
  # ordinary videos, so remove the feed-only playlist fields while preserving
  # playlist metadata for videos that belong to a real playlist.
  playlist_title = data.get("playlist_title")
  if isinstance(playlist_title, str) and playlist_title.rstrip().lower().endswith(" - videos"):
    for key in tuple(data):
      if key == "playlist" or key.startswith("playlist_"):
        data.pop(key, None)

  for key in VIDEO_KEYS_TO_DROP:
    data.pop(key, None)
  for comment in data.get("comments") or []:
    if not isinstance(comment, dict):
      continue
    for key in COMMENT_KEYS_TO_DROP:
      comment.pop(key, None)
    if isinstance(comment.get("timestamp"), (int, float)):
      comment["timestamp"] = datetime.fromtimestamp(comment["timestamp"], timezone.utc).isoformat()

  for key in ("modified_date", "upload_date"):
    if data.get(key):
      data[key] = format_date(data[key])

  # Playlist records use the `000 - <title>` basename and carry
  # modified_date. Their thumbnail may be jpg or webp; playlist videos use
  # the same sidecar naming convention but retain their playlist fields.
  if data.get("modified_date"):
    basename = path.name.removesuffix(".info.json")
    thumbnail = next(
      (path.with_name(basename + extension) for extension in (".webp", ".jpg", ".jpeg")
       if path.with_name(basename + extension).is_file()),
      None,
    )
    if thumbnail:
      data["thumbnail_loc"] = str(thumbnail.relative_to(project_root))

  scalars = {key: value for key, value in data.items() if not isinstance(value, (list, dict))}
  nested = {key: data[key] for key in NESTED_ORDER if isinstance(data.get(key), (list, dict))}
  nested.update({key: value for key, value in data.items() if isinstance(value, (list, dict)) and key not in nested})
  path.write_text(json.dumps({**scalars, **nested}, indent=4, ensure_ascii=False), encoding="utf-8")
print("Formatted media JSON metadata")
