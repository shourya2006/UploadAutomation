import os
from social_uploader import upload_to_youtube
import logging

logging.basicConfig(level=logging.INFO)

def test():
    video_path = "/Users/shouryabafna/Desktop/Class/Automation/static/uploads/Income_Tax_India_Simplified_60s_Summary.mp4"
    thumb_path = "/Users/shouryabafna/Desktop/Class/Automation/static/uploads/Income_Tax_India_Simplified_60s_Summary_thumbnail.jpg"
    
    print("Testing YouTube Upload...")
    url = upload_to_youtube(video_path, "Test Video", "This is a test upload via API", ["Test", "API"], thumb_path)
    
    print(f"Result URL: {url}")

if __name__ == "__main__":
    test()
