import os
import urllib.request

def download_models():
    models_dir = os.path.join("static", "models")
    os.makedirs(models_dir, exist_ok=True)
    
    base_url = "https://raw.githubusercontent.com/justadudewhohacks/face-api.js/master/weights/"
    files = [
        "ssd_mobilenetv1_model-weights_manifest.json",
        "ssd_mobilenetv1_model-shard1",
        "ssd_mobilenetv1_model-shard2",
        "face_landmark_68_model-weights_manifest.json",
        "face_landmark_68_model-shard1",
        "face_recognition_model-weights_manifest.json",
        "face_recognition_model-shard1",
        "face_recognition_model-shard2"
    ]
    
    for f in files:
        url = base_url + f
        dest = os.path.join(models_dir, f)
        if not os.path.exists(dest):
            print(f"Downloading {f}...")
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"Failed to download {f}: {e}")
        else:
            print(f"Already exists: {f}")

if __name__ == "__main__":
    download_models()
