import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
BASE_DIR = Path(__file__).resolve().parent
CLIENT_SECRETS_FILE = BASE_DIR / "client_secrets.json"
TOKEN_FILE = BASE_DIR / "token.json"


def get_authenticated_service():
    """
    Authenticates with YouTube Data API v3.
    Supports:
    1. Reading from TOKEN_JSON environment variable directly (GitHub Secrets)
    2. Reading from local token.json file
    3. Auto-refreshing expired tokens
    """
    creds = None

    # 1. Try from environment variable TOKEN_JSON
    env_token = os.getenv("TOKEN_JSON", "").strip()
    if env_token:
        try:
            token_dict = json.loads(env_token)
            creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
            print("[AUTH] Loaded YouTube credentials from TOKEN_JSON environment variable.")
        except Exception as e:
            print(f"[WARN] Failed to parse TOKEN_JSON env: {e}")

    # 2. Try from local token.json file
    if not creds and TOKEN_FILE.exists() and TOKEN_FILE.stat().st_size > 20:
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            print("[AUTH] Loaded YouTube credentials from token.json file.")
        except Exception as e:
            print(f"[WARN] Failed to parse token.json file: {e}")

    # 3. If credentials found, validate or refresh
    if creds:
        if creds.expired and creds.refresh_token:
            print("[AUTH] Refreshing expired YouTube OAuth token...")
            creds.refresh(Request())
            try:
                with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            except Exception:
                pass
        return build("youtube", "v3", credentials=creds)

    # 4. Fallback to client_secrets if interactive desktop
    env_client = os.getenv("CLIENT_SECRETS_JSON", "").strip()
    if env_client:
        try:
            client_config = json.loads(env_client)
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
            return build("youtube", "v3", credentials=creds)
        except Exception as e:
            print(f"[WARN] Failed to use CLIENT_SECRETS_JSON env: {e}")

    if CLIENT_SECRETS_FILE.exists() and CLIENT_SECRETS_FILE.stat().st_size > 20:
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE), SCOPES)
        creds = flow.run_local_server(port=0)
        return build("youtube", "v3", credentials=creds)

    raise ValueError(
        "YouTube authorization token not found! "
        "Please ensure TOKEN_JSON secret is added in GitHub Repository Settings -> Secrets and variables -> Actions."
    )


def upload_shorts_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str] = None,
    privacy_status: str = "scheduled",
    schedule_hours: float = 2.0,
) -> str:
    """
    Uploads a vertical MP4 video to YouTube with title, description, and tags.
    Returns the YouTube Shorts URL.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    youtube = get_authenticated_service()

    if tags is None:
        tags = ["shorts", "viral", "facts", "trending"]

    # Ensure #shorts is in the title for guaranteed Shorts indexing
    if "#shorts" not in title.lower():
        title = f"{title[:90]} #shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "22",  # People & Blogs / Entertainment
        },
        "status": {
            "privacyStatus": "private" if privacy_status == "scheduled" else privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    if privacy_status == "scheduled":
        from datetime import datetime, timedelta, timezone

        publish_time = datetime.now(timezone.utc) + timedelta(hours=schedule_hours)
        body["status"]["publishAt"] = publish_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        print(
            f"[YOUTUBE] Video scheduled to automatically go PUBLIC at: "
            f"{publish_time.strftime('%Y-%m-%d %H:%M:%S UTC')} ({schedule_hours} hours from now)."
        )

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,  # 5MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(f"[YOUTUBE] Uploading '{title}' to your channel...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YOUTUBE] Upload progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    shorts_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[SUCCESS] Video successfully uploaded to YouTube!")
    print(f"[LINK] {shorts_url}")
    return shorts_url


if __name__ == "__main__":
    import sys

    # Quick test helper: python uploader.py <video_path> <metadata_json_path>
    if len(sys.argv) > 2:
        v_file = Path(sys.argv[1])
        m_file = Path(sys.argv[2])
        with open(m_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        upload_shorts_video(v_file, meta["title"], meta["description"])
    else:
        print("Usage: python uploader.py <path_to_video.mp4> <path_to_metadata.json>")
