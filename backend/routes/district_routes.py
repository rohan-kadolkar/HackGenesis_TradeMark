from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, District, FarmerProfile, VetProfile, Incident, VaccinationRecord, Message

district_bp = Blueprint('district', __name__)

@district_bp.route('/district/dashboard')
@login_required
def district_dashboard():
    if current_user.role != 'district_head':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))

    profile = getattr(current_user, 'district_profile', None)
    district_id = profile.district_id if profile else 1
    district = District.query.get(district_id) or District.query.first()

    if not district:
        flash('No district found in database. Please initialize data.', 'warning')
        return redirect(url_for('auth.index'))

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

@district_bp.route('/district/verify-vet/<int:vet_id>', methods=['POST'])
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
    return redirect(url_for('district.district_dashboard'))

@district_bp.route('/district/send-alert', methods=['POST'])
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
    return redirect(url_for('district.district_dashboard'))
