import os
import uuid
import shutil
import requests
import logging
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import json
from pydantic import BaseModel
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create necessary directories
TEMP_DIR = "temp"
OUTPUT_DIR = "output"

# Get absolute paths
TEMP_DIR = os.path.abspath(TEMP_DIR)
OUTPUT_DIR = os.path.abspath(OUTPUT_DIR)

# Create directories
logger.info(f"Creating directories: TEMP_DIR={TEMP_DIR}, OUTPUT_DIR={OUTPUT_DIR}")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
logger.info(f"Directories created successfully")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MergeRequest(BaseModel):
    video_urls: List[str]
    background_audio_url: Optional[str] = None
    background_volume: Optional[float] = 0.5

def download_file(url, output_path):
    """Download a file from URL to the specified path"""
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    return False

def cleanup_files(file_paths):
    """Clean up temporary files"""
    logger.info(f"Cleaning up files: {file_paths}")
    for file_path in file_paths:
        if os.path.exists(file_path):
            try:
                if os.path.isdir(file_path):
                    logger.info(f"Removing directory: {file_path}")
                    shutil.rmtree(file_path)
                else:
                    logger.info(f"Removing file: {file_path}")
                    os.remove(file_path)
                logger.info(f"Successfully removed: {file_path}")
            except Exception as e:
                logger.error(f"Error removing {file_path}: {str(e)}")

@app.post("/merge")
async def merge_videos(
    background_tasks: BackgroundTasks,
    merge_request: str = Form(...),
    narration_file: UploadFile = File(None)
):
    logger.info("Merge endpoint accessed")
    # Parse the merge request JSON
    logger.info(f"Received merge_request: {merge_request}")
    request_data = json.loads(merge_request)
    merge_data = MergeRequest(**request_data)
    logger.info(f"Parsed merge data: {merge_data}")
    
    # Create a unique ID for this request
    request_id = str(uuid.uuid4())
    logger.info(f"Generated request ID: {request_id}")
    request_temp_dir = os.path.join(TEMP_DIR, request_id)
    logger.info(f"Creating temp directory: {request_temp_dir}")
    os.makedirs(request_temp_dir, exist_ok=True)
    
    # List to track files for cleanup - only include temporary directory
    files_to_cleanup = [request_temp_dir]
    
    try:
        # Download videos
        video_paths = []
        for i, video_url in enumerate(merge_data.video_urls):
            video_path = os.path.join(request_temp_dir, f"video_{i}.mp4")
            if download_file(video_url, video_path):
                video_paths.append(video_path)
            else:
                return {"error": f"Failed to download video from {video_url}"}
        
        if not video_paths:
            return {"error": "No videos were successfully downloaded"}
        
        # Load video clips
        video_clips = [VideoFileClip(path) for path in video_paths]
        
        # Concatenate videos
        final_clip = concatenate_videoclips(video_clips)
        
        # Process audio files
        audio_tracks = []
        
        # Background audio
        if merge_data.background_audio_url:
            bg_audio_path = os.path.join(request_temp_dir, "background.mp3")
            if download_file(merge_data.background_audio_url, bg_audio_path):
                bg_audio = AudioFileClip(bg_audio_path)
                
                # Loop background audio if it's shorter than the final video
                if bg_audio.duration < final_clip.duration:
                    bg_audio = bg_audio.loop(duration=final_clip.duration)
                else:
                    # Trim background audio if it's longer than the final video
                    bg_audio = bg_audio.subclip(0, final_clip.duration)
                
                # Set volume for background audio
                bg_audio = bg_audio.volumex(merge_data.background_volume)
                audio_tracks.append(bg_audio)
            else:
                return {"error": "Failed to download background audio"}
        
        # Narration audio
        if narration_file:
            narration_path = os.path.join(request_temp_dir, "narration.mp3")
            with open(narration_path, "wb") as buffer:
                shutil.copyfileobj(narration_file.file, buffer)
            
            narration_audio = AudioFileClip(narration_path)
            
            # Trim narration if it's longer than the final video
            if narration_audio.duration > final_clip.duration:
                narration_audio = narration_audio.subclip(0, final_clip.duration)
            
            audio_tracks.append(narration_audio)
        
        # Combine audio tracks with video
        if audio_tracks:
            final_audio = CompositeAudioClip(audio_tracks)
            final_clip = final_clip.set_audio(final_audio)
        
        # Export the final clip
        output_filename = f"merged_video_{request_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        logger.info(f"Saving output file to: {output_path}")
        
        # Ensure output directory exists
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Check if output directory is writable
        if not os.access(os.path.dirname(output_path), os.W_OK):
            logger.error(f"Output directory is not writable: {os.path.dirname(output_path)}")
            return {"error": "Output directory is not writable"}
            
        try:
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
            logger.info(f"Successfully wrote video file to: {output_path}")
            
            # Verify file was created
            if os.path.exists(output_path):
                logger.info(f"Verified file exists: {output_path}, size: {os.path.getsize(output_path)} bytes")
                
                # Create a permanent copy with a fixed name
                permanent_output_path = os.path.join(OUTPUT_DIR, "final_merged_video.mp4")
                logger.info(f"Creating permanent copy at: {permanent_output_path}")
                shutil.copy2(output_path, permanent_output_path)
                logger.info(f"Permanent copy created successfully")
            else:
                logger.error(f"File was not created: {output_path}")
                return {"error": "Failed to create output file"}
        except Exception as e:
            logger.error(f"Error writing video file: {str(e)}")
            return {"error": f"Error writing video file: {str(e)}"}
        
        # Close all clips to release resources
        final_clip.close()
        for clip in video_clips:
            clip.close()
        for track in audio_tracks:
            track.close()
        
        # Return the video as a downloadable file
        def iterfile():
            logger.info(f"Streaming file: {output_path}")
            try:
                with open(output_path, "rb") as file:
                    yield from file
                logger.info(f"Finished streaming file: {output_path}")
            except Exception as e:
                logger.error(f"Error streaming file: {str(e)}")
            
            # Clean up temporary files and the output file after streaming
            logger.info(f"Scheduling cleanup of files")
            background_tasks.add_task(cleanup_files, [request_temp_dir, output_path])
        
        return StreamingResponse(
            iterfile(),
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
        
    except Exception as e:
        # Clean up only temporary files in case of error
        cleanup_files([request_temp_dir])
        return {"error": str(e)}

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    
    # Check if output directory exists and is writable
    output_dir_exists = os.path.exists(OUTPUT_DIR)
    output_dir_writable = os.access(OUTPUT_DIR, os.W_OK) if output_dir_exists else False
    
    # Check if temp directory exists and is writable
    temp_dir_exists = os.path.exists(TEMP_DIR)
    temp_dir_writable = os.access(TEMP_DIR, os.W_OK) if temp_dir_exists else False
    
    return {
        "message": "Video Merger API is running. Use /merge endpoint to merge videos.",
        "status": "ok",
        "directories": {
            "output_dir": {
                "path": OUTPUT_DIR,
                "exists": output_dir_exists,
                "writable": output_dir_writable
            },
            "temp_dir": {
                "path": TEMP_DIR,
                "exists": temp_dir_exists,
                "writable": temp_dir_writable
            }
        }
    }

@app.get("/check-directories")
async def check_directories():
    """Check and create output and temp directories"""
    logger.info("Check directories endpoint accessed")
    
    # Ensure directories exist
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Check if directories are writable
    temp_dir_writable = os.access(TEMP_DIR, os.W_OK)
    output_dir_writable = os.access(OUTPUT_DIR, os.W_OK)
    
    # Create a test file in the output directory to verify write permissions
    test_file_path = os.path.join(OUTPUT_DIR, "test_write.txt")
    test_file_success = False
    try:
        with open(test_file_path, "w") as f:
            f.write("Test write access")
        test_file_success = True
        # Clean up test file
        os.remove(test_file_path)
    except Exception as e:
        logger.error(f"Failed to write test file: {str(e)}")
    
    return {
        "status": "ok",
        "directories": {
            "temp_dir": {
                "path": TEMP_DIR,
                "exists": os.path.exists(TEMP_DIR),
                "writable": temp_dir_writable
            },
            "output_dir": {
                "path": OUTPUT_DIR,
                "exists": os.path.exists(OUTPUT_DIR),
                "writable": output_dir_writable,
                "test_write_success": test_file_success
            }
        }
    }

@app.get("/list-videos")
async def list_videos():
    """Information about video streaming"""
    logger.info("List videos endpoint accessed")
    
    return {
        "message": "Videos are not being saved to the server. They are streamed directly to the client upon creation.",
        "videos": []
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on port 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
