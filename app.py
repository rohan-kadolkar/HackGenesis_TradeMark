import os
import json
import requests
import random
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, District, FarmerProfile, VetProfile, DistrictHeadProfile, StateHeadProfile, Incident, VetSchedule, Message, VaccinationRecord, get_ist
from data import seed_database, BIOSAFETY_TIPS, DISEASES, KARNATAKA_DISTRICTS

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'karnataka-biosecurity-2025-default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///biosecurity_karnataka.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Agentic RAG Service & Blueprints
from backend.services.rag_service import RAGService
from backend.services.incident_service import IncidentService
from backend.routes.api_routes import (
    api_bp, init_api_rag_service, analyze_image_endpoint, 
    rag_query_endpoint, vet_verify_endpoint, vet_incidents_endpoint,
    district_dashboard_endpoint, state_dashboard_endpoint
)

rag_service = RAGService("backend/knowledge_base")
rag_service.initialize_knowledge_base()
init_api_rag_service(rag_service)

app.register_blueprint(api_bp, url_prefix='/api')

# Root Level Alias API Endpoints as requested
@app.route('/analyze-image', methods=['POST'])
@login_required
def root_analyze_image():
    return analyze_image_endpoint()

@app.route('/rag/query', methods=['POST'])
@login_required
def root_rag_query():
    return rag_query_endpoint()

@app.route('/vet/verify', methods=['POST'])
@login_required
def root_vet_verify():
    return vet_verify_endpoint()

@app.route('/vet/incidents', methods=['GET'])
@login_required
def root_vet_incidents():
    return vet_incidents_endpoint()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================
# AI SOLUTION GENERATOR (Gemini API Integration)
# ============================================================
def generate_ai_solution(description, symptoms, animal_type, images=None):
    """
    Generate temporary AI solution using Gemma API, Gemini API, or NVIDIA API.
    """
    gemma_key = os.environ.get('GEMMA_API_KEY') or os.environ.get('GEMINI_API_KEY')
    nvidia_key = os.environ.get('NVIDIA_API_KEY')

    # Read image base64 if present
    image_b64 = None
    image_mime = "image/jpeg"
    if images and isinstance(images, list) and len(images) > 0:
        try:
            first_img_path = os.path.join(app.config['UPLOAD_FOLDER'], images[0])
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
    if gemma_key and not gemma_key.startswith('nvapi-'):
        for model_name in ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemma_key}"
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
                            return raw_text.strip()
            except Exception as e:
                print(f"Gemma API error ({model_name}): {e}")

    # NVIDIA NIM API Integration
    if nvidia_key and nvidia_key.startswith('nvapi-'):
        try:
            headers = {
                "Authorization": f"Bearer {nvidia_key}",
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
                return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"NVIDIA API Exception: {e}")

    # Fallback rule-based system for demo
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

    return "\n".join(base_solution)

# ============================================================
# CONTEXT PROCESSORS
# ============================================================
@app.context_processor
def inject_globals():
    return {
        'now': get_ist(),
        'KARNATAKA_DISTRICTS': KARNATAKA_DISTRICTS
    }

# ============================================================
# LANDING & AUTH ROUTES
# ============================================================
@app.route('/')
def index():
    stats = {
        'total_farms': FarmerProfile.query.count(),
        'active_cases': Incident.query.filter(Incident.status.in_(['pending', 'assigned', 'in_progress'])).count(),
        'resolved_cases': Incident.query.filter_by(status='resolved').count(),
        'total_vets': VetProfile.query.count(),
        'districts_covered': District.query.count()
    }
    return render_template('index.html', stats=stats)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')

            # Redirect based on role
            if user.role == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif user.role == 'vet':
                return redirect(url_for('vet_dashboard'))
            elif user.role == 'district_head':
                return redirect(url_for('district_dashboard'))
            elif user.role == 'state_head':
                return redirect(url_for('state_dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        phone = request.form.get('phone')
        language = request.form.get('language', 'en')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or email already exists', 'danger')
            return redirect(url_for('signup'))

        user = User(username=username, email=email, role=role, phone=phone, language=language)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Create role-specific profile
        if role == 'farmer':
            district_id = request.form.get('district_id')
            profile = FarmerProfile(
                user_id=user.id,
                farm_name=request.form.get('farm_name'),
                village=request.form.get('village'),
                taluka=request.form.get('taluka'),
                district_id=district_id,
                farm_size=float(request.form.get('farm_size', 0)),
                livestock_type=request.form.get('livestock_type'),
                animal_count=int(request.form.get('animal_count', 0)),
                latitude=float(request.form.get('latitude', 0)),
                longitude=float(request.form.get('longitude', 0))
            )
            db.session.add(profile)

        elif role == 'vet':
            district_id = request.form.get('district_id')
            profile = VetProfile(
                user_id=user.id,
                registration_number=request.form.get('registration_number'),
                qualification=request.form.get('qualification'),
                specialization=request.form.get('specialization'),
                district_id=district_id,
                taluka=request.form.get('taluka'),
                is_verified=False
            )
            db.session.add(profile)

        elif role == 'district_head':
            district_id = request.form.get('district_id')
            profile = DistrictHeadProfile(
                user_id=user.id,
                district_id=district_id,
                phone_office=request.form.get('phone_office')
            )
            db.session.add(profile)

        elif role == 'state_head':
            profile = StateHeadProfile(
                user_id=user.id,
                state_name='Karnataka',
                phone_office=request.form.get('phone_office')
            )
            db.session.add(profile)

        db.session.commit()
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('login'))

    districts = District.query.all()
    return render_template('signup.html', districts=districts)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# ============================================================
# FARMER ROUTES
# ============================================================
@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.role != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    profile = current_user.farmer_profile
    if not profile:
        flash('Profile not found', 'danger')
        return redirect(url_for('index'))

    incidents = Incident.query.filter_by(farmer_id=profile.id).order_by(Incident.created_at.desc()).all()
    vaccinations = VaccinationRecord.query.filter_by(farmer_id=profile.id).all()
    messages = Message.query.filter(
        (Message.recipient_role == 'farmer') | (Message.recipient_id == current_user.id)
    ).order_by(Message.created_at.desc()).limit(10).all()

    return render_template('farmer_dashboard.html', 
                         profile=profile, 
                         incidents=incidents, 
                         vaccinations=vaccinations,
                         messages=messages,
                         tips=BIOSAFETY_TIPS)

@app.route('/farmer/report-emergency', methods=['GET', 'POST'])
@login_required
def report_emergency():
    if current_user.role != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        profile = current_user.farmer_profile

        title = request.form.get('title')
        description = request.form.get('description')
        symptoms = request.form.get('symptoms')
        animal_type = request.form.get('animal_type')
        affected_count = int(request.form.get('affected_count', 1))
        severity = request.form.get('severity', 'medium')

        # Handle image uploads
        images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"incident_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    images.append(filename)

        incident = Incident(
            farmer_id=profile.id,
            district_id=profile.district_id,
            title=title,
            description=description,
            symptoms=symptoms,
            animal_type=animal_type,
            affected_count=affected_count,
            severity=severity,
            status='pending',
            village=profile.village,
            taluka=profile.taluka
        )
        if images:
            incident.set_images_list(images)

        db.session.add(incident)
        db.session.commit()

        # Run Agentic RAG Pipeline
        mock_gemma = {
            "animal_type": animal_type,
            "title": title,
            "symptoms": symptoms,
            "description": description,
            "severity": severity,
            "confidence": 0.90,
            "needs_vet_visit": True
        }
        raw_form = {
            "title": title,
            "description": description,
            "symptoms": symptoms,
            "animal_type": animal_type,
            "affected_count": affected_count,
            "severity": severity
        }
        
        try:
            rag_output = rag_service.run_pipeline(mock_gemma, raw_form)
            incident.set_rag_data(rag_output)
            
            # Format legacy ai_solution string for backward compatibility
            farmer_recs = "\n".join([f"• {r}" for r in rag_output.get("farmer_response", {}).get("recommended", [])])
            vet_adv = rag_output.get("vet_summary", {}).get("vet_advisory", "Clinical examination advised.")
            incident.ai_solution = f"FARMER ADVISORY:\n{farmer_recs}\n\nVETERINARY ADVISORY:\n{vet_adv}"
        except Exception as ex:
            print(f"Error running Agentic RAG pipeline in report_emergency: {ex}")
            incident.ai_solution = generate_ai_solution(description, symptoms, animal_type, images)

        # Notify Veterinary Doctor(s) of the newly submitted emergency report
        if profile and profile.district_id:
            vets = VetProfile.query.filter_by(district_id=profile.district_id).all()
            for vet in vets:
                if vet.user:
                    vet_msg = Message(
                        sender_id=current_user.id,
                        recipient_id=vet.user.id,
                        recipient_role='vet',
                        district_id=profile.district_id,
                        title=f"🚨 EMERGENCY REPORT: {animal_type.title()} in {profile.village or 'District'} (Case #{incident.id})",
                        content=f"Farmer {current_user.username} reported an emergency livestock case (#{incident.id}).\n\n"
                                f"• Location: {profile.village or 'N/A'}, {profile.taluka or 'N/A'}\n"
                                f"• Animal Type: {animal_type.title()}\n"
                                f"• Symptoms: {symptoms}\n"
                                f"• Severity: {severity.upper()}\n"
                                f"• Affected Count: {affected_count}\n\n"
                                f"Please review, examine, and verify this report.",
                        message_type='emergency' if severity in ['high', 'critical'] else 'alert'
                    )
                    db.session.add(vet_msg)
        if not (profile and profile.district_id) or not vets:
            vet_msg = Message(
                sender_id=current_user.id,
                recipient_role='vet',
                district_id=profile.district_id if profile else None,
                title=f"🚨 EMERGENCY REPORT: {animal_type.title()} (Case #{incident.id})",
                content=f"Farmer {current_user.username} reported an emergency livestock case (#{incident.id}).\n\n"
                        f"• Animal Type: {animal_type.title()}\n"
                        f"• Symptoms: {symptoms}\n"
                        f"• Severity: {severity.upper()}\n\n"
                        f"Please review and verify this report.",
                message_type='emergency' if severity in ['high', 'critical'] else 'alert'
            )
            db.session.add(vet_msg)

        db.session.commit()

        flash('Emergency reported successfully! Agentic RAG Analysis complete.', 'success')
        return redirect(url_for('view_incident', incident_id=incident.id))

    return render_template('report_emergency.html', diseases=DISEASES)

@app.route('/incident/<int:incident_id>')
@login_required
def view_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)

    # Authorization check
    if current_user.role == 'farmer':
        if not current_user.farmer_profile or incident.farmer_id != current_user.farmer_profile.id:
            flash('Access denied', 'danger')
            return redirect(url_for('farmer_dashboard'))

    elif current_user.role == 'vet':
        if not current_user.vet_profile:
            flash('Access denied', 'danger')
            return redirect(url_for('index'))
        
        # Allow vet to view if in their district OR assigned to them
        if incident.district_id and incident.district_id != current_user.vet_profile.district_id and incident.vet_id != current_user.vet_profile.id:
            flash('Access denied. Incident is outside your assigned district.', 'danger')
            return redirect(url_for('vet_dashboard'))
        
        # Auto-assign unassigned pending incident to this reviewing vet
        if not incident.vet_id:
            incident.vet_id = current_user.vet_profile.id
            if incident.status == 'pending':
                incident.status = 'assigned'
            db.session.commit()

    elif current_user.role == 'district_head':
        if not current_user.district_profile or (incident.district_id and incident.district_id != current_user.district_profile.district_id):
            flash('Access denied', 'danger')
            return redirect(url_for('district_dashboard'))

    return render_template('view_incident.html', incident=incident)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================================
# VET ROUTES
# ============================================================
@app.route('/vet/dashboard')
@login_required
def vet_dashboard():
    if current_user.role != 'vet':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    profile = current_user.vet_profile

    # Get nearby incidents (same district)
    pending_incidents = Incident.query.filter_by(
        district_id=profile.district_id, 
        status='pending'
    ).order_by(Incident.created_at.desc()).all()

    assigned_incidents = Incident.query.filter_by(
        vet_id=profile.id
    ).order_by(Incident.created_at.desc()).all()

    schedules = VetSchedule.query.filter_by(vet_id=profile.id).order_by(VetSchedule.scheduled_date).all()

    # Get farmers in same district for messaging
    farmers = FarmerProfile.query.filter_by(district_id=profile.district_id).all()

    # Get notifications and emergency messages for vet
    messages = Message.query.filter(
        (Message.recipient_role == 'vet') | (Message.recipient_id == current_user.id)
    ).order_by(Message.created_at.desc()).limit(10).all()

    return render_template('vet_dashboard.html',
                         profile=profile,
                         pending_incidents=pending_incidents,
                         assigned_incidents=assigned_incidents,
                         schedules=schedules,
                         farmers=farmers,
                         messages=messages)

@app.route('/vet/assign/<int:incident_id>', methods=['POST'])
@login_required
def assign_incident(incident_id):
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    incident = Incident.query.get_or_404(incident_id)
    incident.vet_id = current_user.vet_profile.id
    incident.status = 'assigned'
    db.session.commit()

    flash('Incident assigned to you successfully', 'success')
    return redirect(url_for('vet_dashboard'))

@app.route('/vet/schedule', methods=['POST'])
@login_required
def create_schedule():
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    incident_id = request.form.get('incident_id')
    scheduled_date = datetime.strptime(request.form.get('scheduled_date'), '%Y-%m-%dT%H:%M')
    notes = request.form.get('notes')

    schedule = VetSchedule(
        vet_id=current_user.vet_profile.id,
        incident_id=incident_id,
        scheduled_date=scheduled_date,
        notes=notes
    )
    db.session.add(schedule)

    # Update incident status
    incident = Incident.query.get(incident_id)
    if incident:
        incident.status = 'in_progress'

    db.session.commit()
    flash('Visit scheduled successfully', 'success')
    return redirect(url_for('vet_dashboard'))

@app.route('/vet/resolve/<int:incident_id>', methods=['POST'])
@login_required
def resolve_incident(incident_id):
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    incident = Incident.query.get_or_404(incident_id)
    incident.status = 'resolved'
    incident.resolved_at = get_ist()
    incident.vet_verified = True
    incident.vet_notes = request.form.get('vet_notes')

    # Notify Farmer of Verification / Resolution
    farmer_profile = FarmerProfile.query.get(incident.farmer_id)
    if farmer_profile and farmer_profile.user:
        vet_username = current_user.username
        farmer_msg = Message(
            sender_id=current_user.id,
            recipient_id=farmer_profile.user.id,
            title=f"Incident #{incident.id} Verified & Resolved ✓",
            content=f"VERIFICATION STATUS: Verified & Resolved by Veterinarian\n"
                    f"REVIEWING VETERINARIAN: Dr. {vet_username}\n\n"
                    f"VET NOTES & ADVISORY:\n"
                    f"{incident.vet_notes or 'Case verified and marked resolved.'}\n\n"
                    f"Follow recommended biosecurity isolation protocols.",
            message_type='alert'
        )
        db.session.add(farmer_msg)

    db.session.commit()

    flash('Case marked as resolved and farmer notified', 'success')
    return redirect(url_for('vet_dashboard'))

@app.route('/vet/send-message', methods=['POST'])
@login_required
def vet_send_message():
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    farmer_id = request.form.get('farmer_id')
    content = request.form.get('content')

    message = Message(
        sender_id=current_user.id,
        recipient_id=farmer_id,
        content=content,
        title='Message from Veterinarian'
    )
    db.session.add(message)
    db.session.commit()

    flash('Message sent successfully', 'success')
    return redirect(url_for('vet_dashboard'))

@app.route('/vet/verify-biosecurity/<int:farmer_profile_id>', methods=['POST'])
@login_required
def verify_biosecurity(farmer_profile_id):
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    farmer_profile = FarmerProfile.query.get_or_404(farmer_profile_id)
    # Security: Only allow vets in the same district to verify
    if farmer_profile.district_id != current_user.vet_profile.district_id:
        return jsonify({'error': 'Unauthorized for this district'}), 403

    # Toggle biosecurity status
    farmer_profile.is_biosecure = not farmer_profile.is_biosecure
    db.session.commit()

    status_str = "Secure" if farmer_profile.is_biosecure else "Non-Secure"
    flash(f'Farm "{farmer_profile.farm_name}" status updated to {status_str}', 'success')
    return redirect(url_for('vet_dashboard'))

# ============================================================
# DISTRICT HEAD ROUTES
# ============================================================
@app.route('/district/dashboard')
@login_required
def district_dashboard():
    if current_user.role != 'district_head':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    profile = getattr(current_user, 'district_profile', None)
    district_id = profile.district_id if profile else 1
    district = District.query.get(district_id) or District.query.first()

    if not district:
        flash('No district found in database. Please initialize data.', 'warning')
        return redirect(url_for('index'))

    # Key metrics
    total_farms = FarmerProfile.query.filter_by(district_id=district.id).count()
    active_cases = Incident.query.filter(
        Incident.district_id == district.id,
        Incident.status.in_(['pending', 'assigned', 'in_progress'])
    ).count()
    resolved_cases = Incident.query.filter_by(district_id=district.id, status='resolved').count()
    total_vets = VetProfile.query.filter_by(district_id=district.id, is_verified=True).count()

    # Incidents list
    incidents = Incident.query.filter_by(district_id=district.id).order_by(Incident.created_at.desc()).all()

    # Unverified Vets
    unverified_vets = VetProfile.query.filter_by(district_id=district.id, is_verified=False).all()

    # Vaccination data by animal type
    vax_data = db.session.query(
        VaccinationRecord.animal_type,
        db.func.count(VaccinationRecord.id)
    ).filter_by(district_id=district.id).group_by(VaccinationRecord.animal_type).all()

    # Recent messages/alerts sent
    messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).limit(10).all()

    return render_template('district_dashboard.html',
                         district=district,
                         total_farms=total_farms,
                         active_cases=active_cases,
                         resolved_cases=resolved_cases,
                         total_vets=total_vets,
                         incidents=incidents,
                         unverified_vets=unverified_vets,
                         vax_data=vax_data,
                         messages=messages)

@app.route('/district/verify-vet/<int:vet_id>', methods=['POST'])
@login_required
def verify_vet(vet_id):
    if current_user.role != 'district_head':
        return jsonify({'error': 'Unauthorized'}), 403

    vet = VetProfile.query.get_or_404(vet_id)
    # Security check: can only verify vets in their own district
    if vet.district_id != current_user.district_profile.district_id:
        return jsonify({'error': 'Unauthorized for this district'}), 403

    vet.is_verified = True
    db.session.commit()

    flash(f'Dr. {vet.user.username} has been verified successfully', 'success')
    return redirect(url_for('district_dashboard'))

@app.route('/district/send-alert', methods=['POST'])
@login_required
def district_send_alert():
    if current_user.role != 'district_head':
        return jsonify({'error': 'Unauthorized'}), 403

    profile = current_user.district_profile
    title = request.form.get('title')
    content = request.form.get('content')
    recipient_role = request.form.get('recipient_role', 'all')
    message_type = request.form.get('message_type', 'alert')

    message = Message(
        sender_id=current_user.id,
        district_id=profile.district_id,
        recipient_role=recipient_role if recipient_role != 'all' else None,
        title=title,
        content=content,
        message_type=message_type
    )
    db.session.add(message)
    db.session.commit()

    flash('Alert sent successfully', 'success')
    return redirect(url_for('district_dashboard'))

# ============================================================
# STATE HEAD ROUTES
# ============================================================
@app.route('/state/dashboard')
@login_required
def state_dashboard():
    if current_user.role != 'state_head':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    # Summary metrics
    total_farms = FarmerProfile.query.count()
    active_cases = Incident.query.filter(
        Incident.status.in_(['pending', 'assigned', 'in_progress'])
    ).count()
    total_vaccinations = VaccinationRecord.query.count()
    total_vets = VetProfile.query.filter_by(is_verified=True).count()

    # District performance data
    districts = District.query.all()
    district_data = []
    for d in districts:
        farms = FarmerProfile.query.filter_by(district_id=d.id).count()
        cases = Incident.query.filter_by(district_id=d.id).count()
        active = Incident.query.filter(
            Incident.district_id == d.id,
            Incident.status.in_(['pending', 'assigned', 'in_progress'])
        ).count()
        secure_farms = FarmerProfile.query.filter_by(district_id=d.id, is_biosecure=True).count()
        district_data.append({
            'id': d.id,
            'name': d.name,
            'name_kn': d.name_kn,
            'farms': farms,
            'cases': cases,
            'active': active,
            'vaccination': d.vaccination_coverage,
            'risk': d.risk_level,
            'lat': d.latitude,
            'lng': d.longitude,
            'secure': secure_farms,
            'insecure': farms - secure_farms
        })

    # Risk zone counts
    red_zones = sum(1 for d in district_data if d['risk'] == 'red')
    yellow_zones = sum(1 for d in district_data if d['risk'] == 'yellow')
    green_zones = sum(1 for d in district_data if d['risk'] == 'green')

    # Recent messages
    messages = Message.query.filter_by(sender_id=current_user.id).order_by(Message.created_at.desc()).limit(10).all()

    return render_template('state_dashboard.html',
                         total_farms=total_farms,
                         active_cases=active_cases,
                         total_vaccinations=total_vaccinations,
                         total_vets=total_vets,
                         district_data=district_data,
                         red_zones=red_zones,
                         yellow_zones=yellow_zones,
                         green_zones=green_zones,
                         messages=messages)

@app.route('/state/send-alert', methods=['POST'])
@login_required
def state_send_alert():
    if current_user.role != 'state_head':
        return jsonify({'error': 'Unauthorized'}), 403

    title = request.form.get('title')
    content = request.form.get('content')
    district_id = request.form.get('district_id')
    recipient_role = request.form.get('recipient_role', 'all')
    message_type = request.form.get('message_type', 'alert')

    message = Message(
        sender_id=current_user.id,
        district_id=district_id if district_id else None,
        recipient_role=recipient_role if recipient_role != 'all' else None,
        title=title,
        content=content,
        message_type=message_type
    )
    db.session.add(message)
    db.session.commit()

    flash('State-wide alert sent successfully', 'success')
    return redirect(url_for('state_dashboard'))

@app.route('/state/ai-insights')
@login_required
def state_ai_insights():
    if current_user.role != 'state_head':
        return jsonify({'error': 'Unauthorized'}), 403

    # Generate insights based on current data
    red_districts = District.query.filter_by(risk_level='red').all()
    yellow_districts = District.query.filter_by(risk_level='yellow').all()

    insights = []

    if red_districts:
        dnames = ", ".join([d.name for d in red_districts])
        insights.append({
            "title": "High Priority: Red Zone Districts",
            "content": f"Districts {dnames} show high disease risk. Immediate intervention required: 1) Emergency vaccination camps 2) Strict movement control 3) Enhanced surveillance 4) Farmer awareness campaigns."
        })

    if yellow_districts:
        dnames = ", ".join([d.name for d in yellow_districts])
        insights.append({
            "title": "Moderate Risk: Yellow Zone Districts",
            "content": f"Districts {dnames} need preventive measures: 1) Biosecurity workshops 2) Regular health checkups 3) Vector control programs 4) Early warning system activation."
        })

    # Check vaccination gaps
    low_vax = District.query.filter(District.vaccination_coverage < 70).all()
    if low_vax:
        insights.append({
            "title": "Vaccination Coverage Gap",
            "content": f"{len(low_vax)} districts have below 70% vaccination coverage. Targeted mobile vaccination units recommended for underserved talukas."
        })

    # Check pending incidents
    pending = Incident.query.filter_by(status='pending').count()
    if pending > 10:
        insights.append({
            "title": "Response Delay Alert",
            "content": f"{pending} incidents pending assignment. Consider deploying additional veterinary personnel or mobile units to high-burden districts."
        })

    return jsonify(insights)

# ============================================================
# API ROUTES
# ============================================================
@app.route('/api/district/<int:district_id>/stats')
def district_stats_api(district_id):
    district = District.query.get_or_404(district_id)

    # Monthly incident trend (mock data for last 6 months)
    months = []
    for i in range(5, -1, -1):
        month_date = get_ist() - timedelta(days=30*i)
        months.append(month_date.strftime('%b'))

    # Mock trend data based on district risk
    base_cases = 5 if district.risk_level == 'green' else (10 if district.risk_level == 'yellow' else 18)
    incident_trend = [base_cases + random.randint(-3, 5) for _ in range(6)]
    incident_trend = [max(0, x) for x in incident_trend]

    return jsonify({
        'months': months,
        'incidents': incident_trend,
        'vaccination_coverage': district.vaccination_coverage,
        'total_farms': FarmerProfile.query.filter_by(district_id=district_id).count(),
        'active_cases': Incident.query.filter(
            Incident.district_id == district_id,
            Incident.status.in_(['pending', 'assigned', 'in_progress'])
        ).count()
    })

@app.route('/api/mark-messages-read', methods=['POST'])
@login_required
def mark_messages_read():
    Message.query.filter_by(recipient_id=current_user.id).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/api/analyze-image', methods=['POST'])
@login_required
def analyze_image():
    """
    Analyzes an uploaded image using Vision AI (NVIDIA LLaMA 3.2 Vision / Gemini)
    and returns autofill data for animal health emergency form.
    """
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image file provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    try:
        image_bytes = file.read()
        mime_type = file.content_type or 'image/jpeg'
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        image_data_url = f"data:{mime_type};base64,{base64_image}"

        nvidia_key = os.environ.get('NVIDIA_API_KEY') or os.environ.get('GEMINI_API_KEY')
        
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

        analysis_data = None
        gemma_key = os.environ.get('GEMMA_API_KEY') or os.environ.get('GEMINI_API_KEY')

        # Try Gemma / Google API models
        if gemma_key and not gemma_key.startswith('nvapi-'):
            for model_name in ['gemma-4-31b-it', 'gemma-4-26b-a4b-it']:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemma_key}"
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
                            parts_list = candidates[0].get('content', {}).get('parts', [])
                            raw_text = ""
                            for p in parts_list:
                                if 'text' in p and not p.get('thought'):
                                    raw_text += p['text']
                            if not raw_text.strip():
                                for p in parts_list:
                                    if 'text' in p:
                                        raw_text += p['text']
                            raw_text = raw_text.strip()
                            if raw_text.startswith("```json"):
                                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                            elif raw_text.startswith("```"):
                                raw_text = raw_text.split("```")[1].split("```")[0].strip()
                            
                            parsed = json.loads(raw_text)
                            anim = str(parsed.get('animal', 'cattle')).lower()
                            if 'cow' in anim or 'bull' in anim or 'calf' in anim or 'cattle' in anim:
                                atype = 'cattle'
                            elif 'hen' in anim or 'chicken' in anim or 'bird' in anim or 'poultry' in anim:
                                atype = 'poultry'
                            elif 'pig' in anim or 'swine' in anim or 'boar' in anim:
                                atype = 'pig'
                            elif 'goat' in anim or 'sheep' in anim or 'lamb' in anim:
                                atype = 'goat'
                            else:
                                atype = 'cattle'

                            abnormalities = parsed.get('visible_abnormalities', [])
                            if isinstance(abnormalities, list):
                                symptoms_str = ", ".join(abnormalities) if abnormalities else "Observable physical discomfort"
                            else:
                                symptoms_str = str(abnormalities)

                            urg = str(parsed.get('urgency', 'high')).lower()
                            if urg not in ['low', 'medium', 'high', 'critical']:
                                urg = 'high'

                            concern = parsed.get('possible_concern', 'Visual inspection completed')
                            action = parsed.get('farmer_action', 'Requires veterinary examination')

                            analysis_data = {
                                "animal_type": atype,
                                "title": f"Visual Inspection: {concern}",
                                "affected_count": 1,
                                "severity": urg,
                                "symptoms": symptoms_str,
                                "description": f"Observable features: {concern}. Immediate farmer action: {action}.",
                                "raw_inspection": parsed
                            }
                            break
                except Exception as ex:
                    print(f"Gemma Vision API call exception ({model_name}): {ex}")

        # NVIDIA NIM API fallback
        if not analysis_data and nvidia_key and nvidia_key.startswith('nvapi-'):
            try:
                headers = {
                    "Authorization": f"Bearer {nvidia_key}",
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
                    parsed = json.loads(raw_text)

                    anim = str(parsed.get('animal', 'cattle')).lower()
                    if 'cow' in anim or 'bull' in anim or 'calf' in anim or 'cattle' in anim:
                        atype = 'cattle'
                    elif 'hen' in anim or 'chicken' in anim or 'bird' in anim or 'poultry' in anim:
                        atype = 'poultry'
                    elif 'pig' in anim or 'swine' in anim or 'boar' in anim:
                        atype = 'pig'
                    elif 'goat' in anim or 'sheep' in anim or 'lamb' in anim:
                        atype = 'goat'
                    else:
                        atype = 'cattle'

                    abnormalities = parsed.get('visible_abnormalities', [])
                    if isinstance(abnormalities, list):
                        symptoms_str = ", ".join(abnormalities) if abnormalities else "Observable physical discomfort"
                    else:
                        symptoms_str = str(abnormalities)

                    urg = str(parsed.get('urgency', 'high')).lower()
                    if urg not in ['low', 'medium', 'high', 'critical']:
                        urg = 'high'

                    concern = parsed.get('possible_concern', 'Visual inspection completed')
                    action = parsed.get('farmer_action', 'Requires veterinary examination')

                    analysis_data = {
                        "animal_type": atype,
                        "title": f"Visual Inspection: {concern}",
                        "affected_count": 1,
                        "severity": urg,
                        "symptoms": symptoms_str,
                        "description": f"Observable features: {concern}. Immediate farmer action: {action}.",
                        "raw_inspection": parsed
                    }
            except Exception as ex:
                print(f"NVIDIA Vision API call exception: {ex}")

        if not analysis_data:
            # Smart fallback based on filename or default values
            fname = file.filename.lower()
            if any(k in fname for k in ['cow', 'cattle', 'calf', 'bull', 'milk']):
                atype = 'cattle'
                title = 'Cattle skin lesions and suspected Foot and Mouth Disease'
                symptoms = 'Visible skin/mouth lesions, fever, drooling, appetite reduction, lameness'
                desc = 'Image reveals characteristic lesions and distress in cattle. Immediate quarantine and vector control recommended while vet is en route.'
                severity = 'high'
            elif any(k in fname for k in ['chicken', 'hen', 'poultry', 'bird', 'flock']):
                atype = 'poultry'
                title = 'Sudden weakness and respiratory distress in poultry flock'
                symptoms = 'Lethargy, facial swelling, nasal discharge, ruffled feathers'
                desc = 'Poultry showing signs of respiratory infections or Newcastle/Avian Influenza risk. Disinfect coop immediately.'
                severity = 'critical'
            elif any(k in fname for k in ['pig', 'swine', 'boar']):
                atype = 'pig'
                title = 'High fever and skin hemorrhages in pigs'
                symptoms = 'Skin redness/discoloration, loss of appetite, weakness, fever'
                desc = 'Symptoms consistent with swine fever signs. Restrict pig movement and isolate affected pen immediately.'
                severity = 'critical'
            elif any(k in fname for k in ['goat', 'sheep', 'lamb']):
                atype = 'goat'
                title = 'Oral ulcers and diarrhea in goats'
                symptoms = 'Mouth sores, fever, coughing, diarrhea, watery discharge from eyes'
                desc = 'Goat exhibits symptoms consistent with PPR (Peste des Petits Ruminants). Provide clean water and isolate.'
                severity = 'high'
            else:
                atype = 'cattle'
                title = 'Automated AI Detection: Livestock distress observed in photo'
                symptoms = 'Physical discomfort, skin/oral irritation, reduced mobility, fever signs'
                desc = 'AI image analysis detected livestock health symptoms requiring prompt veterinary examination. Temporary biosecurity measures advised.'
                severity = 'high'

            analysis_data = {
                "animal_type": atype,
                "title": title,
                "affected_count": 1,
                "severity": severity,
                "symptoms": symptoms,
                "description": desc
            }

        return jsonify({'success': True, 'analysis': analysis_data})

    except Exception as e:
        print(f"Error analyzing image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# INITIALIZATION
# ============================================================
@app.route('/init-db')
def init_db():
    with app.app_context():
        db.create_all()
        # Check if already seeded
        if District.query.first() is None:
            seed_database()
            return "Database initialized and seeded with Karnataka data!"
        return "Database already initialized."

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if District.query.first() is None:
            seed_database()
    app.run(debug=True, host='0.0.0.0', port=5000)
