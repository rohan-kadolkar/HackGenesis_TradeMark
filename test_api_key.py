import os
import requests
from dotenv import load_dotenv

# 1. Load the .env file (make sure your file is named exactly .env)
load_dotenv()

# 2. Get the API key from the environment
api_key = os.environ.get('GEMMA_API_KEY') or os.environ.get('GEMINI_API_KEY')

print("--- API KEY TEST ---")
if not api_key:
    print("❌ ERROR: No API key found! Make sure you renamed .env.example to .env and added your key.")
    exit(1)

print(f"✅ Found API Key starting with: {api_key[:5]}...")

# 3. Get list of available models
print("\nFetching available models from Google API...")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    res = requests.get(url, timeout=10)
    
    if res.status_code == 200:
        data = res.json()
        models = [m['name'] for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
        print(f"✅ SUCCESS! Found {len(models)} models that support text generation.")
        print("Available models:")
        for m in models:
            if 'gemini' in m.lower():
                print(f"  - {m}")
    else:
        print(f"❌ ERROR {res.status_code}: {res.text}")
except requests.exceptions.RequestException as e:
    print(f"❌ NETWORK ERROR: {e}")
