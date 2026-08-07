import os
import requests

class VoiceService:
    """
    Manages OpenAI Whisper AI (Speech-to-Text) and Murf AI (Text-to-Speech)
    API calls with automatic fallback to Web Speech engines for English & Kannada.
    """
    @staticmethod
    def transcribe_audio_whisper(audio_file_path, language="kn"):
        """
        Transcribes Kannada / English audio file using OpenAI Whisper AI API.
        """
        api_key = os.getenv("WHISPER_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {"error": "Whisper API key not configured", "success": False}

        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        try:
            with open(audio_file_path, "rb") as f:
                files = {"file": f}
                data = {
                    "model": "whisper-1",
                    "language": language
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                if response.status_code == 200:
                    return {"text": response.json().get("text", ""), "success": True}
                else:
                    return {"error": response.text, "success": False}
        except Exception as ex:
            return {"error": str(ex), "success": False}

    @staticmethod
    def generate_speech_murf(text, language="kn"):
        """
        Generates Kannada / English text-to-speech audio using Murf AI API.
        """
        api_key = os.getenv("MURF_API_KEY")
        if not api_key:
            return {"error": "Murf AI API key not configured", "success": False}

        url = "https://api.murf.ai/v1/speech/generate"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        voice_id = "kn-IN-kannada-female" if language == "kn" else "en-US-natalie"
        payload = {
            "voiceId": voice_id,
            "text": text,
            "style": "Conversational",
            "rate": 0,
            "pitch": 0,
            "sampleRate": 24000,
            "format": "MP3"
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            if response.status_code == 200:
                res_data = response.json()
                return {"audio_url": res_data.get("audioFile"), "success": True}
            else:
                return {"error": response.text, "success": False}
        except Exception as ex:
            return {"error": str(ex), "success": False}
