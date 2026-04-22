import os
import urllib.request
from huggingface_hub import hf_hub_download

os.makedirs("models", exist_ok=True)

print("[*] Downloading twowheeler detection model (YOLOv8n)...")
yolo_url = "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt"
urllib.request.urlretrieve(yolo_url, "models/twowheeler_yolov8n.pt")
print("[+] Downloaded YOLOv8n to models/twowheeler_yolov8n.pt")

print("[*] Downloading License Plate Localization model from HuggingFace...")
try:
    path = hf_hub_download(
        repo_id="yasirfaizahmed/license-plate-object-detection",
        filename="best.pt",
        local_dir="models",
        local_dir_use_symlinks=False
    )
    # Rename to match config
    os.rename(path, "models/lp_localiser.pt")
    print("[+] Downloaded and renamed to models/lp_localiser.pt")
except Exception as e:
    print(f"[-] Error downloading localizer: {e}")
