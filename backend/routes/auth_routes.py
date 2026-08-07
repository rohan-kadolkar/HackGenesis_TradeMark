from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, District, FarmerProfile, VetProfile, DistrictHeadProfile, StateHeadProfile, Incident

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    stats = {
        'total_farms': FarmerProfile.query.count(),
        'active_cases': Incident.query.filter(Incident.status.in_(['pending', 'assigned', 'in_progress'])).count(),
        'resolved_cases': Incident.query.filter_by(status='resolved').count(),
        'total_vets': VetProfile.query.count(),
        'districts_covered': District.query.count()
    }
    return render_template('index.html', stats=stats)

@auth_bp.route('/about')
def about():
    return render_template('about.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
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
                return redirect(url_for('farmer.farmer_dashboard'))
            elif user.role == 'vet':
                return redirect(url_for('vet.vet_dashboard'))
            elif user.role == 'district_head':
                return redirect(url_for('district.district_dashboard'))
            elif user.role == 'state_head':
                return redirect(url_for('state.state_dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
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
            return redirect(url_for('auth.signup'))

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
        return redirect(url_for('auth.login'))

    districts = District.query.all()
    return render_template('signup.html', districts=districts)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('auth.index'))
