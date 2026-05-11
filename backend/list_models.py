import os
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "AIzaSyCCBgJFt76lSsz_AT6Uty6WUzRvPi478Ss"))

print("Available embedding models:")
for m in genai.list_models():
    if 'embedContent' in m.supported_generation_methods:
        print(m.name)
