from models import db, Incident, District, FarmerProfile, VetProfile, Message, get_ist
from datetime import datetime

class IncidentService:
    """
    Manages database CRUD operations for incidents, RAG persistence,
    vet verification actions, district escalation, and farmer notifications.
    """
    @staticmethod
    def create_incident(farmer_id, district_id, title, description, symptoms, animal_type, affected_count, severity, images_list, village, taluka, rag_output=None):
        incident = Incident(
            farmer_id=farmer_id,
            district_id=district_id,
            title=title,
            description=description,
            symptoms=symptoms,
            animal_type=animal_type,
            affected_count=affected_count,
            severity=severity,
            status='pending',
            village=village,
            taluka=taluka
        )
        if images_list:
            incident.set_images_list(images_list)

        if rag_output:
            incident.set_rag_data(rag_output)
            farmer_rec = "\n".join([f"• {r}" for r in rag_output.get("farmer_response", {}).get("recommended", [])])
            vet_adv = rag_output.get("vet_summary", {}).get("vet_advisory", "Clinical examination advised.")
            incident.ai_solution = f"FARMER ADVISORY:\n{farmer_rec}\n\nVETERINARY SUMMARY:\n{vet_adv}"

        db.session.add(incident)
        db.session.commit()

        # Check automated outbreak trigger for District
        if severity in ['medium', 'high', 'critical'] and district_id:
            district = District.query.get(district_id)
            if district:
                if severity in ['high', 'critical']:
                    district.risk_level = 'red'
                elif severity == 'medium' and district.risk_level != 'red':
                    district.risk_level = 'yellow'
                db.session.commit()

        # Notify Veterinary Doctors of new Emergency Incident
        vets = VetProfile.query.filter_by(district_id=district_id).all() if district_id else []
        for vet in vets:
            if vet.user:
                vet_msg = Message(
                    sender_id=farmer_id,
                    recipient_id=vet.user.id,
                    recipient_role='vet',
                    district_id=district_id,
                    title=f"🚨 EMERGENCY REPORT: {animal_type.title()} Incident #{incident.id}",
                    content=f"Emergency report created by Farmer.\n"
                            f"• Animal Type: {animal_type.title()}\n"
                            f"• Symptoms: {symptoms}\n"
                            f"• Severity: {severity.upper()}\n"
                            f"• Location: {village or 'District'}, {taluka or ''}\n\n"
                            f"Please review and verify this incident report.",
                    message_type='emergency' if severity in ['high', 'critical'] else 'alert'
                )
                db.session.add(vet_msg)
        if not vets:
            vet_msg = Message(
                sender_id=farmer_id,
                recipient_role='vet',
                district_id=district_id,
                title=f"🚨 EMERGENCY REPORT: {animal_type.title()} Incident #{incident.id}",
                content=f"Emergency report created by Farmer.\n"
                        f"• Animal Type: {animal_type.title()}\n"
                        f"• Symptoms: {symptoms}\n"
                        f"• Severity: {severity.upper()}\n\n"
                        f"Please review and verify this incident report.",
                message_type='emergency' if severity in ['high', 'critical'] else 'alert'
            )
            db.session.add(vet_msg)

        db.session.commit()
        return incident

    @staticmethod
    def vet_verify_incident(incident_id, vet_id, action, ai_assessment_rating="correct", vet_notes=None, edited_fields=None):
        """
        Processes Vet verification:
        Actions: 'verify', 'reject', 'save_changes', 'edit'
        Stores AI output, vet corrections, rating, timestamp, vet identity, and verification status.
        Triggers District Outbreak alert if High/Critical, and notifies the farmer.
        """
        incident = Incident.query.get(incident_id)
        if not incident:
            return None, "Incident not found"

        vet_profile = VetProfile.query.get(vet_id)
        vet_user = vet_profile.user if vet_profile else None
        vet_username = vet_user.username if vet_user else f"Vet #{vet_id}"

        incident.vet_id = vet_id
        is_verified = (action in ['verify', 'save_changes', 'edit'])
        incident.vet_verified = is_verified
        incident.status = 'resolved'
        incident.resolved_at = get_ist()

        if vet_notes:
            incident.vet_notes = vet_notes if is_verified else f"[REJECTED BY VET]: {vet_notes}"

        # Apply edited fields if provided
        edited_fields = edited_fields or {}
        if edited_fields.get("title"):
            incident.title = edited_fields["title"]
        if edited_fields.get("severity"):
            incident.severity = edited_fields["severity"]
        if edited_fields.get("symptoms"):
            incident.symptoms = edited_fields["symptoms"]

        # Store complete audit record
        original_rag = incident.get_rag_data() or {}
        correction_record = {
            "original_ai_response": original_rag,
            "ai_assessment_rating": ai_assessment_rating,
            "vet_corrected_fields": edited_fields,
            "vet_notes": vet_notes,
            "verified_at": get_ist().strftime("%Y-%m-%d %H:%M:%S"),
            "vet_username": vet_username,
            "verification_status": "verified" if is_verified else "rejected"
        }
        incident.set_vet_correction_data(correction_record)

        # 1. District Escalation for High / Critical severity
        sev = incident.severity.lower()
        if is_verified and sev in ['high', 'critical'] and incident.district_id:
            district = District.query.get(incident.district_id)
            if district:
                district.risk_level = 'red'
                # Create District Outbreak Alert Message
                alert_msg = Message(
                    sender_id=vet_user.id if vet_user else 1,
                    recipient_role='district_head',
                    district_id=district.id,
                    title=f"🚨 OUTBREAK ALERT: Verified High Risk Case #{incident.id} in {incident.village}",
                    content=f"Dr. {vet_username} verified a High Severity {incident.animal_type.title()} incident (#{incident.id}: {incident.title}) in {incident.village}, {incident.taluka}. Immediate biosecurity containment and 3 km surveillance zone recommended.",
                    message_type='emergency'
                )
        # 2. Notify Farmer, District Head, and State Head via NotificationService (Real-Time + DB)
        try:
            from backend.services.notification_service import NotificationService
            NotificationService.notify_vet_verification_completed(
                incident=incident,
                is_verified=is_verified,
                vet_user=vet_user,
                severity=sev,
                edited_fields=edited_fields
            )
        except Exception as n_ex:
            print(f"Error in NotificationService post-verification: {n_ex}")

        db.session.commit()
        return incident, None
