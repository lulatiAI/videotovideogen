from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import os
import tempfile
import requests
import time
from runwayml import RunwayML
import boto3
import uuid

app = FastAPI(title="Video-to-Video Generation API", version="1.0.0")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RunwayML API key
RUNWAY_API_KEY = os.getenv("RUNWAYML_API_SECRET")
if not RUNWAY_API_KEY:
    raise RuntimeError("RUNWAYML_API_SECRET environment variable is missing")

# AWS credentials
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

BUCKET_NAME = "image-to-video-library"

client = RunwayML(api_key=RUNWAY_API_KEY)

class VideoToVideoRequest(BaseModel):
    prompt_video: HttpUrl
    prompt_text: str = ""
    model: str = "gen4_turbo"
    ratio: str = "1280:720"

def is_video_safe(video_url: str) -> bool:
    """
    Use AWS Rekognition to perform moderation on uploaded video.
    """
    try:
        # Download video temporarily
        video_data = requests.get(video_url, stream=True)
        video_data.raise_for_status()
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        with open(tmp_file.name, "wb") as f:
            for chunk in video_data.iter_content(chunk_size=8192):
                f.write(chunk)

        # Upload to S3 for Rekognition processing (temporary key)
        temp_key = f"temp/{uuid.uuid4()}.mp4"
        s3_client.put_object(Bucket=BUCKET_NAME, Key=temp_key, Body=open(tmp_file.name, "rb"))

        # Start Rekognition content moderation
        response = rekognition.start_content_moderation(
            Video={'S3Object': {'Bucket': BUCKET_NAME, 'Name': temp_key}},
            MinConfidence=80
        )
        job_id = response['JobId']

        # Poll until Rekognition finishes
        while True:
            result = rekognition.get_content_moderation(JobId=job_id)
            if result['JobStatus'] in ['SUCCEEDED', 'FAILED']:
                break
            time.sleep(5)

        if result['JobStatus'] == 'FAILED':
            raise HTTPException(status_code=500, detail="Video moderation failed in Rekognition.")

        # Check for moderation labels
        if result.get('ModerationLabels'):
            print("Video flagged:", result['ModerationLabels'])
            return False

        return True

    except Exception as e:
        print("Rekognition error:", e)
        raise HTTPException(status_code=500, detail=f"Video moderation failed: {str(e)}")

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video to S3 and return the private URL
    """
    try:
        file_extension = file.filename.split('.')[-1].lower()
        if file_extension not in ["mp4", "mov", "avi", "mkv"]:
            return JSONResponse(status_code=400, content={"error": "Invalid video format."})

        # Generate a unique file name
        unique_filename = f"{uuid.uuid4()}.{file_extension}"

        # Read file content
        contents = await file.read()

        # Upload to S3 (private)
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=unique_filename,
            Body=contents,
            ContentType=file.content_type
        )

        # Construct URL (front-end can fetch via signed URL if needed)
        video_url = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"

        return {"url": video_url}

    except Exception as e:
        print("Upload error:", e)
        raise HTTPException(status_code=500, detail=f"Video upload failed: {str(e)}")

@app.post("/generate-video")
def generate_video(request: VideoToVideoRequest):
    """
    Generate video using RunwayML after moderation
    """
    try:
        prompt_video_str = str(request.prompt_video)
        if not is_video_safe(prompt_video_str):
            return {"status": "REJECTED", "reason": "Video failed moderation check"}

        task = client.video_to_video.create(
            model=request.model,
            input_video=prompt_video_str,
            prompt_text=request.prompt_text,
            ratio=request.ratio
        )
        task_id = task.id

        while True:
            task_status = client.tasks.retrieve(task_id)
            if task_status.status in ["SUCCEEDED", "FAILED"]:
                break
            time.sleep(5)

        if task_status.status == "FAILED":
            raise HTTPException(status_code=500, detail="RunwayML task failed.")

        if not task_status.output:
            raise HTTPException(status_code=500, detail="RunwayML task returned no output.")

        video_url = task_status.output[0]
        if not video_url:
            raise HTTPException(status_code=500, detail="RunwayML output missing video URL.")

        # Download generated video
        video_response = requests.get(video_url, stream=True)
        video_response.raise_for_status()

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        with open(tmp_file.name, "wb") as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        return FileResponse(tmp_file.name, media_type="video/mp4", filename="generated_video.mp4")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")

@app.get("/")
def home():
    return {"message": "Video-to-Video API with Rekognition moderation is running"}
