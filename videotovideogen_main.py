from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os

# Create FastAPI app
app = FastAPI(title="Video-to-Video Generation API", version="1.0.0")

# Request model
class VideoToVideoRequest(BaseModel):
    prompt_video: str   # URL to input video
    prompt_text: str    # Description for generation

@app.get("/")
async def read_root():
    return {"message": "Video-to-video backend is running"}

@app.post("/generate-video")
async def generate_video(request: VideoToVideoRequest):
    runway_api_url = os.getenv("RUNWAY_API_URL")
    runway_api_key = os.getenv("RUNWAY_API_KEY")

    if not runway_api_url or not runway_api_key:
        raise HTTPException(status_code=500, detail="Runway API credentials not set")

    payload = {
        "input_video": request.prompt_video,
        "prompt": request.prompt_text
    }

    headers = {
        "Authorization": f"Bearer {runway_api_key}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(runway_api_url, json=payload, headers=headers)
        resp.raise_for_status()  # Will raise HTTPError for bad responses
        return resp.json()
    except requests.exceptions.HTTPError as http_err:
        raise HTTPException(status_code=resp.status_code, detail=f"HTTP error: {http_err}")
    except requests.exceptions.RequestException as req_err:
        raise HTTPException(status_code=500, detail=f"Request error: {req_err}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
