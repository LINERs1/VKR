import os
import requests

api_key = os.environ.get("GEMINI_API_KEY", "AIzaSyCCBgJFt76lSsz_AT6Uty6WUzRvPi478Ss")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
resp = requests.get(url)
models = resp.json().get('models', [])
print("Supported generateContent models:")
for m in models:
    if 'generateContent' in m.get('supportedGenerationMethods', []):
        print(m.get('name'))
