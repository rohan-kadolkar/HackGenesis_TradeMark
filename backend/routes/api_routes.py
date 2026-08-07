from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from backend.services.ai_service import AIService
from backend.services.incident_service import IncidentService
from backend.services.dashboard_service import DashboardService
from backend.services.voice_service import VoiceService
import base64
import os
import tempfile

api_bp = Blueprint('api', __name__)
ai_service = AIService()

# Reference to global RAG service set on app startup
_rag_service = None

def init_api_rag_service(rag_service_instance):
    global _rag_service
    _rag_service = rag_service_instance

@api_bp.route('/analyze-image', methods=['POST'])
@login_required
def analyze_image_endpoint():
    """
    POST /analyze-image
    Analyzes an uploaded image using Gemma Vision API and runs Agentic RAG pipeline.
    """
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    try:
        image_bytes = file.read()
        mime_type = file.content_type or 'image/jpeg'
        target_lang = request.form.get('language') or request.args.get('language') or 'en'

        # Step 1: Gemma Vision Analysis
        gemma_json = ai_service.analyze_image_with_gemma(image_bytes, mime_type)

        # Step 2: Run Agentic RAG Pipeline
        if _rag_service:
            rag_output = _rag_service.run_pipeline(gemma_json)
        else:
            rag_output = {"gemma_raw": gemma_json}

        incident_data = rag_output.get("incident", {})

        # Step 3: If target language is Kannada, translate auto-fill text fields to Kannada
        if target_lang == 'kn':
            if gemma_json.get("possible_concern"):
                gemma_json["possible_concern"] = ai_service.translate_text_to_kannada(gemma_json["possible_concern"])
            if gemma_json.get("farmer_action"):
                gemma_json["farmer_action"] = ai_service.translate_text_to_kannada(gemma_json["farmer_action"])
            if isinstance(gemma_json.get("visible_abnormalities"), list):
                gemma_json["visible_abnormalities"] = [ai_service.translate_text_to_kannada(s) for s in gemma_json["visible_abnormalities"]]
            elif isinstance(gemma_json.get("visible_abnormalities"), str):
                gemma_json["visible_abnormalities"] = ai_service.translate_text_to_kannada(gemma_json["visible_abnormalities"])

            if incident_data.get("issue_title"):
                incident_data["issue_title"] = ai_service.translate_text_to_kannada(incident_data["issue_title"])
            if incident_data.get("symptoms"):
                incident_data["symptoms"] = ai_service.translate_text_to_kannada(incident_data["symptoms"])
            if incident_data.get("description"):
                incident_data["description"] = ai_service.translate_text_to_kannada(incident_data["description"])

        return jsonify({
            'success': True,
            'gemma_output': gemma_json,
            'analysis': incident_data,
            'rag_response': rag_output
        })

    except Exception as e:
        print(f"Error in /analyze-image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/rag/query', methods=['POST'])
@login_required
def rag_query_endpoint():
    """
    POST /rag/query
    Direct Agentic RAG semantic search and reasoning query.
    Body JSON: { "animal_type": "cattle", "symptoms": "Fever, tongue blisters", "severity": "high" }
    """
    data = request.get_json() or {}
    animal_type = data.get("animal_type", "cattle")
    symptoms = data.get("symptoms", "Fever and skin lesions")
    severity = data.get("severity", "high")

    try:
        if _rag_service:
            result = _rag_service.direct_rag_query(animal_type, symptoms, severity)
        else:
            return jsonify({'error': 'RAG service not initialized'}), 500

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/vet/verify', methods=['POST'])
@login_required
def vet_verify_endpoint():
    """
    POST /vet/verify
    Processes Vet action (✓ Verify, ✗ Reject, ✎ Edit + Comment Box).
    Body JSON or Form: { "incident_id": 1, "action": "verify"|"reject"|"edit", "vet_notes": "...", "edited_fields": {...} }
    """
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized. Vet role required.'}), 403

    data = request.get_json() if request.is_json else request.form.to_dict()
    
    incident_id = data.get("incident_id")
    action = data.get("action")  # 'verify', 'reject', 'save_changes', 'edit'
    ai_rating = data.get("ai_assessment_rating", "correct")
    vet_notes = data.get("vet_notes", "")
    edited_fields = data.get("edited_fields") or {}

    if not incident_id or not action:
        return jsonify({'error': 'Missing incident_id or action'}), 400

    vet_profile = current_user.vet_profile
    if not vet_profile:
        return jsonify({'error': 'Vet profile not found'}), 400

    incident, err = IncidentService.vet_verify_incident(
        incident_id=int(incident_id),
        vet_id=vet_profile.id,
        action=action,
        ai_assessment_rating=ai_rating,
        vet_notes=vet_notes,
        edited_fields=edited_fields
    )

    if err:
        return jsonify({'error': err}), 400

    return jsonify({
        'success': True,
        'message': f'Incident #{incident.id} report successfully processed ({action.replace("_", " ").title()})!',
        'incident_status': incident.status,
        'vet_verified': incident.vet_verified,
        'district_alert_triggered': incident.severity in ['high', 'critical'],
        'farmer_notified': True
    })


@api_bp.route('/vet/incidents', methods=['GET'])
@login_required
def vet_incidents_endpoint():
    """
    GET /vet/incidents
    Returns list of incidents for vet's district with RAG details.
    """
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    profile = current_user.vet_profile
    status_filter = request.args.get('status')
    
    incidents = DashboardService.get_vet_incidents(profile.district_id, status_filter)

    results = []
    for inc in incidents:
        results.append({
            "id": inc.id,
            "title": inc.title,
            "animal_type": inc.animal_type,
            "symptoms": inc.symptoms,
            "severity": inc.severity,
            "status": inc.status,
            "vet_verified": inc.vet_verified,
            "created_at": inc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "images": inc.get_images_list(),
            "rag_data": inc.get_rag_data(),
            "vet_correction": inc.get_vet_correction_data()
        })

    return jsonify({'success': True, 'incidents': results})


@api_bp.route('/district/dashboard', methods=['GET'])
@login_required
def district_dashboard_endpoint():
    """
    GET /district/dashboard
    Returns outbreak events, risk levels, and GIS map markers for District Head.
    """
    district_id = request.args.get('district_id')
    if not district_id and current_user.role == 'district_head':
        district_id = current_user.district_profile.district_id
    elif not district_id:
        district_id = 1

    data = DashboardService.get_district_dashboard(int(district_id))
    if not data:
        return jsonify({'error': 'District not found'}), 404

    return jsonify({'success': True, 'data': data})


@api_bp.route('/state/dashboard', methods=['GET'])
@login_required
def state_dashboard_endpoint():
    """
    GET /state/dashboard
    Returns aggregated heatmap points, disease trends, and verification stats for State Head.
    """
    data = DashboardService.get_state_dashboard()
    return jsonify({'success': True, 'data': data})


@api_bp.route('/voice/stt', methods=['POST'])
def voice_stt_endpoint():
    """
    POST /api/voice/stt
    Transcribes audio using OpenAI Whisper AI API.
    """
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided', 'success': False}), 400

    audio_file = request.files['audio']
    lang = request.form.get('language', 'kn')

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    res = VoiceService.transcribe_audio_whisper(tmp_path, language=lang)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    return jsonify(res)


@api_bp.route('/voice/tts', methods=['POST'])
def voice_tts_endpoint():
    """
    POST /api/voice/tts
    Synthesizes Kannada / English text into audio using Murf AI.
    """
    data = request.get_json() if request.is_json else request.form.to_dict()
    text = data.get('text', '')
    lang = data.get('language', 'kn')

    if not text:
        return jsonify({'error': 'No text provided', 'success': False}), 400

    res = VoiceService.generate_speech_murf(text, language=lang)
    return jsonify(res)


@api_bp.route('/translate', methods=['POST'])
def translate_endpoint():
    """
    POST /api/translate
    Translates text dynamically using AIService / Gemma.
    """
    data = request.get_json() if request.is_json else request.form.to_dict()
    text = data.get('text', '')
    if not text:
        return jsonify({'translated': '', 'success': False})

    translated = ai_service.translate_text_to_kannada(text)
    return jsonify({'translated': translated, 'success': True})
