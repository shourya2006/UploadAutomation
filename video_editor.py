import ffmpeg
import os

def merge_videos(video_paths: list[str], output_path: str = "final_output.mp4", progress_callback=None):
    """
    Merges a list of video files into a single video file using ffmpeg.
    """
    msg = f"Merging {len(video_paths)} videos into {output_path}..."
    print(msg)
    if progress_callback: progress_callback(msg)
    
    if not video_paths:
        raise ValueError("No video paths provided for merging.")
        
    # Remove output file if it exists to avoid ffmpeg asking for confirmation
    if os.path.exists(output_path):
        os.remove(output_path)
    
    # Create input streams
    inputs = [ffmpeg.input(path) for path in video_paths]
    
    # We need to concat both video and audio streams (if they exist)
    # Our mock videos only have video, but we should handle both in production
    
    try:
        # Simple concat using ffmpeg-python
        concat = ffmpeg.concat(*inputs, v=1, a=0) # Only video for now to avoid errors with audio-less clips
        
        # Run ffmpeg command
        ffmpeg.output(concat, output_path, vcodec='libx264', crf=23, preset='fast').run(quiet=True, overwrite_output=True)
        
        msg2 = f"Successfully created {output_path}"
        print(msg2)
        if progress_callback: progress_callback(msg2)
        
        return output_path
    except ffmpeg.Error as e:
        err_msg = f"FFmpeg Error: {e.stderr.decode() if e.stderr else str(e)}"
        print(err_msg)
        if progress_callback: progress_callback(err_msg)
        raise

if __name__ == "__main__":
    # Small test if you have multiple mp4 files
    print("Video editor module loaded.")
