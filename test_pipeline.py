"""Quick test of the full pipeline - thumbnail + youtube."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from social_uploader import generate_thumbnail_hf, upload_to_youtube

def log(msg):
    print(f"  >> {msg.get('message', msg)}")

# 1. Test thumbnail generation
print("=" * 50)
print("TEST 1: Pollinations.ai Thumbnail Generation")
print("=" * 50)
video = "/Users/shouryabafna/Desktop/Class/Automation/static/uploads/2026-07-13T22_57_54.mp4"
thumb = generate_thumbnail_hf("Minecraft rare items gameplay", video, progress_callback=log)
print(f"Thumbnail result: {thumb}")
print(f"Thumbnail exists: {os.path.exists(thumb)}")
print(f"Thumbnail size: {os.path.getsize(thumb)} bytes")

# 2. Test YouTube upload
print("\n" + "=" * 50)
print("TEST 2: YouTube Upload")
print("=" * 50)
url = upload_to_youtube(video, "Pipeline Test - Delete Me", "Testing upload pipeline", ["test"], thumb, progress_callback=log)
print(f"YouTube URL: {url}")
