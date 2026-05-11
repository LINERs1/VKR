import requests
from tqdm import tqdm
import os
url = "https://huggingface.co/SWivid/F5-TTS/resolve/main/F5TTS_Base/model_1200000.safetensors"
path = "models/f5_tts/model_1200000.safetensors"
os.makedirs("models/f5_tts", exist_ok=True)
print(f"Скачивание в {path}...")
r = requests.get(url, stream=True)
total = int(r.headers.get("content-length", 0))
with open(path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="F5-TTS Model") as pb:
    for chunk in r.iter_content(chunk_size=1024*1024):
        if chunk:
            f.write(chunk)
            pb.update(len(chunk))
print("\n--- ЗАГРУЗКА ЗАВЕРШЕНА! ---")
