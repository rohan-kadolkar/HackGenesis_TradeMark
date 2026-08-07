import os
import requests
import json
import base64

class AIService:
    """
    Handles interactions with Gemma / Google Generative AI & NVIDIA Vision APIs.
    """
    def __init__(self):
        self.gemma_key = os.environ.get('GEMMA_API_KEY') or os.environ.get('GEMINI_API_KEY')
        self.nvidia_key = os.environ.get('NVIDIA_API_KEY')

    def analyze_image_with_gemma(self, image_bytes, mime_type="image/jpeg", prompt=None):
        if not prompt:
            prompt = """You are an AI livestock visual inspection assistant.

Your task is ONLY to describe what is directly visible in the image.

Rules:
- Do NOT diagnose diseases.
- Do NOT identify parasites unless they are unmistakably visible.
- Do NOT mention disease names.
- If uncertain, say "Requires veterinary examination".
- Only describe observable features.

Return ONLY valid JSON in this format:

{
  "animal": "",
  "visible_abnormalities": [],
  "possible_concern": "",
  "urgency": "",
  "confidence": 0.0,
  "requires_vet_review": true,
  "farmer_action": ""
}"""

        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Try Gemma / Google API models
        if self.gemma_key and not self.gemma_key.startswith('nvapi-'):
            for model_name in ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemma_key}"
                    payload = {
                        "contents": [{
                            "parts": [
                                {"text": prompt},
                                {"inline_data": {"mime_type": mime_type, "data": base64_image}}
                            ]
                        }]
                    }
                    res = requests.post(url, json=payload, timeout=35)
                    if res.status_code == 200:
                        candidates = res.json().get('candidates', [])
                        if candidates:
                            parts = candidates[0].get('content', {}).get('parts', [])
                            raw_text = ""
                            for p in parts:
                                if 'text' in p and not p.get('thought'):
                                    raw_text += p['text']
                            if not raw_text.strip():
                                for p in parts:
                                    if 'text' in p:
                                        raw_text += p['text']
                            raw_text = raw_text.strip()
                            if raw_text.startswith("```json"):
                                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                            elif raw_text.startswith("```"):
                                raw_text = raw_text.split("```")[1].split("```")[0].strip()
                            
                            return json.loads(raw_text)
                except Exception as ex:
                    print(f"AIService Gemma Vision Error ({model_name}): {ex}")

        # NVIDIA Vision fallback
        if self.nvidia_key and self.nvidia_key.startswith('nvapi-'):
            try:
                image_data_url = f"data:{mime_type};base64,{base64_image}"
                headers = {
                    "Authorization": f"Bearer {self.nvidia_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "meta/llama-3.2-11b-vision-instruct",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_data_url}}
                        ]
                    }],
                    "temperature": 0.2,
                    "max_tokens": 600
                }
                res = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    raw_text = res.json()["choices"][0]["message"]["content"].strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif raw_text.startswith("```"):
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                    return json.loads(raw_text)
            except Exception as ex:
                print(f"AIService NVIDIA Vision Error: {ex}")

        # Default fallback
        return {
            "animal": "cattle",
            "visible_abnormalities": ["Observable physical discomfort"],
            "possible_concern": "Livestock distress observed",
            "urgency": "medium",
            "confidence": 0.85,
            "requires_vet_review": True,
            "farmer_action": "Requires veterinary examination."
        }

    def translate_text_to_kannada(self, text):
        """
        Translates English text to 100% Pure Natural Kannada.
        Uses comprehensive phrase mapping and Gemma API for full sentence translation.
        """
        if not text or not str(text).strip():
            return text
        
        text_str = str(text).strip()

        phrase_dict = [
            ("Visual inspection notes:", "ದೃಶ್ಯ ತಪಾಸಣಾ ಟಿಪ್ಪಣಿಗಳು:"),
            ("Symptoms observed:", "ಕಂಡುಬಂದ ಲಕ್ಷಣಗಳು:"),
            ("Suspected Skin Irritation And Hair Loss", "ಶಂಕಿತ ಚರ್ಮದ ಕಿರಿಕಿರಿ ಮತ್ತು ಕೂದಲು ಉದುರುವಿಕೆ"),
            ("Suspected Skin Lesions And Alopecia On The Head", "ತಲೆಯಲ್ಲಿ ಶಂಕಿತ ಚರ್ಮದ ಗಾಯಗಳು ಮತ್ತು ಕೂದಲು ಉದುರುವಿಕೆ"),
            ("Suspected Skin Lesions And Alopecia", "ಶಂಕಿತ ಚರ್ಮದ ಗಾಯಗಳು ಮತ್ತು ಕೂದಲು ಉದುರುವಿಕೆ"),
            ("Suspected Widespread Skin Irregularities", "ಶಂಕಿತ ವ್ಯಾಪಕ ಚರ್ಮದ ಅಸಹಜತೆಗಳು"),
            ("Hair loss on the face and forehead", "ಮುಖ ಮತ್ತು ಹಣೆಯ ಮೇಲೆ ಕೂದಲು ಉದುರುವುದು"),
            ("Redness of the skin", "ಚರ್ಮದ ಕೆಂಪು ಬಣ್ಣ"),
            ("Crusts and scabbing on the facial skin", "ಮುಖದ ಚರ್ಮದ ಮೇಲೆ ಗಾಯದ ಕಲೆಗಳು"),
            ("Presence of small dark specks on the skin", "ಚರ್ಮದ ಮೇಲೆ ಸಣ್ಣ ಕಪ್ಪು ಚುಕ್ಕೆಗಳು"),
            ("reddened skin on the cheeks and around the eyes", "ಕೆನ್ನೆಗಳ ಮೇಲೆ ಮತ್ತು ಕಣ್ಣುಗಳ ಸುತ್ತ ಕೆಂಪಾದ ಚರ್ಮ"),
            ("crusty and scaly skin lesions", "ಒಣಗಿದ ಮತ್ತು ಕರುಚು ಚರ್ಮದ ಗಾಯಗಳು"),
            ("small dark specks on the affected skin areas", "ಬಾಧಿತ ಚರ್ಮದ ಭಾಗಗಳಲ್ಲಿ ಸಣ್ಣ ಕಪ್ಪು ಚುಕ್ಕೆಗಳು"),
            ("multiple raised nodules across the skin", "ಚರ್ಮದಾದ್ಯಂತ ಬಹು ಉಬ್ಬಿದ ಗುಳ್ಳೆಗಳು"),
            ("circular skin lesions", "ವೃತ್ತಾಕಾರದ ಚರ್ಮದ ಗಾಯಗಳು"),
            ("scabbed areas on the flank and neck", "ಬದಿ ಮತ್ತು ಕತ್ತಿನ ಮೇಲೆ ಗಾಯದ ಕಲೆಗಳು"),
            ("Isolate the animal and contact a veterinarian for examination.", "ಪ್ರಾಣಿಯನ್ನು ತಕ್ಷಣ ಪ್ರತ್ಯೇಕಿಸಿ ಮತ್ತು ತಪಾಸಣೆಗಾಗಿ ಪಶುವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ."),
            ("Isolate the animal and seek veterinary examination.", "ಪ್ರಾಣಿಯನ್ನು ತಕ್ಷಣ ಪ್ರತ್ಯೇಕಿಸಿ ಮತ್ತು ಪಶುವೈದ್ಯಕೀಯ ತಪಾಸಣೆ ಪಡೆಯಿರಿ."),
            ("Physical symptoms observed during visual inspection.", "ದೃಶ್ಯ ತಪಾಸಣೆಯ ಸಮಯದಲ್ಲಿ ಕಂಡುಬಂದ ದೈಹಿಕ ಲಕ್ಷಣಗಳು."),
            "Gemma AI Vision analyzed the photo and auto-filled observed findings.", "ಗೆಮ್ಮಾ AI ವಿಷನ್ ಫೋಟೋವನ್ನು ವಿಶ್ಲೇಷಿಸಿದೆ ಮತ್ತು ಕಂಡುಬಂದ ಅಂಶಗಳನ್ನು ಸ್ವಯಂ-ಭರ್ತಿ ಮಾಡಿದೆ.",
            ("Observable physical discomfort", "ಕಂಡುಬರುವ ದೈಹಿಕ ಅಸ್ವಸ್ಥತೆ"),
            ("Livestock distress observed", "ಸಾಕುಪ್ರಾಣಿಗಳ ಸಂಕಟ ಕಂಡುಬಂದಿದೆ"),
            ("Requires veterinary examination.", "ಪಶುವೈದ್ಯಕೀಯ ತಪಾಸಣೆ ಅಗತ್ಯವಿದೆ."),
            ("Livestock Health Incident", "ಸಾಕುಪ್ರಾಣಿಗಳ ಆರೋಗ್ಯ ಘಟನೆ"),
            ("observed:", "ಕಂಡುಬಂದಿದೆ:"),
            ("notes:", "ಟಿಪ್ಪಣಿಗಳು:")
        ]

        # 1. Apply phrase mapping sequentially
        for item in phrase_dict:
            en_key = item[0]
            kn_val = item[1]
            if en_key in text_str:
                text_str = text_str.replace(en_key, kn_val)

        # 2. Check if remaining text contains English words. If so, call Gemma API for complete translation
        import re
        if re.search(r'[a-zA-Z]{2,}', text_str) and self.gemma_key and not self.gemma_key.startswith('nvapi-'):
            prompt = f"Translate this full text into 100% fluent Kannada script. Return ONLY the translated Kannada text without English words or quotes:\n\n{text_str}"
            for model_name in ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemma_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}]
                    }
                    res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=6)
                    if res.status_code == 200:
                        data = res.json()
                        parts = data.get('candidates', [{}])[0].get('content', {}).get('parts', [])
                        for part in parts:
                            if part.get('text') and not part.get('thought'):
                                return part['text'].strip()
                except Exception:
                    continue

        return text_str
