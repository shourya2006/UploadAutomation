import os
import requests
import json
import time
import threading
import http.server
import socketserver
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google import genai
from google.genai import types
from groq import Groq

# Scopes needed for YouTube upload
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def log_progress(callback, msg_type, **kwargs):
    if callback:
        kwargs["type"] = msg_type
        callback(kwargs)
    else:
        print(f"[{msg_type.upper()}] {kwargs.get('message', '')}")

def extract_thumbnail(video_path: str, progress_callback=None) -> str:
    """Extracts a frame from the middle of the video using ffmpeg as a fallback."""
    thumbnail_path = video_path.rsplit(".", 1)[0] + "_thumbnail.jpg"
    msg = f"Fallback: Extracting thumbnail to {thumbnail_path} using ffmpeg..."
    log_progress(progress_callback, "log", message=msg)
    
    try:
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", video_path]
        duration_str = subprocess.check_output(duration_cmd).strip().decode()
        duration = float(duration_str)
        mid_point = duration / 2.0
        
        extract_cmd = ["ffmpeg", "-y", "-ss", str(mid_point), "-i", video_path, "-vframes", "1", "-q:v", "2", thumbnail_path]
        subprocess.run(extract_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_progress(progress_callback, "log", message="Fallback thumbnail extracted successfully.")
        log_progress(progress_callback, "thumbnail", path=f"/static/uploads/{os.path.basename(thumbnail_path)}")
        return thumbnail_path
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Error extracting fallback thumbnail: {e}")
        return None

def ensure_vertical_video(video_path: str, progress_callback=None) -> str:
    """
    Checks if a video is 9:16 vertical. If not, reformats it using ffmpeg
    with a blurred background padding.
    """
    log_progress(progress_callback, "log", message="Checking video aspect ratio...")
    
    try:
        # Check aspect ratio
        cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", video_path]
        output = subprocess.check_output(cmd).strip().decode()
        width_str, height_str = output.split("x")
        width, height = int(width_str), int(height_str)
        
        # Calculate aspect ratio
        aspect_ratio = width / height
        target_ratio = 9 / 16
        
        # If it's already approximately 9:16 (within 5% margin), skip
        if abs(aspect_ratio - target_ratio) < 0.05:
            log_progress(progress_callback, "log", message="Video is already 9:16 vertical.")
            return video_path
            
        log_progress(progress_callback, "log", message="Video is not 9:16. Auto-reformatting with blurred background (this may take a moment)...")
        
        # Generate new filename
        out_path = video_path.rsplit(".", 1)[0] + "_vertical.mp4"
        
        # Complex filter string for blurred background:
        # 1. Scale background to 1080x1920 (crop to fill) and blur heavily
        # 2. Scale foreground to fit within 1080x1920 while maintaining aspect ratio
        # 3. Overlay foreground on top of background
        vf_string = (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=luma_radius=min(h\\,w)/20:luma_power=1:chroma_radius=min(cw\\,ch)/20:chroma_power=1[bg];"
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-filter_complex", vf_string,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            out_path
        ]
        
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_progress(progress_callback, "log", message="Successfully reformatted video to 9:16!")
        return out_path
        
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Warning: Failed to reformat video: {e}. Proceeding with original.")
        return video_path

def generate_thumbnail_hf(prompt: str, video_path: str, progress_callback=None) -> str:
    """Uses Pollinations.ai POST API to generate a YouTube thumbnail."""
    log_progress(progress_callback, "log", message="Generating AI Thumbnail with Pollinations.ai...")
    
    try:
        payload = {
            "prompt": f"Highly engaging clickbait YouTube thumbnail, no text, topic: {prompt}. Cinematic, 4k, vibrant colors, high contrast.",
            "width": 1280,
            "height": 720,
            "model": "flux",
            "nologo": True,
            "seed": 42
        }
        
        response = requests.post(
            "https://image.pollinations.ai/",
            json=payload,
            timeout=90
        )
        
        if response.status_code != 200 or 'image' not in response.headers.get('content-type', ''):
            raise Exception(f"Pollinations API Error: status={response.status_code}, content-type={response.headers.get('content-type')}")
            
        thumb_path = video_path.rsplit(".", 1)[0] + "_thumbnail.jpg"
        with open(thumb_path, 'wb') as f:
            f.write(response.content)
        
        # Verify we got a real image (at least 5KB)
        if os.path.getsize(thumb_path) < 5000:
            raise Exception(f"Generated image too small ({os.path.getsize(thumb_path)} bytes), likely an error page")
            
        log_progress(progress_callback, "log", message="AI Thumbnail generated successfully!")
        log_progress(progress_callback, "thumbnail", path=f"/static/uploads/{os.path.basename(thumb_path)}")
        return thumb_path
        
    except Exception as e:
        log_progress(progress_callback, "log", message=f"AI Thumbnail Generation Error: {e}")
        log_progress(progress_callback, "log", message="Falling back to video frame extraction.")
        return extract_thumbnail(video_path, progress_callback)

def optimize_metadata(brief_description: str, progress_callback=None) -> dict:
    """Uses Groq to generate SEO metadata."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log_progress(progress_callback, "log", message="Warning: GROQ_API_KEY not set. Using original description.")
        return {
            "title": brief_description[:90],
            "description": brief_description,
            "tags": ["AI", "Video"]
        }
        
    client = Groq(api_key=api_key)
    log_progress(progress_callback, "log", message="Generating SEO metadata with Groq...")
    
    prompt = f"Optimize this brief video description for YouTube/Instagram/Facebook SEO: '{brief_description}'. Return exactly a JSON object with 'title' (catchy, max 80 chars), 'description' (detailed, SEO friendly, includes 3 hashtags), and 'tags' (list of 5-10 relevant string keywords). Do not include markdown formatting or any other text, just raw JSON."
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a social media expert who outputs ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        metadata = json.loads(response.choices[0].message.content)
        log_progress(progress_callback, "log", message=f"Generated SEO Title: {metadata.get('title')}")
        log_progress(progress_callback, "metadata", metadata=metadata)
        return metadata
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Groq Metadata Error: {e}")
        return {
            "title": brief_description[:90],
            "description": brief_description,
            "tags": ["AI", "Video"]
        }

def upload_to_youtube(video_path: str, title: str, description: str, tags: list, thumbnail_path: str, progress_callback=None):
    """
    Uploads a video to YouTube using OAuth 2.0 flow.
    Requires client_secrets.json in the project root.
    """
    log_progress(progress_callback, "log", message="Initiating YouTube Upload...")
    
    _dir = os.path.dirname(os.path.abspath(__file__))
    client_secrets_path = os.path.join(_dir, "client_secrets.json")
    token_path = os.path.join(_dir, "token.json")
    
    if not os.path.exists(client_secrets_path):
        log_progress(progress_callback, "log", message="Warning: client_secrets.json not found. Skipping YouTube upload.")
        return None
        
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        credentials = None
        if os.path.exists(token_path):
            credentials = Credentials.from_authorized_user_file(token_path, YOUTUBE_SCOPES)
            
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                log_progress(progress_callback, "log", message="YouTube auth required. Please run 'python auth_yt.py' first!")
                return None
            # Save refreshed credentials
            with open(token_path, 'w') as token:
                token.write(credentials.to_json())
                
        youtube = build("youtube", "v3", credentials=credentials)
        
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22" # People & Blogs
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }
        
        # Upload
        log_progress(progress_callback, "log", message=f"Uploading {video_path} to YouTube...")
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                log_progress(progress_callback, "log", message=f"Uploaded {int(status.progress() * 100)}% to YouTube")
                
        video_id = response['id']
        log_progress(progress_callback, "log", message=f"YouTube Upload Complete! Video ID: {video_id}")
        
        if thumbnail_path and os.path.exists(thumbnail_path):
            log_progress(progress_callback, "log", message=f"Uploading custom thumbnail from {thumbnail_path}...")
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumbnail_path)
                ).execute()
                log_progress(progress_callback, "log", message="Thumbnail uploaded successfully.")
            except Exception as thumb_e:
                log_progress(progress_callback, "log", message=f"Thumbnail upload failed (Shorts do not support custom thumbnails): {thumb_e}")
            
        return f"https://youtu.be/{video_id}"
    except Exception as e:
        log_progress(progress_callback, "log", message=f"YouTube Upload Error: {e}")
        return None

def upload_to_facebook(video_path: str, description: str, progress_callback=None):
    """
    Uploads a video to a Facebook Page using the Graph API.
    """
    page_id = os.getenv("FACEBOOK_PAGE_ID")
    access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not page_id or not access_token:
        log_progress(progress_callback, "log", message="Warning: FACEBOOK_PAGE_ID or FACEBOOK_PAGE_ACCESS_TOKEN not set. Skipping FB upload.")
        return
        
    log_progress(progress_callback, "log", message=f"Uploading {video_path} to Facebook Page...")
    
    url = f"https://graph.facebook.com/v19.0/{page_id}/videos"
    
    payload = {
        'description': description,
        'access_token': access_token
    }
    
    try:
        with open(video_path, 'rb') as f:
            files = {'source': f}
            response = requests.post(url, data=payload, files=files)
            
        result = response.json()
        if 'id' in result:
            log_progress(progress_callback, "log", message=f"Facebook upload successful! Video ID: {result['id']}")
        else:
            log_progress(progress_callback, "log", message=f"Facebook upload failed: {result}")
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Facebook Upload Error: {e}")

class _QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress logs

def _start_local_server(port, directory):
    os.chdir(directory)
    handler = _QuietHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

def upload_to_instagram(video_path: str, description: str, progress_callback=None):
    """
    Uploads a video to Instagram Reels.
    Uses ngrok to temporarily host the video on a public URL.
    """
    ig_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    access_token = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
    
    if not ig_account_id or not access_token:
        log_progress(progress_callback, "log", message="Warning: INSTAGRAM_ACCOUNT_ID or FACEBOOK_PAGE_ACCESS_TOKEN not set. Skipping IG upload.")
        return
        
    log_progress(progress_callback, "log", message="Initiating Instagram Reels Upload...")
    
    # Setup temporary public URL using ngrok
    video_dir = os.path.dirname(os.path.abspath(video_path))
    video_filename = os.path.basename(video_path)
    port = 8090
    
    # Determine if we are on Render or local
    public_url_base = os.getenv("RENDER_EXTERNAL_URL")
    ngrok_tunnel = None
    httpd = None
    
    if public_url_base:
        # We are on Render, use its public URL. Files are saved in static/uploads
        public_video_url = f"{public_url_base}/static/uploads/{video_filename}"
        log_progress(progress_callback, "log", message=f"Using Render public URL: {public_video_url}")
    else:
        # We are local, fallback to ngrok
        log_progress(progress_callback, "log", message="Starting local server and ngrok tunnel to generate public URL for Instagram...")
        httpd = _start_local_server(port, video_dir)
        try:
            from pyngrok import ngrok, conf
            pyngrok_config = conf.PyngrokConfig(ngrok_path="/opt/homebrew/bin/ngrok")
            ngrok_tunnel = ngrok.connect(port, bind_tls=True, pyngrok_config=pyngrok_config)
            public_video_url = f"{ngrok_tunnel.public_url}/{video_filename}"
            log_progress(progress_callback, "log", message=f"Generated temporary ngrok URL: {public_video_url}")
        except ImportError:
            log_progress(progress_callback, "log", message="Error: pyngrok is not installed and RENDER_EXTERNAL_URL is missing. Skipping IG upload.")
            if httpd:
                httpd.shutdown()
                httpd.server_close()
            return
        
    try:
        # Step 1: Create media container
        url_create = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
        payload_create = {
            'media_type': 'REELS',
            'video_url': public_video_url,
            'caption': description,
            'share_to_feed': 'true',
            'access_token': access_token
        }
        
        log_progress(progress_callback, "log", message="Creating Instagram Media Container...")
        response_create = requests.post(url_create, data=payload_create).json()
        
        if 'error' in response_create:
            log_progress(progress_callback, "log", message=f"IG Container Creation Failed: {response_create['error']}")
            return
            
        container_id = response_create['id']
        log_progress(progress_callback, "log", message=f"Container Created! ID: {container_id}. Polling for processing completion...")
        
        # Step 2: Poll status
        url_status = f"https://graph.facebook.com/v19.0/{container_id}"
        params_status = {
            'fields': 'status_code',
            'access_token': access_token
        }
        
        ready_to_publish = False
        for _ in range(180): # Poll up to 15 minutes
            response_status = requests.get(url_status, params=params_status).json()
            status = response_status.get('status_code')
            
            if status == 'FINISHED':
                ready_to_publish = True
                break
            elif status == 'ERROR':
                log_progress(progress_callback, "log", message="IG Video processing encountered an error.")
                return
                
            log_progress(progress_callback, "log", message=f"IG Status: {status}... waiting 5s.")
            time.sleep(5)
            
        if not ready_to_publish:
            log_progress(progress_callback, "log", message="Timeout waiting for IG video processing.")
            return
            
        # Step 3: Publish
        log_progress(progress_callback, "log", message="Video processed. Publishing reel...")
        url_publish = f"https://graph.facebook.com/v19.0/{ig_account_id}/media_publish"
        payload_publish = {
            'creation_id': container_id,
            'access_token': access_token
        }
        
        response_publish = requests.post(url_publish, data=payload_publish).json()
        
        if 'id' in response_publish:
            log_progress(progress_callback, "log", message=f"Instagram Reels upload successful! Post ID: {response_publish['id']}")
        else:
            log_progress(progress_callback, "log", message=f"IG Publish Failed: {response_publish}")
            
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Instagram Upload Error: {e}")
    finally:
        # Cleanup
        if not public_url_base:
            log_progress(progress_callback, "log", message="Shutting down ngrok tunnel and local server...")
            if ngrok_tunnel:
                try:
                    from pyngrok import ngrok
                    ngrok.disconnect(ngrok_tunnel.public_url)
                    ngrok.kill()
                except Exception:
                    pass
            if httpd:
                httpd.shutdown()
                httpd.server_close()

def publish_all(video_path: str, brief_description: str, thumbnail_path: str=None, progress_callback=None):
    log_progress(progress_callback, "log", message="--- Pre-processing Video ---")
    original_video_path = video_path
    vertical_video_path = ensure_vertical_video(video_path, progress_callback)
    
    log_progress(progress_callback, "log", message="--- Starting AI Metadata Optimization ---")
    
    # AI Optimization Step
    metadata = optimize_metadata(brief_description, progress_callback)
    title = metadata.get("title", brief_description[:90])
    description = metadata.get("description", brief_description)
    tags = metadata.get("tags", ["AI", "Shorts"])
    
    if thumbnail_path:
        log_progress(progress_callback, "log", message="Using provided frontend Puter thumbnail.")
        log_progress(progress_callback, "thumbnail", path=f"/static/uploads/{os.path.basename(thumbnail_path)}")
    else:
        # AI Thumbnail Generation Step (Hugging Face) or fallback
        # Use ORIGINAL video path for thumbnail extraction so it retains original aspect ratio
        thumbnail_path = generate_thumbnail_hf(brief_description, original_video_path, progress_callback)
    
    log_progress(progress_callback, "log", message="--- Starting Social Media Uploads ---")
    
    # 1. Instagram Upload (Uses vertical 9:16)
    try:
        upload_to_instagram(vertical_video_path, description, progress_callback)
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Instagram upload failed: {e}. Skipping to next platform.")
    
    # 2. Facebook Upload (Uses original)
    try:
        upload_to_facebook(original_video_path, description, progress_callback)
    except Exception as e:
        log_progress(progress_callback, "log", message=f"Facebook upload failed: {e}. Skipping to next platform.")
    
    # 3. YouTube Upload (Uses original)
    yt_url = None
    try:
        yt_url = upload_to_youtube(original_video_path, title, description, tags, thumbnail_path, progress_callback)
        if yt_url:
            log_progress(progress_callback, "log", message=f"YouTube URL: {yt_url}")
    except Exception as e:
        log_progress(progress_callback, "log", message=f"YouTube upload failed: {e}.")
        
    # 4. Cleanup Cache Files
    log_progress(progress_callback, "log", message="--- Cleaning Up Cached Files ---")
    files_to_remove = [original_video_path, vertical_video_path, thumbnail_path]
    for file_path in set(files_to_remove):
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                log_progress(progress_callback, "log", message=f"Removed: {os.path.basename(file_path)}")
            except Exception as e:
                log_progress(progress_callback, "log", message=f"Failed to remove {file_path}: {e}")

    return yt_url

if __name__ == "__main__":
    print("Social uploader module loaded.")
    # Example usage:
    # publish_all("/path/to/video.mp4", "A cool AI generated video about spaceships")
