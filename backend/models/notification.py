from models import db, get_ist
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recipient_role = db.Column(db.String(20), nullable=True)  # farmer, vet, district_head, state_head, all
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('incidents.id'), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_ist)

    # Relationships
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='notifications')
    report = db.relationship('Incident', foreign_keys=[report_id], backref='notifications')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            'id': self.id,
            'recipient_id': self.recipient_id,
            'recipient_role': self.recipient_role,
            'title': self.title,
            'message': self.message,
            'report_id': self.report_id,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }
