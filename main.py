from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Response, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import StreamingResponse
import io
import os
import tempfile
import uuid
import requests
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
import logging
import shutil
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up Video Merger API")
    yield
    # Shutdown logic
    logger.info("Shutting down Video Merger API")
    # Clean up temp directory
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

app = FastAPI(title="Video Merger API", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Create a temporary directory for storing downloaded files
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Create output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class MergeRequest(BaseModel):
    videos: List[str]
    background_audio: str
    narration: str
    max_duration: int = 600  # Default max duration in seconds

class MergeResponse(BaseModel):
    output_file: str
    message: str

@app.get("/")
@app.head("/")
async def root():
    return {"message": "Video Merger API is running"}

def download_file(url, save_path):
    """Download a file from a URL and save it to the specified path."""
    try:
        logger.info(f"Downloading file from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"File downloaded successfully to {save_path}")
        return save_path
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {str(e)}")
        raise

def process_videos(request: MergeRequest):
    """Process the videos and audio files according to the request."""
    try:
        # Create a unique job ID
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Download all videos
        video_paths = []
        for i, video_url in enumerate(request.videos):
            video_path = os.path.join(job_dir, f"video_{i}.mp4")
            download_file(video_url, video_path)
            video_paths.append(video_path)
        
        # Download audio files
        bg_audio_path = os.path.join(job_dir, "background.mp3")
        download_file(request.background_audio, bg_audio_path)
        
        narration_path = os.path.join(job_dir, "narration.mp3")
        download_file(request.narration, narration_path)
        
        # Load video clips
        video_clips = []
        for path in video_paths:
            try:
                clip = VideoFileClip(path)
                video_clips.append(clip)
                logger.info(f"Loaded video clip: {path}, duration: {clip.duration}")
            except Exception as e:
                logger.error(f"Error loading video clip {path}: {str(e)}")
                # Continue with other clips if one fails
        
        if not video_clips:
            raise Exception("No valid video clips could be loaded")
        
        # Concatenate video clips
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # Limit video duration if needed
        if final_video.duration > request.max_duration:
            logger.info(f"Trimming video to max duration: {request.max_duration}s")
            final_video = final_video.subclip(0, request.max_duration)
        
        # Load audio clips
        try:
            background_audio = AudioFileClip(bg_audio_path)
            # Loop background audio if it's shorter than the video
            if background_audio.duration < final_video.duration:
                background_audio = background_audio.fx(
                    lambda clip: clip.loop(duration=final_video.duration)
                )
            else:
                # Trim background audio if it's longer than the video
                background_audio = background_audio.subclip(0, final_video.duration)
            
            narration_audio = AudioFileClip(narration_path)
            # Trim narration if it's longer than the video
            if narration_audio.duration > final_video.duration:
                narration_audio = narration_audio.subclip(0, final_video.duration)
            
            # Adjust volumes
            background_audio = background_audio.volumex(0.3)  # Lower background volume
            
            # Combine audio tracks
            final_audio = CompositeAudioClip([background_audio, narration_audio])
            
            # Set the audio of the final video
            final_video = final_video.set_audio(final_audio)
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            # Continue with just the video if audio processing fails
        
        # Save the final video
        output_filename = f"merged_video_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        logger.info(f"Writing final video to {output_path}")
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(job_dir, "temp_audio.m4a"),
            remove_temp=True,
            threads=4
        )
        
        # Close all clips to free resources
        final_video.close()
        for clip in video_clips:
            clip.close()
        
        # Clean up temporary files
        shutil.rmtree(job_dir)
        
        return output_filename
    
    except Exception as e:
        logger.error(f"Error processing videos: {str(e)}")
        # Clean up if possible
        if 'job_dir' in locals() and os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        raise

@app.post("/merge")
async def merge_videos(request: MergeRequest, background_tasks: BackgroundTasks):
    try:
        # Process the videos
        output_filename = process_videos(request)
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Open the file and return it as a binary response
        file_like = open(output_path, mode="rb")
        
        # Set up background task to clean up the file after sending
        def cleanup_file():
            file_like.close()
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info(f"Cleaned up file: {output_path}")
        
        background_tasks.add_task(cleanup_file)
        
        # Return the video file as a StreamingResponse
        return StreamingResponse(
            content=file_like, 
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error in merge_videos endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to handle binary file upload for narration
@app.post("/merge-with-file")
async def merge_videos_with_file(
    videos: str = Form(...),
    background_audio: str = Form(...),
    max_duration: int = Form(600),
    narration_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    try:
        # Parse videos list from JSON string
        import json
        videos_list = json.loads(videos)
        
        # Create a temporary directory for this request
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Save the uploaded narration file
        narration_path = os.path.join(job_dir, "narration.mp3")
        with open(narration_path, "wb") as buffer:
            shutil.copyfileobj(narration_file.file, buffer)
        
        # Create a request object to reuse existing processing logic
        request = MergeRequest(
            videos=videos_list,
            background_audio=background_audio,
            narration="",  # Not used in this flow
            max_duration=max_duration
        )
        
        # Process the videos with the local narration file
        output_filename = process_videos_with_local_narration(request, narration_path)
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # Open the file and return it as a binary response
        file_like = open(output_path, mode="rb")
        
        # Set up background task to clean up the file after sending
        def cleanup_file():
            file_like.close()
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info(f"Cleaned up file: {output_path}")
            if os.path.exists(job_dir):
                shutil.rmtree(job_dir)
        
        background_tasks.add_task(cleanup_file)
        
        # Return the video file as a StreamingResponse
        return StreamingResponse(
            content=file_like, 
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename={output_filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error in merge_videos_with_file endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Function to process videos with local narration file
def process_videos_with_local_narration(request: MergeRequest, narration_path: str):
    """Process the videos and audio files with a local narration file."""
    try:
        # Create a unique job ID
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Download all videos
        video_paths = []
        for i, video_url in enumerate(request.videos):
            video_path = os.path.join(job_dir, f"video_{i}.mp4")
            download_file(video_url, video_path)
            video_paths.append(video_path)
        
        # Download background audio
        bg_audio_path = os.path.join(job_dir, "background.mp3")
        download_file(request.background_audio, bg_audio_path)
        
        # Narration file is already local, no need to download
        
        # Load video clips
        video_clips = []
        for path in video_paths:
            try:
                clip = VideoFileClip(path)
                video_clips.append(clip)
                logger.info(f"Loaded video clip: {path}, duration: {clip.duration}")
            except Exception as e:
                logger.error(f"Error loading video clip {path}: {str(e)}")
                # Continue with other clips if one fails
        
        if not video_clips:
            raise Exception("No valid video clips could be loaded")
        
        # Concatenate video clips
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # Limit video duration if needed
        if final_video.duration > request.max_duration:
            logger.info(f"Trimming video to max duration: {request.max_duration}s")
            final_video = final_video.subclip(0, request.max_duration)
        
        # Load audio clips
        try:
            background_audio = AudioFileClip(bg_audio_path)
            # Loop background audio if it's shorter than the video
            if background_audio.duration < final_video.duration:
                background_audio = background_audio.fx(
                    lambda clip: clip.loop(duration=final_video.duration)
                )
            else:
                # Trim background audio if it's longer than the video
                background_audio = background_audio.subclip(0, final_video.duration)
            
            narration_audio = AudioFileClip(narration_path)
            # Trim narration if it's longer than the video
            if narration_audio.duration > final_video.duration:
                narration_audio = narration_audio.subclip(0, final_video.duration)
            
            # Adjust volumes
            background_audio = background_audio.volumex(0.3)  # Lower background volume
            
            # Combine audio tracks
            final_audio = CompositeAudioClip([background_audio, narration_audio])
            
            # Set the audio of the final video
            final_video = final_video.set_audio(final_audio)
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            # Continue with just the video if audio processing fails
        
        # Save the final video
        output_filename = f"merged_video_{job_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        logger.info(f"Writing final video to {output_path}")
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(job_dir, "temp_audio.m4a"),
            remove_temp=True,
            threads=4
        )
        
        # Close all clips to free resources
        final_video.close()
        for clip in video_clips:
            clip.close()
        
        # Clean up temporary files
        shutil.rmtree(job_dir)
        
        return output_filename
    
    except Exception as e:
        logger.error(f"Error processing videos: {str(e)}")
        # Clean up if possible
        if 'job_dir' in locals() and os.path.exists(job_dir):
            shutil.rmtree(job_dir)
        raise

# Lifespan events are now handled by the asynccontextmanager above
