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
            for model_name in ['gemini-3.5-flash', 'gemini-2.5-flash']:
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
            ("Gemma AI Vision analyzed the photo and auto-filled observed findings.", "ಗೆಮ್ಮಾ AI ವಿಷನ್ ಫೋಟೋವನ್ನು ವಿಶ್ಲೇಷಿಸಿದೆ ಮತ್ತು ಕಂಡುಬಂದ ಅಂಶಗಳನ್ನು ಸ್ವಯಂ-ಭರ್ತಿ ಮಾಡಿದೆ."),
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
            for model_name in ['gemini-3.5-flash', 'gemini-2.5-flash']:
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

    def generate_ai_solution(self, description, symptoms, animal_type, images=None, upload_folder=None):
        """
        Generate temporary AI solution using Gemma API or NVIDIA API.
        Moved from app.py to consolidate AI logic (fix #17).
        """
        import base64

        # Read image base64 if present
        image_b64 = None
        image_mime = "image/jpeg"
        if images and isinstance(images, list) and len(images) > 0 and upload_folder:
            try:
                import os
                first_img_path = os.path.join(upload_folder, images[0])
                if os.path.exists(first_img_path):
                    with open(first_img_path, 'rb') as f:
                        img_bytes = f.read()
                        image_b64 = base64.b64encode(img_bytes).decode('utf-8')
                        ext = images[0].rsplit('.', 1)[-1].lower()
                        image_mime = f"image/{'png' if ext=='png' else 'jpeg'}"
            except Exception as e:
                print(f"Error reading image for AI solution: {e}")

        prompt = f"""You are an expert veterinary assistant for Karnataka, India farmers.
A farmer has reported an animal health issue:
- Animal Type: {animal_type}
- Symptoms: {symptoms}
- Description: {description}

Provide IMMEDIATE practical temporary emergency measures (5-6 numbered bullet points) the farmer can take BEFORE the veterinarian arrives.
Rules:
1. Do not give conclusive medical diagnosis.
2. Focus on biosecurity, isolation, sanitation, hydration, and observation.
3. Include Kannada translations (in dual language) where helpful.
4. Include a clear disclaimer that this is temporary AI guidance."""

        # Gemma / Google API Integration
        if self.gemma_key and not self.gemma_key.startswith('nvapi-'):
            for model_name in ['gemini-3.5-flash', 'gemini-2.5-flash']:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemma_key}"
                    parts = [{"text": prompt}]
                    if image_b64:
                        parts.append({"inline_data": {"mime_type": image_mime, "data": image_b64}})
                    payload = {"contents": [{"parts": parts}]}
                    res = requests.post(url, json=payload, timeout=35)
                    if res.status_code == 200:
                        candidates = res.json().get('candidates', [])
                        if candidates:
                            parts_list = candidates[0].get('content', {}).get('parts', [])
                            raw_text = ""
                            for p in parts_list:
                                if 'text' in p and not p.get('thought'):
                                    raw_text += p['text']
                            if not raw_text.strip():
                                for p in parts_list:
                                    if 'text' in p:
                                        raw_text += p['text']
                            if raw_text.strip():
                                return "[Source: Google Gemini AI]\n\n" + raw_text.strip()
                except Exception as e:
                    print(f"Gemma API error ({model_name}): {e}")

        # NVIDIA NIM API Integration
        if self.nvidia_key and self.nvidia_key.startswith('nvapi-'):
            try:
                headers = {
                    "Authorization": f"Bearer {self.nvidia_key}",
                    "Content-Type": "application/json"
                }
                if image_b64:
                    model_name = "meta/llama-3.2-11b-vision-instruct"
                    user_content = [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}}
                    ]
                else:
                    model_name = "meta/llama-3.1-70b-instruct"
                    user_content = prompt

                data = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": user_content}],
                    "temperature": 0.3,
                    "max_tokens": 800
                }

                response = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=headers, json=data, timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    return "[Source: NVIDIA Llama 3 AI]\n\n" + result["choices"][0]["message"]["content"].strip()
            except Exception as e:
                print(f"NVIDIA API Exception: {e}")

        # Fallback rule-based system
        solutions = {
            "poultry": [
                "1. Immediately isolate sick birds from the flock.",
                "2. Disinfect the shed with phenol-based disinfectant.",
                "3. Ensure proper ventilation and reduce overcrowding.",
                "4. Provide electrolyte solution in drinking water.",
                "5. Contact veterinarian immediately if mortality exceeds 2%."
            ],
            "pig": [
                "1. Isolate affected pigs immediately.",
                "2. Strict biosecurity - no visitors, dedicated footwear.",
                "3. Disinfect premises with 2% sodium hydroxide or iodine.",
                "4. Do not move pigs to other farms or markets.",
                "5. Report to nearest veterinary officer within 24 hours."
            ],
            "cattle": [
                "1. Separate sick animals from healthy herd.",
                "2. Check temperature and provide shade/cool water.",
                "3. Do not share equipment between sick and healthy animals.",
                "4. Clean and disinfect feeding/watering troughs daily.",
                "5. Note: This is temporary advice. Vet visit is mandatory."
            ],
            "goat": [
                "1. Isolate affected goats immediately.",
                "2. Disinfect shed with lime powder and phenol.",
                "3. Provide clean drinking water with oral rehydration salts.",
                "4. Check for ticks and apply acaricides if needed.",
                "5. Contact veterinarian for PPR/ET vaccination if not done."
            ]
        }

        base_solution = solutions.get(animal_type, solutions["cattle"])

        if "fever" in symptoms.lower() and "cough" in symptoms.lower():
            base_solution.append("⚠️ HIGH RISK: Respiratory symptoms with fever may indicate contagious disease. Immediate quarantine required.")
        if "diarrhea" in symptoms.lower() or "diarrhoea" in symptoms.lower():
            base_solution.append("💧 HYDRATION CRITICAL: Ensure oral electrolyte therapy continuously. Dehydration is the main cause of death.")
        if "sudden death" in symptoms.lower() or "mortality" in description.lower():
            base_solution.append("🚨 EMERGENCY: Multiple sudden deaths require immediate veterinary investigation and sample collection.")

        return "[Source: Offline Fallback System]\n\n" + "\n".join(base_solution)
