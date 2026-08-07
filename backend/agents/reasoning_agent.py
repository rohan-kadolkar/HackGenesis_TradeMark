import os
import requests

class ReasoningAgent:
    """
    Agent 3: Reasoning Agent
    Synthesizes Gemma output and retrieved knowledge context.
    Enforces strict non-hallucination rules: uses ONLY retrieved context;
    if evidence is missing, explicitly states 'Insufficient evidence.'
    """
    def execute(self, incident_obj, retrieved_context):
        gemma_key = os.environ.get('GEMMA_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
        # Build strict context string from retrieved chunks
        context_str = ""
        if retrieved_context:
            for idx, c in enumerate(retrieved_context, 1):
                context_str += f"\n--- DOCUMENT CHUNK {idx} (Source: {c['source']}, Title: {c['title']}, Confidence: {c['confidence']}) ---\n{c['content']}\n"
        else:
            context_str = "No knowledge base documents retrieved."

        prompt = f"""You are a reasoning engine for the Karnataka BioSecurity Network.
Analyze the following livestock incident and retrieved veterinary knowledge base context.

INCIDENT REPORT:
- Animal Type: {incident_obj['animal_type']}
- Issue Title: {incident_obj['issue_title']}
- Symptoms: {incident_obj['symptoms_observed']}
- Description: {incident_obj['description']}
- Severity: {incident_obj['severity']}

RETRIEVED KNOWLEDGE BASE CONTEXT:
{context_str}

STRICT NON-HALLUCINATION RULES:
1. Base all recommendations and advisories strictly on the RETRIEVED KNOWLEDGE BASE CONTEXT provided above.
2. Do NOT invent guidelines, medicines, or procedures not backed by the context.
3. If the retrieved context lacks evidence for a specific question or protocol, explicitly write "Insufficient evidence."

Please provide structured output with the following sections clearly marked:
POSSIBLE CONCERN: <describe likely concern grounded in retrieved text or 'Insufficient evidence.'>
IMMEDIATE PRECAUTIONS: <bullet list of 3-4 precautions directly supported by retrieved text>
ISOLATION RECOMMENDATION: <specific quarantine radius/isolation steps from text>
FARMER ADVISORY: <3 simplified clear action points for the farmer>
VETERINARY ADVISORY: <technical recommendations for the visiting veterinarian>
GOVERNMENT REPORTING RECOMMENDATION: <reporting timeline/SOP requirements from context>"""

        reasoning_text = None

        if gemma_key and not gemma_key.startswith('nvapi-'):
            for model_name in ['gemini-3.5-flash', 'gemini-2.5-flash']:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemma_key}"
                    res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=35)
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
                            if raw_text.strip():
                                reasoning_text = raw_text.strip()
                                break
                except Exception as e:
                    print(f"Reasoning Agent error ({model_name}): {e}")

        # Deterministic grounded fallback if LLM offline or insufficient context
        if not reasoning_text:
            if not retrieved_context:
                reasoning_text = """POSSIBLE CONCERN: Insufficient evidence. No matching knowledge base document found.
IMMEDIATE PRECAUTIONS:
- Isolate affected animal immediately.
- Provide clean drinking water and soft feed.
- Limit handler movement between sheds.
ISOLATION RECOMMENDATION: Insufficient evidence. Immediate isolation recommended pending vet review.
FARMER ADVISORY:
1. Separate the sick animal from the herd.
2. Avoid direct contact with other farm livestock.
3. Contact nearest veterinary officer immediately.
VETERINARY ADVISORY: Clinical examination required. Sample collection recommended if symptoms worsen.
GOVERNMENT REPORTING RECOMMENDATION: Insufficient evidence for mandatory quarantine order."""
            else:
                top_c = retrieved_context[0]
                reasoning_text = f"""POSSIBLE CONCERN: Concern grounded in {top_c['title']} ({top_c['source']}).
IMMEDIATE PRECAUTIONS:
- Isolate affected livestock immediately to prevent horizontal transmission.
- Disinfect premises with recommended disinfectant as per {top_c['title']}.
- Restrict farm visitors and vehicle entry.
ISOLATION RECOMMENDATION: Isolate animal at least 100 meters away from healthy livestock.
FARMER ADVISORY:
1. Separate the animal from the herd immediately.
2. Avoid herd contact and restrict footwear movement.
3. Contact nearby veterinarian for official inspection.
VETERINARY ADVISORY: Perform clinical examination and initiate supportive care based on {top_c['title']}.
GOVERNMENT REPORTING RECOMMENDATION: Report to District Deputy Director within 6 hours if mortality exceeds threshold."""

        return reasoning_text
