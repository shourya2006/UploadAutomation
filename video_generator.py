import os
import json
import time
import re
from google import genai
from google.genai import types
from huggingface_hub import InferenceClient

def split_prompt_into_scenes(prompt: str, max_scenes: int = 4, progress_callback=None) -> list[str]:
    """
    Uses Gemini flash-lite to split a single prompt into 4-second scenes.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set in the .env file.")
    
    client = genai.Client(api_key=api_key)
    
    msg = "Asking Gemini Flash-Lite to plan the scenes..."
    if progress_callback: progress_callback(msg)
    else: print(msg)
    
    system_instruction = (
        "You are an expert video director. Split the user's video prompt into "
        f"a sequence of visually distinct scenes. Each scene should describe roughly 4 seconds of footage. "
        f"Return exactly {max_scenes} scenes or fewer. Keep the descriptions highly visual, descriptive, and concise. "
        "Output ONLY a valid JSON list of strings, nothing else."
    )
    
    response = client.models.generate_content(
        model='gemini-flash-lite-latest',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )
    )
    
    response_text = response.text
    
    # Try to extract JSON array if the model added markdown blocks
    json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
    if json_match:
        response_text = json_match.group(0)
    
    try:
        scenes = json.loads(response_text)
        if isinstance(scenes, list):
            return scenes
        else:
            return [str(s) for s in scenes]
    except json.JSONDecodeError:
        msg2 = "Failed to parse LLM response as JSON. Falling back to line splitting."
        if progress_callback: progress_callback(msg2)
        else: print(msg2)
        return [line.strip('- *1234567890.') for line in response_text.split('\n') if line.strip() and len(line) > 10]

def generate_video_clip(scene_prompt: str, index: int, output_dir: str = "clips", progress_callback=None) -> str:
    """
    Generates a video clip using Hugging Face Inference Providers (fal-ai backend).
    """
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        error_msg = "HF_TOKEN is missing from your .env file! Please get one from huggingface.co."
        if progress_callback: progress_callback(error_msg)
        raise ValueError(error_msg)
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scene_{index}.mp4")
    
    msg = f"Generating video for scene {index}: {scene_prompt}"
    if progress_callback: progress_callback(msg)
    else: print(msg)
    
    msg2 = "Sending prompt to Hugging Face Cloud (fal-ai provider)..."
    if progress_callback: progress_callback(msg2)
    else: print(msg2)
    
    try:
        # Use the official HF InferenceClient with fal-ai as the provider
        hf_client = InferenceClient(
            provider="fal-ai",
            api_key=hf_token,
        )
        
        video_bytes = hf_client.text_to_video(
            prompt=scene_prompt,
            model="Wan-AI/Wan2.2-T2V-A14B",
        )
        
        with open(output_path, "wb") as f:
            f.write(video_bytes)
            
        msg3 = f"Successfully downloaded cloud-rendered clip to {output_path}"
        if progress_callback: progress_callback(msg3)
        else: print(msg3)
        return output_path
        
    except Exception as e:
        error_msg = f"Hugging Face API Error: {str(e)}"
        if progress_callback: progress_callback(error_msg)
        else: print(error_msg)
        raise

def generate_all_scenes(prompt: str, progress_callback=None) -> list[str]:
    # Check keys first
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY is missing from .env file!")
    if not os.getenv("HF_TOKEN"):
        raise ValueError("HF_TOKEN is missing from .env file!")
        
    scenes = split_prompt_into_scenes(prompt, progress_callback=progress_callback)
    
    if not scenes:
        scenes = [prompt]
        
    msg = f"Gemini successfully split the prompt into {len(scenes)} short scenes."
    if progress_callback: progress_callback(msg)
    else: print(msg)
    
    clip_paths = []
    for i, scene in enumerate(scenes):
        msg2 = f"--- Starting Scene {i+1}/{len(scenes)} ---"
        if progress_callback: progress_callback(msg2)
        else: print(msg2)
        
        path = generate_video_clip(scene, i+1, progress_callback=progress_callback)
        clip_paths.append(path)
        
    return clip_paths

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    test_prompt = "A cinematic journey through a futuristic cyberpunk city at night."
    generate_all_scenes(test_prompt)
