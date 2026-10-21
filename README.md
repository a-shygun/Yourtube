# YourTube

YourTube is a local Django app for organizing, searching, and watching your own YouTube video library. Each person runs a copy on their own computer. The database and downloaded video files stay local, so cloning the project does not include anyone's library.

![YourTube library in dark mode](screenshots/library-dark.png)

## Technologies

- **Python 3.12+** and **Django 6.1** for the application and server-rendered pages
- **SQLite** for the local database
- **yt-dlp** for downloading video files and metadata
- **Pillow** for image processing, including profile pictures
- **Django templates, HTML, Tailwind CSS, and JavaScript** for the frontend

## Run YourTube locally

Requirements: Python 3.12 or newer and internet access for yt-dlp downloads and YouTube embeds.

From the repository directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and register an account. The first run creates the local SQLite database and `media/` directory.

## Download and import videos

YouTube video files are large, so every user downloads their own library. Run YourTube locally on the computer where you want the files stored. A hosted copy of the site cannot save downloads onto a visitor's computer.

### Download from the Import page

1. Sign in and open **Import library**.
2. Make a plain text file with one video, playlist, or channel URL on each line. Blank lines and lines beginning with `#` are ignored.
3. Choose the text file and select **Download and import**. YourTube downloads videos, thumbnails, and yt-dlp info JSON files under `media/`, then imports channels, playlists, videos, tags, categories, and comments into the local database.

The built-in downloader uses yt-dlp's `--write-info-json`, `--write-thumbnail`, `--convert-thumbnails jpg`, `--write-comments`, `--no-overwrites`, `--merge-output-format mp4`, and `--yes-playlist` options. It does not read the user's yt-dlp configuration file. Install yt-dlp in the same Python environment as Django; it is included in `requirements.txt`.

### Download manually with yt-dlp

You can also use yt-dlp directly. Create `video-urls.txt` beside `media/`, with one URL per line. Install yt-dlp (for example, `brew install yt-dlp` on macOS), then create its configuration file:

```sh
mkdir -p ~/.config/yt-dlp
nano ~/.config/yt-dlp/config
```

Paste these options into the config file. The browser-cookie option is optional; use it when a video requires your browser's YouTube session, and change `safari` to a supported browser on your system.

```text
--cookies-from-browser safari
-f "bv[ext=mp4][height<=720]+ba[ext=m4a][language^=en]/b[ext=mp4][height<=720][language^=en]/bv[ext=webm][height<=720]+ba[ext=webm][language^=en]/b[ext=webm][height<=720][language^=en]"
--ignore-errors
--write-info-json
--write-comments
--extractor-args "youtube:max_comments=50"
--playlist-end 50
--write-thumbnail
--no-write-subs
--no-write-auto-subs
--no-embed-subs
-o "media/%(title)s - %(channel)s/%(title)s.%(ext)s"
```

This format prefers MP4 video with M4A audio up to 720p, prefers English audio, and falls back to compatible MP4 or WebM formats. `--playlist-end 50` limits a playlist or channel URL to its first 50 entries; remove that line to download every available entry. The comment option collects up to 50 comments per video. If your browser is not Safari, edit the cookie option or remove it.

Run yt-dlp on the URL list from the project directory:

```sh
yt-dlp -a video-urls.txt
```

When the downloads finish, sign in to YourTube, open **Import library**, and choose **Scan media/ and import**. This also works for compatible yt-dlp folders downloaded elsewhere: copy the folders into `media/` first and keep each video's `.info.json`, thumbnail, and media file together.

![Download and import instructions in YourTube](screenshots/import-guide.png)

### Expected media layout

The output template above creates a folder for each video. Keep the info JSON and thumbnail beside the matching video file. The importer scans nested folders and accepts common video and thumbnail extensions.

```text
Yourtube/
├── manage.py
├── db.sqlite3                 # created locally by Django
├── media/
│   ├── Video title - Channel/
│   │   ├── Video title.mp4
│   │   ├── Video title.info.json
│   │   └── Video title.jpg
│   └── Another video - Channel/
│       ├── Another video.webm
│       ├── Another video.info.json
│       └── Another video.webp
└── helper/
    └── data/                  # generated import data; rebuilt on import
```

Avoid renaming the sidecar files independently. Their shared filename lets the importer match metadata, thumbnail, and video. A valid `.info.json` is required for a video to be added to the database.

![YourTube video detail page](screenshots/video-detail.png)

## Local data and backups

`db.sqlite3` contains local accounts, profiles, comments, and watch status. `media/` contains downloaded video files, thumbnails, metadata, and uploaded profile images. Both are excluded from Git and are not included in a clone. Back them up separately to preserve your library.

`helper/data/` contains generated fixture JSON used by the import helpers. The importer rebuilds it from `media/`.

## Configuration

Local development defaults to Django debug mode and accepts requests from `localhost` and `127.0.0.1`. The fallback secret is for local development only. Set `DJANGO_SECRET_KEY` to use a different secret. To turn off debug mode, set `DJANGO_DEBUG=false` and configure `DJANGO_ALLOWED_HOSTS` as a comma-separated list.

These instructions are for local use. A public deployment needs separate configuration for secrets, allowed hosts, HTTPS, static and media storage, and upload limits.

## Screenshots

![YourTube library in light mode](screenshots/library-light.png)

## License

No license has been selected yet. Ask the project owner before redistributing this code or adding a license.
