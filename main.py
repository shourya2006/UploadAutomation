import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our custom modules
from video_generator import generate_all_scenes
from video_editor import merge_videos
from social_uploader import publish_all

def main():
    print("=======================================")
    print("   AI Video Automation Pipeline (HF)   ")
    print("=======================================")
    
    if not os.getenv("GEMINI_API_KEY"):
        print("Error: GEMINI_API_KEY is not set in .env file.")
        print("Please configure your API keys first.")
        sys.exit(1)
        
    prompt = input("\nEnter your video prompt: ")
    if not prompt.strip():
        print("Prompt cannot be empty. Exiting.")
        sys.exit(1)
        
    print("\n--- STEP 1: Generating Scenes ---")
    clip_paths = generate_all_scenes(prompt)
    
    if not clip_paths:
        print("No clips were generated. Exiting.")
        sys.exit(1)
        
    print("\n--- STEP 2: Merging Video Clips ---")
    final_video_path = "final_output.mp4"
    try:
        merge_videos(clip_paths, final_video_path)
    except Exception as e:
        print(f"Failed to merge videos: {e}")
        sys.exit(1)
        
    print(f"\nVideo successfully generated at: {os.path.abspath(final_video_path)}")
    
    print("\n--- STEP 3: Client Verification ---")
    print("Please review the generated video.")
    while True:
        verify = input("Is the video correct and ready for upload? (y/n): ").strip().lower()
        if verify in ['y', 'yes']:
            break
        elif verify in ['n', 'no']:
            print("Video rejected by client. Exiting without uploading.")
            sys.exit(0)
        else:
            print("Please enter 'y' or 'n'.")
            
    print("\n--- STEP 4: Uploading to Social Media ---")
    yt_url = publish_all(final_video_path, prompt)
    
    print("\n=======================================")
    print("           Pipeline Complete!          ")
    print("=======================================")
    if yt_url:
        print(f"YouTube URL: {yt_url}")
        print("You can now share this URL with your audience.")

if __name__ == "__main__":
    main()
