import requests
import urllib.parse


API_KEY = "your_api_key"


def extract_video_id(url: str) -> str:
    """Extract video ID from normal or short YouTube URL."""
    parsed = urllib.parse.urlparse(url)

    if parsed.hostname in ["youtu.be"]:
        return parsed.path[1:]

    if parsed.hostname in ["www.youtube.com", "youtube.com"]:
        query = urllib.parse.parse_qs(parsed.query)
        return query.get("v", [None])[0]

    return None


def get_live_chat_id(video_url: str):
    video_id = extract_video_id(video_url)

    if not video_id:
        print("❌ Could not extract video ID")
        return

    endpoint = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "liveStreamingDetails",
        "id": video_id,
        "key": API_KEY
    }

    response = requests.get(endpoint, params=params)
    data = response.json()

    if "items" not in data or not data["items"]:
        print("❌ Video not found")
        return

    details = data["items"][0].get("liveStreamingDetails", {})

    live_chat_id = details.get("activeLiveChatId")

    if live_chat_id:
        print("✅ Live Chat ID:")
        print(live_chat_id)
    else:
        print("❌ No active live chat found.")
        print("Is the stream currently LIVE?")


if __name__ == "__main__":
    url = input("Enter YouTube live URL: ")
    get_live_chat_id(url)