import os
from dotenv import load_dotenv
from flask import Flask, send_from_directory
from flask_login import LoginManager
from models import db, User, get_ist
from data import seed_database, KARNATAKA_DISTRICTS

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
login_manager.login_view = 'auth.login'

# Ensure Notification table is created by importing the model
from backend.models.notification import Notification

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ============================================================
# INITIALIZE AGENTIC RAG SERVICE
# ============================================================
from backend.services.rag_service import RAGService

rag_service = RAGService("backend/knowledge_base")
rag_service.initialize_knowledge_base()

# Store RAG service in app config so blueprints can access it
app.config['RAG_SERVICE'] = rag_service

# ============================================================
# REGISTER BLUEPRINTS
# ============================================================
from backend.routes.api_routes import api_bp, init_api_rag_service
init_api_rag_service(rag_service)
app.register_blueprint(api_bp, url_prefix='/api')

from backend.routes.notification_routes import notification_bp
app.register_blueprint(notification_bp)

from backend.routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

from backend.routes.farmer_routes import farmer_bp
app.register_blueprint(farmer_bp)

from backend.routes.vet_routes import vet_bp
app.register_blueprint(vet_bp)

from backend.routes.district_routes import district_bp
app.register_blueprint(district_bp)

from backend.routes.state_routes import state_bp
app.register_blueprint(state_bp)

# ============================================================
# INITIALIZE SOCKET.IO
# ============================================================
from backend.socketio_events import init_socketio, socketio
init_socketio(app)

# ============================================================
# ROOT-LEVEL API ALIASES (backward compatibility)
# ============================================================
from backend.routes.api_routes import (
    analyze_image_endpoint, rag_query_endpoint,
    vet_verify_endpoint, vet_incidents_endpoint
)
from flask_login import login_required

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

# ============================================================
# ROOT-LEVEL STATIC FILES (sw.js, favicon)
# ============================================================
@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')

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
# STARTUP
# ============================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        from models import District
        if District.query.first() is None:
            seed_database()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
