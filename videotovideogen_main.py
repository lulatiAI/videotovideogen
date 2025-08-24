# videotovideogen_main.py

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import os
import tempfile
import requests
import time
import uuid
import boto3
from botocore.exceptions import BotoCoreError, ClientError

# Optional SDK for RunwayML (mirrors your image-to-video service)
try:
    from runwayml import RunwayML
    RUNWAY_SDK_AVAILABLE = True
except Exception:
    RUNWAY_SDK_AVAILABLE = False

# -----------------------------------------------------------------------------
# App & CORS
# -----------------------------------------------------------------------------
app = FastAPI(title="Video-to-Video Generation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            # tighten later if you want
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
    raise RuntimeError("AWS credentials are missing (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)")

BUCKET_NAME = "image-to-video-library"  # provided by you

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

# Runway client (if SDK is present)
RUNWAY_CLIENT = RunwayML(api_key=RUNWAY_API_KEY) if RUNWAY_SDK_AVAILABLE else None

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class VideoToVideoRequest(BaseModel):
    prompt_video: HttpUrl                  # should be an S3 URL (we’ll copy it in if external)
    prompt_text: str = ""
    model: str = "gen3_alpha_turbo"        # per your direction
    ratio: str = "1280:720"                # keep same shape as image service; adjust if needed

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _is_s3_url(url: str) -> bool:
    return url.startswith("s3://") or (".amazonaws.com/" in url and url.startswith("https://"))

def _s3_key_from_presigned_or_path(url: str) -> str:
    """
    Extract the key from a typical virtual-hosted–style S3 URL:
    https://<bucket>.s3.<region>.amazonaws.com/<key>
    """
    try:
        # virtual-hosted style
        prefix = f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/"
        if url.startswith(prefix):
            return url[len(prefix):]
        # path-style: https://s3.<region>.amazonaws.com/<bucket>/<key>
        path_prefix = f"https://s3.{AWS_REGION}.amazonaws.com/{BUCKET_NAME}/"
        if url.startswith(path_prefix):
            return url[len(path_prefix):]
        # s3://bucket/key
        if url.startswith("s3://"):
            parts = url.replace("s3://", "").split("/", 1)
            if len(parts) == 2 and parts[0] == BUCKET_NAME:
                return parts[1]
    except Exception:
        pass
    return ""

def _public_s3_url(key: str) -> str:
    return f"https://{BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"

def _copy_external_video_to_bucket(external_url: str) -> str:
    """
    Download external video and store it in our bucket under uploads/video/<uuid>.<ext>
    Returns the S3 key.
    """
    try:
        # Guess file extension
        ext = "mp4"
        if "." in external_url.split("?")[0]:
            maybe_ext = external_url.split("?")[0].split(".")[-1].lower()
            if maybe_ext in ["mp4", "mov", "webm", "m4v"]:
                ext = maybe_ext

        unique_key = f"uploads/video/{uuid.uuid4()}.{ext}"

        resp = requests.get(external_url, stream=True, timeout=60)
        resp.raise_for_status()

        # Upload streaming to S3
        s3_client.upload_fileobj(resp.raw, BUCKET_NAME, unique_key, ExtraArgs={"ContentType": f"video/{ext}"})
        return unique_key
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to copy external video to S3: {e}")

def _start_video_moderation(bucket: str, key: str, min_confidence: int = 80) -> str:
    """
    Start Rekognition Video Content Moderation on S3 object; returns JobId.
    """
    try:
        response = rekognition.start_content_moderation(
            Video={"S3Object": {"Bucket": bucket, "Name": key}},
            MinConfidence=min_confidence,
        )
        return response["JobId"]
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Rekognition start_content_moderation failed: {e}")

def _poll_video_moderation(job_id: str, max_wait_seconds: int = 120, poll_every: int = 4) -> dict:
    """
    Poll GetContentModeration until COMPLETE or timeout. Returns result dict:
    {
      "safe": bool,
      "labels": [ ... ]  # moderation labels if any
    }
    """
    waited = 0
    labels = []
    next_token = None
    while waited <= max_wait_seconds:
        try:
            kwargs = {"JobId": job_id, "SortBy": "TIMESTAMP"}
            if next_token:
                kwargs["NextToken"] = next_token
            resp = rekognition.get_content_moderation(**kwargs)
            status = resp.get("JobStatus")
            if status == "SUCCEEDED":
                # Collect labels (could be paginated)
                labels.extend(resp.get("ModerationLabels", []))
                next_token = resp.get("NextToken")
                if not next_token:
                    break
            elif status in ("FAILED", "PARTIAL_SUCCESS"):
                raise HTTPException(status_code=500, detail=f"Rekognition moderation job status: {status}")
            else:
                time.sleep(poll_every)
                waited += poll_every
                continue
        except (BotoCoreError, ClientError) as e:
            raise HTTPException(status_code=500, detail=f"Rekognition get_content_moderation failed: {e}")

    # Decide safe vs not based on any labels present (you can refine with categories/confidence)
    is_safe = len(labels) == 0
    return {"safe": is_safe, "labels": labels}

def _run_runway_video_to_video(model: str, video_url: str, prompt_text: str, ratio: str) -> str:
    """
    Kick off RunwayML video-to-video and poll until done.
    Returns the output video URL.
    """
    # Prefer SDK (matches your other service). If not available, raise a clear error.
    if not RUNWAY_SDK_AVAILABLE or RUNWAY_CLIENT is None:
        raise HTTPException(
            status_code=500,
            detail="`runwayml` SDK not installed. Add `runwayml>=1.0.0` to requirements.txt."
        )

    try:
        task = RUNWAY_CLIENT.video_to_video.create(
            model=model,
            prompt_video=video_url,
            prompt_text=prompt_text,
            ratio=ratio
        )
        task_id = task.id

        # Poll
        while True:
            status = RUNWAY_CLIENT.tasks.retrieve(task_id)
            if status.status in ["SUCCEEDED", "FAILED"]:
                break
            time.sleep(5)

        if status.status == "FAILED":
            raise HTTPException(status_code=500, detail="RunwayML task failed.")

        if not status.output:
            raise HTTPException(status_code=500, detail="RunwayML returned no output.")

        out_url = status.output[0]
        if not out_url:
            raise HTTPException(status_code=500, detail="RunwayML output missing URL.")
        return out_url

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RunwayML error: {e}")

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/")
def home():
    return {"message": "RunwayML Video-to-Video API with Rekognition moderation is running"}

@app.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        ext = file.filename.split(".")[-1].lower()
        if ext not in ["mp4", "mov", "webm", "m4v"]:
            return JSONResponse(status_code=400, content={"error": "Invalid video format."})

        key = f"uploads/video/{uuid.uuid4()}.{ext}"
        contents = await file.read()

        # Upload to S3 (no public ACL; bucket should block public access)
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=contents,
            ContentType=file.content_type or f"video/{ext}"
        )

        # Moderate the uploaded video immediately
        job_id = _start_video_moderation(BUCKET_NAME, key)
        result = _poll_video_moderation(job_id)

        if not result["safe"]:
            # Optionally delete disallowed content
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=key)
            except Exception:
                pass
            return JSONResponse(
                status_code=400,
                content={"status": "REJECTED", "reason": "Video failed moderation.", "labels": result["labels"]}
            )

        # Return our S3 URL (frontend/backends can use this)
        return {"url": _public_s3_url(key), "status": "APPROVED"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video upload failed: {e}")

@app.post("/generate-video")
def generate_video(request: VideoToVideoRequest):
    """
    1) Ensure the input video is in our S3 bucket (copy if external).
    2) Run Rekognition Video moderation (block if flagged).
    3) Call RunwayML video-to-video (gen3_alpha_turbo).
    4) Stream resulting video file back to client.
    """
    try:
        # 1) Ensure video resides in our bucket
        input_url = str(request.prompt_video)
        if _is_s3_url(input_url) and _s3_key_from_presigned_or_path(input_url):
            src_key = _s3_key_from_presigned_or_path(input_url)
        else:
            # Copy external to our bucket
            src_key = _copy_external_video_to_bucket(input_url)

        # 2) Moderate the S3 video
        job_id = _start_video_moderation(BUCKET_NAME, src_key)
        result = _poll_video_moderation(job_id)
        if not result["safe"]:
            return {"status": "REJECTED", "reason": "Video failed moderation.", "labels": result["labels"]}

        # 3) Call RunwayML
        s3_public_url = _public_s3_url(src_key)
        output_url = _run_runway_video_to_video(
            model=request.model,
            video_url=s3_public_url,
            prompt_text=request.prompt_text,
            ratio=request.ratio
        )

        # 4) Download generated video and send as FileResponse
        r = requests.get(output_url, stream=True, timeout=120)
        r.raise_for_status()
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        with open(tmp_file.name, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        return FileResponse(tmp_file.name, media_type="video/mp4", filename="generated_video.mp4")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API error: {e}")

