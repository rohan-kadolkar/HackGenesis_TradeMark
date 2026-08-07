import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, FarmerProfile, VetProfile, Incident, VaccinationRecord, Message, get_ist
from data import BIOSAFETY_TIPS, DISEASES
from backend.services.ai_service import AIService

farmer_bp = Blueprint('farmer', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@farmer_bp.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.role != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))

    profile = current_user.farmer_profile
    if not profile:
        flash('Profile not found', 'danger')
        return redirect(url_for('auth.index'))

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

@farmer_bp.route('/farmer/report-emergency', methods=['GET', 'POST'])
@login_required
def report_emergency():
    if current_user.role != 'farmer':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))

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
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
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
            from backend.services.rag_service import RAGService
            rag_service = current_app.config.get('RAG_SERVICE')
            if rag_service:
                rag_output = rag_service.run_pipeline(mock_gemma, raw_form)
                incident.set_rag_data(rag_output)
                
                # Format legacy ai_solution string for backward compatibility
                farmer_recs = "\n".join([f"• {r}" for r in rag_output.get("farmer_response", {}).get("recommended", [])])
                vet_adv = rag_output.get("vet_summary", {}).get("vet_advisory", "Clinical examination advised.")
                incident.ai_solution = f"[Source: Agentic RAG Pipeline]\n\nFARMER ADVISORY:\n{farmer_recs}\n\nVETERINARY ADVISORY:\n{vet_adv}"
            else:
                raise Exception("RAG service not available")
        except Exception as ex:
            print(f"Error running Agentic RAG pipeline in report_emergency: {ex}")
            ai_service = AIService()
            incident.ai_solution = ai_service.generate_ai_solution(description, symptoms, animal_type, images, current_app.config['UPLOAD_FOLDER'])

        # Notify Veterinary Doctor(s) of the newly submitted emergency report
        vets = []
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
        if not vets:
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
        return redirect(url_for('farmer.view_incident', incident_id=incident.id))

    return render_template('report_emergency.html', diseases=DISEASES)

@farmer_bp.route('/incident/<int:incident_id>')
@login_required
def view_incident(incident_id):
    incident = Incident.query.get_or_404(incident_id)

    # Authorization check
    if current_user.role == 'farmer':
        if not current_user.farmer_profile or incident.farmer_id != current_user.farmer_profile.id:
            flash('Access denied', 'danger')
            return redirect(url_for('farmer.farmer_dashboard'))

    elif current_user.role == 'vet':
        if not current_user.vet_profile:
            flash('Access denied', 'danger')
            return redirect(url_for('auth.index'))
        
        # Allow vet to view if in their district OR assigned to them
        if incident.district_id and incident.district_id != current_user.vet_profile.district_id and incident.vet_id != current_user.vet_profile.id:
            flash('Access denied. Incident is outside your assigned district.', 'danger')
            return redirect(url_for('vet.vet_dashboard'))
        
        # Auto-assign unassigned pending incident to this reviewing vet
        if not incident.vet_id:
            incident.vet_id = current_user.vet_profile.id
            if incident.status == 'pending':
                incident.status = 'assigned'
            db.session.commit()

    elif current_user.role == 'district_head':
        if not current_user.district_profile or (incident.district_id and incident.district_id != current_user.district_profile.district_id):
            flash('Access denied', 'danger')
            return redirect(url_for('district.district_dashboard'))

    return render_template('view_incident.html', incident=incident)

@farmer_bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
