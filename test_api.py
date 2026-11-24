import os
from dotenv import load_dotenv
from backend.gemini_helper import get_active_model, invoke_llm

load_dotenv()

print("Loaded key prefix:", (os.getenv("GOOGLE_API_KEY") or "")[:10] + "...")
print("Active Model:", get_active_model())

try:
    response_text = invoke_llm("Say hello and confirm you are ready.")
    print("Response:\n", response_text)
except Exception as e:
    print("Error:", e)
