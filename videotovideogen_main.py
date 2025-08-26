# videotovideogen_main.py

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import os
import uuid
import requests
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import asyncio

# RunwayML SDK
try:
    from runwayml import RunwayML
    RUNWAY_SDK_AVAILABLE = True
except ImportError:
    RUNWAY_SDK_AVAILABLE = False

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="Video-to-Video Generation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Config / Clients
# -----------------------------------------------------------------------------
RUNWAY_API_KEY = os.getenv("RUNWAYML_API_SECRET")
if not RUNWAY_API_KEY:
    raise RuntimeError("RUNWAYML_API_SECRET environment variable is missing")

AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

if not (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
    raise RuntimeError("AWS credentials are missing")

BUCKET_NAME = "image-to-video-library"

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

rekognition = boto3.client(
    "rekognition",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

RUNWAY_CLIENT = RunwayML(api_key=RUNWAY_API_KEY) if RUNWAY_SDK_AVAILABLE else None

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class VideoToVideoRequest(BaseModel):
    prompt_video: HttpUrl
    prompt_text: str = ""
    model: str = "gen3_alpha_turbo"
    ratio: str = "1280:720"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _is_s3_url(url: str) -> bool:
    return url.startswith("s3://") or (".amazonaws.com/" in url and url.startswith("https://"))

def _s3_key_from_presigned_or_path(url: str) -> str:
    prefix = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/"
    if url.startswith(prefix):
        return url[len(prefix):]
    path_prefix = f"https://s3.{AWS_REGION}.amazonaws.com/{BUCKET_NAME}/"
    if url.startswith(path_prefix):
        return url[len(path_prefix):]
    if url.startswith("s3://"):
        parts = url.replace("s3://", "").split("/", 1)
        if len(parts) == 2 and parts[0] == BUCKET_NAME:
            return parts[1]
    return ""

def _public_s3_url(key: str) -> str:
    return f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"

async def _copy_external_video_to_bucket(external_url: str) -> str:
    ext = "mp4"
    if "." in external_url.split("?")[0]:
        maybe_ext = external_url.split("?")[0].split(".")[-1].lower()
        if maybe_ext in ["mp4", "mov", "webm", "m4v"]:
            ext = maybe_ext
    unique_key = f"uploads/video/{uuid.uuid4()}.{ext}"
    resp = requests.get(external_url, stream=True, timeout=60)
    resp.raise_for_status()
    s3_client.upload_fileobj(resp.raw, BUCKET_NAME, unique_key, ExtraArgs={"ContentType": f"video/{ext}"})
    return unique_key

async def _start_video_moderation(bucket: str, key: str, min_confidence: int = 80) -> str:
    try:
        response = rekognition.start_content_moderation(
            Video={"S3Object": {"Bucket": bucket, "Name": key}},
            MinConfidence=min_confidence,
        )
        job_id = response["JobId"]
        # Poll asynchronously
        while True:
            status = rekognition.get_content_moderation(JobId=job_id)
            if status["JobStatus"] in ["SUCCEEDED", "FAILED"]:
                break
            await asyncio.sleep(2)
        if status["JobStatus"] == "FAILED":
            raise HTTPException(status_code=500, detail="Rekognition moderation failed")
        # Simple check: if any ModerationLabels are found, mark rejected
        if status.get("ModerationLabels"):
            raise HTTPException(status_code=400, detail="Video flagged by content moderation")
        return key
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Rekognition error: {e}")

async def _poll_runway_task(task_id: str) -> str:
    while True:
        status = RUNWAY_CLIENT.tasks.retrieve(task_id)
        if status.status in ["SUCCEEDED", "FAILED"]:
            break
        await asyncio.sleep(2)
    if status.status == "FAILED":
        raise HTTPException(status_code=500, detail="RunwayML task failed.")
    output_url = status.output[0] if status.output else None
    if not output_url:
        raise HTTPException(status_code=500, detail="RunwayML returned no output.")
    return output_url

async def _run_runway_video_to_video(model: str, video_url: str, prompt_text: str, ratio: str) -> str:
    if not RUNWAY_SDK_AVAILABLE or RUNWAY_CLIENT is None:
        raise HTTPException(
            status_code=500,
            detail="`runwayml` SDK not installed. Add `runwayml>=1.0.0` to requirements.txt."
        )
    try:
        task = RUNWAY_CLIENT.video_to_video.create(
            model=model,
            input={"video": video_url, "prompt": prompt_text, "ratio": ratio}
        )
        return await _poll_runway_task(task.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RunwayML error: {e}")

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/")
@app.head("/")
def home():
    return {"message": "RunwayML Video-to-Video API running"}

@app.get("/healthz")
@app.head("/healthz")
def healthz():
    return {"ok": True}

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ["mp4", "mov", "webm", "m4v"]:
        return JSONResponse(status_code=400, content={"error": "Invalid video format."})
    key = f"uploads/video/{uuid.uuid4()}.{ext}"
    contents = await file.read()
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=contents,
        ContentType=file.content_type or f"video/{ext}"
    )
    await _start_video_moderation(BUCKET_NAME, key)
    return {"url": _public_s3_url(key), "status": "APPROVED"}

@app.post("/generate-video")
async def generate_video(request: VideoToVideoRequest):
    input_url = str(request.prompt_video)
    if _is_s3_url(input_url) and _s3_key_from_presigned_or_path(input_url):
        src_key = _s3_key_from_presigned_or_path(input_url)
    else:
        src_key = await _copy_external_video_to_bucket(input_url)
    s3_url = _public_s3_url(src_key)
    output_url = await _run_runway_video_to_video(
        model=request.model,
        video_url=s3_url,
        prompt_text=request.prompt_text,
        ratio=request.ratio
    )
    return {"output_url": output_url, "status": "SUCCESS"}
