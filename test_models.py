import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Configure with your Gemini API key
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# List available models
print("🔍 Available Gemini models on your account:")
for m in genai.list_models():
    print(f"- {m.name} (supports: {m.supported_generation_methods})")
