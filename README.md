# Video Merger API

A FastAPI server that uses MoviePy to merge multiple videos and audio tracks.

## Features

- Merges multiple videos into a single video
- Combines background audio and narration with the merged video
- Limits video duration if needed
- Handles downloading of remote video and audio files

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Run the server:

```bash
uvicorn main:app --reload
```

## API Usage

### Merge Videos and Audio

**Endpoint:** `POST /merge`

**Request Body:**

```json
{
  "videos": [
    "https://example.com/video1.mp4",
    "https://example.com/video2.mp4",
    "..."
  ],
  "background_audio": "https://example.com/background.mp3",
  "narration": "https://example.com/narration.mp3",
  "max_duration": 600
}
```

**Response:**

```json
{
  "output_file": "/output/merged_video_uuid.mp4",
  "message": "Videos and audio merged successfully"
}
```

## Directory Structure

- `/temp`: Temporary directory for downloaded files
- `/output`: Directory for the merged output videos

## Notes

- The API automatically creates the necessary directories if they don't exist
- Temporary files are cleaned up after processing
- Background audio volume is reduced to 30% to make narration more clear
- If background audio is shorter than the final video, it will be looped
