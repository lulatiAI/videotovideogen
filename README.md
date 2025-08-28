# 🎥 Video-to-AI Video Generator

Transform regular videos into AI-generated, enhanced videos in just a few clicks.  
This project powers the **Video-to-Video** page on [Lulati.com](https://www.lulati.com/video-to-ai-video/), where users can upload videos, process them through an AI model, and instantly download the generated result.

---

## 🚀 Features

- **Simple Upload:** Drag and drop or browse to select your video.
- **Real-Time Progress:** Displays live upload percentages for a better UX.
- **AI Processing:** Sends video to a backend API for AI-driven transformations.
- **Instant Playback:** Streams the generated video in-browser once ready.
- **Download Option:** Provides a direct download link for the processed video.
- **Error Handling:** Clean error alerts and logs for smoother debugging.

---

## 🛠️ Tech Stack

**Frontend**
- HTML5, CSS3, JavaScript (Vanilla)
- jQuery (for lightweight DOM utilities)
- WordPress integration

**Backend**
- Python (FastAPI)
- AWS S3 (for video storage)
- Render (for backend hosting)
- Custom AI inference pipeline

**Other Tools**
- `boto3` for AWS operations  
- Progress monitoring and blob handling for video responses  

---

## ⚙️ How It Works

1. **User uploads video**  
   - File is validated and sent to the backend API.
2. **Video stored on S3**  
   - Temporary storage in an S3 bucket for processing.
3. **AI processing starts**  
   - Video is analyzed and transformed by the AI model.
4. **Processed video returned**  
   - Downloadable `MP4` is streamed back to the user.
5. **Playback and download**  
   - User can preview or download their AI-enhanced video.

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

