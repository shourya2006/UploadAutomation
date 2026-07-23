import os
import argparse
from dotenv import load_dotenv
from social_uploader import publish_all

def main():
    parser = argparse.ArgumentParser(description="Upload a video to YouTube, Facebook, and Instagram.")
    parser.add_argument("video_path", help="Path to the video file to upload (.mp4)")
    parser.add_argument("--prompt", default="My latest AI-generated video!", help="Description/Prompt for the video post")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.video_path):
        print(f"Error: The video file '{args.video_path}' does not exist.")
        return
        
    print(f"Starting upload manager for: {args.video_path}")
    
    # Run the uploader
    publish_all(args.video_path, args.prompt)
    
    print("Upload manager finished.")

if __name__ == "__main__":
    load_dotenv()
    main()
