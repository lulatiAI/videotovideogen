# runway_video_to_video.py

from runwayml import RunwayML

def main():
    # Initialize client (make sure RUNWAYML_API_SECRET is set in your env)
    client = RunwayML()

    # Parameters - update these!
    input_video_url = "https://example.com/input_video.mp4"
    reference_image_url = "https://example.com/reference_image.jpg"
    prompt_text = "A cinematic style transformation with vibrant colors and smooth motion."
    model_name = "gen4_aleph"
    output_ratio = "1280:720"
    seed = 12345  # optional, use None for random

    print("Starting video-to-video generation task...")
    task = client.video_to_video.create(
        model=model_name,
        videoUri=input_video_url,
        promptText=prompt_text,
        ratio=output_ratio,
        seed=seed,
        references=[
            {
                "type": "image",
                "uri": reference_image_url
            }
        ],
        contentModeration={
            "publicFigureThreshold": "auto"
        }
    ).wait_for_task_output()

    print("Task completed! Output:")
    print(task)

if __name__ == "__main__":
    main()
