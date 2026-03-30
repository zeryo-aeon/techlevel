import os
import json
import time
import dotenv
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound
)
from agent import get_engine, save_tasks_to_json
from pytube import Playlist

dotenv.load_dotenv()

# =========================
# CONFIG
# =========================
TRANSCRIPT_DIR = "transcripts"
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

MAX_VIDEOS = -1  # limit for testing

# =========================
# ENGINE SETUP
# =========================
config = {
    "provider": "ollama",
    "ollama_model": "qwen2.5:3b",
    "system_prompt": "You extract actionable tasks from transcripts."
}

if os.getenv("GROQ_API_KEY"):
    config = {
        "provider": "groq",
        "groq_api_key": os.getenv("GROQ_API_KEY"),
        "groq_model": "llama-3.1-8b-instant",
        "system_prompt": "You extract actionable tasks from transcripts."
    }

engine = get_engine(config)

# =========================
# FILE HELPERS
# =========================
def transcript_path(video_id):
    return os.path.join(TRANSCRIPT_DIR, f"{video_id}.json")


def load_local_transcript(video_id):
    path = transcript_path(video_id)

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate structure
        if not isinstance(data, list) or len(data) == 0 or "text" not in data[0]:
            raise ValueError("Invalid transcript format")

        print("📂 Loaded cached transcript")
        return data

    except Exception as e:
        print(f"⚠️ Corrupted cache detected → deleting: {e}")
        try:
            os.remove(path)
        except:
            pass
        return None


def save_local_transcript(video_id, data):
    path = transcript_path(video_id)
    temp_path = path + ".tmp"

    try:
        # Convert to JSON-safe format
        serializable_data = [
            {
                "text": t.text,
                "start": t.start,
                "duration": t.duration
            }
            for t in data
        ]

        # Atomic write
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)

        os.replace(temp_path, path)

    except Exception as e:
        print(f"❌ Failed to save transcript: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)


# =========================
# TRANSCRIPT FETCHING
# =========================
def fetch_transcript_safe(video_id, retries=3):
    api = YouTubeTranscriptApi()

    for attempt in range(retries):
        try:
            print(f"🔍 Fetching transcript (attempt {attempt+1})...")
            transcript = api.fetch(video_id)
            print("✅ Transcript fetched")
            return transcript

        except (NoTranscriptFound, TranscriptsDisabled):
            print("⚠️ No transcript available")
            return None

        except Exception as e:
            print(f"⚠️ Retry due to error: {e}")
            time.sleep(2)

    print("❌ Failed after retries")
    return None


def get_transcript_text(video_id):
    # 1. Try cache
    local_data = load_local_transcript(video_id)
    if local_data:
        return " ".join([t["text"] for t in local_data])

    # 2. Fetch from API
    transcript_data = fetch_transcript_safe(video_id)
    if not transcript_data:
        return None

    # 3. Save safely
    save_local_transcript(video_id, transcript_data)

    # 4. Return text
    return " ".join([t.text for t in transcript_data])


# =========================
# MAIN PIPELINE
# =========================
def process_playlist(playlist_url):
    playlist = Playlist(playlist_url)

    print(f"\n📺 Total videos in playlist: {len(playlist.video_urls)}")

    for i, url in enumerate(playlist.video_urls):
        if  i >= MAX_VIDEOS :
            pass

        video_id = url.split("v=")[-1]
        print("\n" + "=" * 50)
        print(f"🎬 Processing Video {i+1}: {video_id}")

        # Get transcript
        transcript_text = get_transcript_text(video_id)

        if not transcript_text:
            print("⏭️ Skipping (no transcript)")
            continue

        print(f"📝 Transcript length: {len(transcript_text)} chars")

        output_file = f"tasks_{video_id}.json"

        # ✅ Skip if already exists
        if os.path.exists(output_file):
            print(f"⏭️ Tasks already exist → skipping: {output_file}")
            continue

        # Generate tasks
        try:
            tasks = engine.generate_tasks_from_transcript(video_id, transcript_text)

            if tasks:
                save_tasks_to_json(tasks, output_file)
                print(f"💾 Tasks saved → {output_file}")
            else:
                print("⚠️ No tasks generated")

        except Exception as e:
            print(f"❌ Task generation failed: {e}")


def generate_index_file():
    files = [
        f for f in os.listdir(".")
        if f.startswith("tasks_") and f.endswith(".json")
    ]

    with open("files.json", "w", encoding="utf-8") as f:
        json.dump(files, f, indent=2)

    print(f"📄 files.json generated with {len(files)} files")
# =========================
# RUN
# =========================
if __name__ == "__main__":
    playlist_url = "https://www.youtube.com/playlist?list=PL_qscgptXmW9HWSQJL9bk7VzsdTZk6S_i"
    process_playlist(playlist_url)
    generate_index_file() 