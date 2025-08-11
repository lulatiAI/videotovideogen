from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os

# Create FastAPI app
app = FastAPI(title="Video-to-Video Generation API", version="1.0.0")

# Example request model
class VideoToVideoRequest(BaseModel):
    prompt_video: str   # URL to input video
    prompt_text: str    # Description for generation

@app.get("/")
def read_root():
    return {"message": "Video-to-video backend is running"}

@app.post("/generate-video")
def generate_video(request: VideoToVideoRequest):
    try:
        # Example: Replace this with your actual video generation call
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

        resp = requests.post(runway_api_url, json=payload, headers=headers)
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        return resp.json()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
