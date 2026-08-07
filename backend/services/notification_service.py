from models import db, User, Incident, District, FarmerProfile, VetProfile, DistrictHeadProfile, StateHeadProfile
from backend.models.notification import Notification
from backend.socketio_events import socketio
from datetime import datetime, timedelta

class NotificationService:
    @staticmethod
    def create_and_send_notification(recipient_id, recipient_role, title, message, report_id=None):
        """
        Saves notification to database and emits real-time WebSocket event.
        """
        notification = Notification(
            recipient_id=recipient_id,
            recipient_role=recipient_role,
            title=title,
            message=message,
            report_id=report_id,
            is_read=False
        )
        db.session.add(notification)
        db.session.commit()

        data = notification.to_dict()

        # Real-time Socket.IO emission
        if recipient_id:
            socketio.emit('notification', data, room=f"user_{recipient_id}")
        if recipient_role:
            socketio.emit('notification', data, room=f"role_{recipient_role}")
            
        # Broadcast event
        socketio.emit('notification_broadcast', data)
        return notification

    @staticmethod
    def notify_emergency_report_created(farmer_user, incident):
        """
        Req 3: When farmer submits an emergency report, save report notification
        for assigned/district vet and send real-time Socket.IO event.
        """
        title = f"🚨 EMERGENCY REPORT: {incident.animal_type.title()} in {incident.village or 'District'} (#{incident.id})"
        message = (
            f"Farmer {farmer_user.username} submitted an emergency report (#{incident.id}).\n"
            f"Animal: {incident.animal_type.title()} | Symptoms: {incident.symptoms} | Severity: {incident.severity.upper()}"
        )

        vets = VetProfile.query.filter_by(district_id=incident.district_id).all() if incident.district_id else []
        notified = False

        for vet in vets:
            if vet.user:
                NotificationService.create_and_send_notification(
                    recipient_id=vet.user.id,
                    recipient_role='vet',
                    title=title,
                    message=message,
                    report_id=incident.id
                )
                notified = True

        if not notified:
            NotificationService.create_and_send_notification(
                recipient_id=None,
                recipient_role='vet',
                title=title,
                message=message,
                report_id=incident.id
            )

    @staticmethod
    def notify_vet_verification_completed(incident, is_verified, vet_user, severity, edited_fields=None):
        """
        Req 4 & 5: When vet verifies report, notify farmer.
        If severity is Medium or High, notify District Head.
        If multiple Medium/High cases occur in district, notify State Head.
        """
        edited_fields = edited_fields or {}
        diag = edited_fields.get("diagnosis") or "Clinical Veterinary Inspection Completed"

        # 1. Notify Farmer (Req 4)
        farmer_profile = FarmerProfile.query.get(incident.farmer_id)
        if farmer_profile and farmer_profile.user:
            farmer_title = f"Incident #{incident.id} Update - {'Verified ✓' if is_verified else 'Rejected ✗'}"
            farmer_msg = (
                f"Veterinarian Dr. {vet_user.username} has {'verified' if is_verified else 'rejected'} your report (#{incident.id}).\n"
                f"Diagnosis: {diag}\n"
                f"Severity: {severity.upper()}"
            )
            NotificationService.create_and_send_notification(
                recipient_id=farmer_profile.user.id,
                recipient_role='farmer',
                title=farmer_title,
                message=farmer_msg,
                report_id=incident.id
            )

        # 2. Check Severity for District Head & State Head Escalation (Req 5)
        sev = str(severity).lower()
        if is_verified and sev in ['medium', 'high', 'critical'] and incident.district_id:
            district = District.query.get(incident.district_id)
            if district:
                if sev in ['high', 'critical']:
                    district.risk_level = 'red'
                elif sev == 'medium' and district.risk_level != 'red':
                    district.risk_level = 'yellow'
                db.session.commit()

            # Notify District Head
            district_heads = DistrictHeadProfile.query.filter_by(district_id=incident.district_id).all()
            dist_title = f"🚨 DISTRICT ESCALATION: Verified {sev.upper()} Severity Case #{incident.id}"
            dist_msg = (
                f"Dr. {vet_user.username} verified a {sev.upper()} risk {incident.animal_type} incident (#{incident.id}) "
                f"in village {incident.village}, district #{incident.district_id}."
            )

            for dh in district_heads:
                if dh.user:
                    NotificationService.create_and_send_notification(
                        recipient_id=dh.user.id,
                        recipient_role='district_head',
                        title=dist_title,
                        message=dist_msg,
                        report_id=incident.id
                    )

            # If no specific district head user found, broadcast to role
            if not district_heads:
                NotificationService.create_and_send_notification(
                    recipient_id=None,
                    recipient_role='district_head',
                    title=dist_title,
                    message=dist_msg,
                    report_id=incident.id
                )

            # Check for multiple Medium/High/Critical cases in the same district
            multi_count = Incident.query.filter(
                Incident.district_id == incident.district_id,
                Incident.vet_verified == True,
                Incident.severity.in_(['medium', 'high', 'critical'])
            ).count()

            if multi_count >= 2:
                state_heads = User.query.filter_by(role='state_head').all()
                state_title = f"⚠️ STATE OUTBREAK WARNING: {multi_count} Verified Cases in District #{incident.district_id}"
                state_msg = (
                    f"District #{incident.district_id} has recorded {multi_count} verified Medium/High risk livestock outbreaks. "
                    f"Latest Case #{incident.id} ({incident.animal_type.title()} - {sev.upper()}). Immediate state-level monitoring required."
                )

                for sh in state_heads:
                    NotificationService.create_and_send_notification(
                        recipient_id=sh.id,
                        recipient_role='state_head',
                        title=state_title,
                        message=state_msg,
                        report_id=incident.id
                    )

                if not state_heads:
                    NotificationService.create_and_send_notification(
                        recipient_id=None,
                        recipient_role='state_head',
                        title=state_title,
                        message=state_msg,
                        report_id=incident.id
                    )

    @staticmethod
    def get_notifications(user_id, user_role=None, unread_only=False):
        """
        Req 7 & 8: Retrieve user notification history.
        """
        query = Notification.query.filter(
            (Notification.recipient_id == user_id) | (Notification.recipient_role == user_role)
        )
        if unread_only:
            query = query.filter(Notification.is_read == False)

        return query.order_by(Notification.created_at.desc()).all()

    @staticmethod
    def mark_read(notification_id, user_id=None):
        notif = Notification.query.get(notification_id)
        if notif:
            # Verify the notification belongs to the requesting user
            if user_id and notif.recipient_id and notif.recipient_id != user_id:
                return None
            notif.is_read = True
            db.session.commit()
            return notif
        return None

    @staticmethod
    def mark_all_read(user_id, user_role=None):
        notifications = Notification.query.filter(
            (Notification.recipient_id == user_id) | (Notification.recipient_role == user_role),
            Notification.is_read == False
        ).all()

        for n in notifications:
            n.is_read = True
        db.session.commit()
        return len(notifications)
