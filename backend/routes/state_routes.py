from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, District, FarmerProfile, VetProfile, Incident, VaccinationRecord, Message

state_bp = Blueprint('state', __name__)

@state_bp.route('/state/dashboard')
@login_required
def state_dashboard():
    if current_user.role != 'state_head':
        flash('Access denied', 'danger')
        return redirect(url_for('auth.index'))

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

@state_bp.route('/state/send-alert', methods=['POST'])
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
    return redirect(url_for('state.state_dashboard'))

@state_bp.route('/state/ai-insights')
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
