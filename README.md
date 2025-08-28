# 🎥 Video-to-AI Video Generator

Transform regular videos into AI-generated, enhanced videos in just a few clicks.  
This project powers the **Video-to-Video** page on [Lulati.com](https://www.lulati.com/video-to-ai-video/), where users can upload videos, process them through an AI model, and instantly download the generated result.

---

## 🚀 Features

Seamless Video Uploads – Drag-and-drop or select videos from your device.

Real-Time Upload Feedback – Progress bar with status updates for every stage of the upload.

AI Video Generation – Powered by a custom inference pipeline for high-quality video transformation.

Strict Content Moderation – All videos are screened with AWS Rekognition before processing.

Scalable Storage – Uses Amazon S3 for reliable, secure storage and delivery.

Fully Responsive UI – Works smoothly on desktop and mobile devices.

---

## 🛠️ Tech Stack

**Frontend**
HTML5, CSS3, JavaScript (Vanilla)

AJAX / Fetch API for asynchronous requests

Clean and responsive layout

**Backend**
Flask or FastAPI for API handling

AWS Lambda for serverless moderation logic

Amazon Rekognition for video content screening

Amazon S3 for storage and delivery

DevOps & Deployment

Render for backend hosting

GitHub for version control

AWS SDKs for seamless integrations

**Other Tools**
- `boto3` for AWS operations  
- Progress monitoring and blob handling for video responses  

---

🔄 Custom AI Inference & Moderation Pipeline

The platform implements a custom pipeline to ensure content safety and reliability:

Video Upload – Users upload a source video via the frontend.

Content Moderation – The video is analyzed by AWS Rekognition for unsafe or prohibited content.

Serverless Moderation Logic – An AWS Lambda function reviews moderation results:

❌ If the video fails moderation, it is rejected and not processed.

✅ If the video passes, it’s approved for generation.

AI Processing – Approved videos are transformed through the custom AI inference model.

Result Delivery – The generated video is stored in Amazon S3 and the URL is returned to the user.

This ensures safety, compliance, and quality control in every request.

---

## 📂 Project Structure

/frontend
├── video-to-video.html # Main page
├── generator.js # Frontend logic for upload, progress, and video rendering
├── styles.css # Custom page styling

/backend
├── app.py # FastAPI backend
├── utils/ # Helper scripts for S3 and AI model handling
└── requirements.txt # Python dependencies

Yaml
---

## 🔧 Installation

### Frontend (Local Development)
```bash
# Clone the repository
git clone https://github.com/your-username/video-to-video.git
cd video-to-video/frontend

Backend
# Navigate to backend
cd ../backend

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app:app --reload

🌐 Deployment

Frontend is deployed via WordPress on a custom page.

Backend is hosted on Render
 with AWS S3 for video storage.

🧪 Testing

Upload multiple video types (.mp4, .mov, .avi)

Check error handling for:

Large files

Unsupported formats

Network failures

🖼️ Demo

Live Page: https://www.lulati.com/video-to-ai-video/

Example Workflow:

Upload your video.

Wait for upload and generation progress.

Preview or download your AI-transformed video.

🧠 Future Enhancements

Add user accounts with video history

Support multiple AI transformation models

Enhance UI for better animations and themes

WebSocket support for real-time processing updates

👨‍💻 Author

Antoine Maxwell

Email: antoinemaxwell0@gmail.com

GitHub: https://github.com/lulatiAI/videotovideogen
GitHub@: Lulatiai

Portfolio: Lulati.com

