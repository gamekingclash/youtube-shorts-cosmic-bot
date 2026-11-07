import os
from pathlib import Path
import requests


def upload_to_facebook_reels(video_path: Path, description: str) -> str | None:
    """
    Uploads the rendered vertical MP4 directly to a Facebook Page as a Reel
    using the official Meta Graph API v21.0.
    """
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    page_token = os.getenv("FB_PAGE_TOKEN", "").strip()
    if not page_id or not page_token:
        print("[MULTI-PLATFORM] FB_PAGE_ID / FB_PAGE_TOKEN not set; skipping Facebook Reels upload.")
        return None

    try:
        print(f"[FACEBOOK REELS] Initializing Reel upload for Page {page_id}...")
        # Step 1: Initialize upload session
        init_url = f"https://graph.facebook.com/v21.0/{page_id}/video_reels"
        init_resp = requests.post(
            init_url,
            data={"upload_phase": "start", "access_token": page_token},
            timeout=20,
        )
        if init_resp.status_code != 200:
            print(f"[WARN] Facebook Reels init failed: {init_resp.text}")
            return None

        init_data = init_resp.json()
        video_id = init_data.get("video_id")
        upload_url = init_data.get("upload_url")

        # Step 2: Upload binary MP4 file to rupload.facebook.com
        file_size = video_path.stat().st_size
        with open(video_path, "rb") as f:
            up_resp = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {page_token}",
                    "offset": "0",
                    "file_size": str(file_size),
                },
                data=f,
                timeout=120,
            )
        if up_resp.status_code != 200:
            print(f"[WARN] Facebook Reels binary upload failed: {up_resp.text}")
            return None

        # Step 3: Publish the Reel
        pub_resp = requests.post(
            init_url,
            data={
                "access_token": page_token,
                "video_id": video_id,
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "description": description,
            },
            timeout=30,
        )
        if pub_resp.status_code == 200:
            fb_url = f"https://www.facebook.com/reel/{video_id}"
            print(f"[SUCCESS] Published to Facebook Reels: {fb_url}")
            return fb_url
        else:
            print(f"[WARN] Facebook Reels finish phase failed: {pub_resp.text}")
    except Exception as exc:
        print(f"[WARN] Facebook Reels upload exception: {exc}")
    return None


def upload_to_tiktok(video_path: Path, title: str) -> bool:
    """
    Uploads the rendered MP4 to TikTok via TikTok Content Posting API v2.
    """
    access_token = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    if not access_token:
        print("[MULTI-PLATFORM] TIKTOK_ACCESS_TOKEN not set; skipping TikTok upload.")
        return False

    try:
        file_size = video_path.stat().st_size
        init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        payload = {
            "post_info": {
                "title": title[:150],
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": file_size,
                "total_chunk_count": 1,
            },
        }
        r = requests.post(init_url, headers=headers, json=payload, timeout=20)
        if r.status_code != 200:
            print(f"[WARN] TikTok init failed: {r.text}")
            return False

        upload_url = r.json().get("data", {}).get("upload_url")
        if not upload_url:
            return False

        with open(video_path, "rb") as f:
            up = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                    "Content-Type": "video/mp4",
                },
                data=f,
                timeout=120,
            )
        if up.status_code in (200, 201):
            print("[SUCCESS] Video uploaded to TikTok!")
            return True
    except Exception as exc:
        print(f"[WARN] TikTok upload exception: {exc}")
    return False
