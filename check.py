import os
import time
import json
import requests
from yt_dlp import YoutubeDL
from datetime import datetime, timedelta
import tempfile

# Telegram credentials
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# YouTube Music artist channel
ARTIST_CHANNEL_URL = os.environ.get("ARTIST_CHANNEL_URL")

# Local paths
DOWNLOAD_DIR = "./downloads"
SENT_LOG_FILE = "sent_log.json"


def write_cookies_to_temp():
    cookie_str = os.getenv("COOKIE")
    if not cookie_str:
        raise ValueError("COOKIE environment variable not set.")

    temp_cookie_file = tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    )
    temp_cookie_file.write(cookie_str)
    temp_cookie_file.close()
    return temp_cookie_file.name


def send_file(bot_token, chat_id, file_path, caption):
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {
            "chat_id": chat_id,
            "caption": os.path.basename(file_path) + "\n" + caption,
        }
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendDocument",
            files=files,
            data=data,
        )
        (
            print("Sent:", file_path)
            if response.ok
            else print("Failed to send:", response.text)
        )


def load_sent_log():
    if os.path.exists(SENT_LOG_FILE):
        with open(SENT_LOG_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_log(sent_ids):
    with open(SENT_LOG_FILE, "w") as f:
        json.dump(list(sent_ids), f)


def get_latest_video():
    cookie_file = write_cookies_to_temp()
    ydl_opts = {
        "quiet": True,
        "cookiefile": cookie_file,
        "extract_flat": True,
        "dump_single_json": True,
        "playlist_items": "1",
    }
    with YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(ARTIST_CHANNEL_URL, download=False)
        if "entries" in result and result["entries"]:
            return result["entries"][0]  # Latest video
    return None


def download_file(video_url, output_dir, format_code):
    cookie_file = write_cookies_to_temp()
    ydl_opts = {
        "format": format_code,
        "cookiefile": cookie_file,
        "outtmpl": os.path.join(output_dir, "%(title)s.f" + format_code + ".%(ext)s"),
        "quiet": True,
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        file_path = (
            ydl.prepare_filename(info).replace(".webm", ".mp4")
            if format_code == "135"
            else ydl.prepare_filename(info)
        )
        return file_path, info.get("title", "No Title")


def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    sent_ids = load_sent_log()
    end_time = datetime.now() + timedelta(minutes=120)

    # send_file(BOT_TOKEN, CHAT_ID, "check.py", f"Test")
    # return

    while datetime.now() < end_time:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking for updates...")
            latest = get_latest_video()
            if latest:
                video_id = latest.get("id")
                video_title = latest.get("title", "")
                if video_id not in sent_ids:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    print(f"Found new video: {video_title}")

                    # Download video (135 = 480p no audio)
                    video_path, title = download_file(video_url, DOWNLOAD_DIR, "135")
                    send_file(BOT_TOKEN, CHAT_ID, video_path, f"{title}\n{video_url}")

                    # Download audio (140 = m4a)
                    audio_path, _ = download_file(video_url, DOWNLOAD_DIR, "140")
                    send_file(BOT_TOKEN, CHAT_ID, audio_path, f"{title}\n{video_url}")

                    sent_ids.add(video_id)
                    save_sent_log(sent_ids)
                    cleanup_temp_files([video_path, audio_path])
                else:
                    print("No new video.")
            else:
                print("Failed to fetch channel info.")
        except Exception as e:
            print("Error:", e)

        time.sleep(60)  # wait 1 minute

    print("Monitoring finished.")


def cleanup_temp_files(keep_files):
    keep_names = [os.path.basename(f) for f in keep_files]
    for f in os.listdir(DOWNLOAD_DIR):
        if f not in keep_names:
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, f))
            except:
                pass


if __name__ == "__main__":
    main()
