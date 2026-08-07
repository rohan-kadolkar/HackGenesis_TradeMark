from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, FarmerProfile, VetProfile, Incident, VetSchedule, Message, get_ist

vet_bp = Blueprint('vet', __name__)

@vet_bp.route('/vet/dashboard')
@login_required
def vet_dashboard():
    if current_user.role != 'vet':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))

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

@vet_bp.route('/vet/assign/<int:incident_id>', methods=['POST'])
@login_required
def assign_incident(incident_id):
    if current_user.role != 'vet':
        return jsonify({'error': 'Unauthorized'}), 403

    incident = Incident.query.get_or_404(incident_id)
    incident.vet_id = current_user.vet_profile.id
    incident.status = 'assigned'
    db.session.commit()

    flash('Incident assigned to you successfully', 'success')
    return redirect(url_for('vet.vet_dashboard'))

@vet_bp.route('/vet/schedule', methods=['POST'])
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
    return redirect(url_for('vet.vet_dashboard'))

@vet_bp.route('/vet/resolve/<int:incident_id>', methods=['POST'])
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
    return redirect(url_for('vet.vet_dashboard'))

@vet_bp.route('/vet/send-message', methods=['POST'])
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
    return redirect(url_for('vet.vet_dashboard'))

@vet_bp.route('/vet/verify-biosecurity/<int:farmer_profile_id>', methods=['POST'])
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
    return redirect(url_for('vet.vet_dashboard'))
