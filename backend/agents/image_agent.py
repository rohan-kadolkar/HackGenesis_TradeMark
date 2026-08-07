class ImageAnalysisAgent:
    """
    Agent 1: Image Analysis Agent
    Parses and standardizes Gemma Vision output into a structured incident object.
    """
    def execute(self, gemma_output, raw_form_data=None):
        raw_form_data = raw_form_data or {}
        gemma_output = gemma_output or {}

        # 1. Animal Type detection
        animal_type = (
            gemma_output.get("animal_type") or 
            gemma_output.get("animal") or 
            raw_form_data.get("animal_type", "cattle")
        )
        animal_type = str(animal_type).lower()
        if any(k in animal_type for k in ['cow', 'calf', 'bull', 'cattle', 'milk']):
            animal_type = 'cattle'
        elif any(k in animal_type for k in ['hen', 'chicken', 'bird', 'flock', 'poultry']):
            animal_type = 'poultry'
        elif any(k in animal_type for k in ['pig', 'swine', 'boar']):
            animal_type = 'pig'
        elif any(k in animal_type for k in ['goat', 'sheep', 'lamb']):
            animal_type = 'goat'
        else:
            animal_type = 'cattle'

        # 2. Symptoms extraction from Gemma visible_abnormalities / symptoms
        abnormalities = (
            gemma_output.get("visible_abnormalities") or 
            gemma_output.get("symptoms_observed") or 
            gemma_output.get("symptoms") or 
            raw_form_data.get("symptoms")
        )
        if isinstance(abnormalities, list):
            symptoms = ", ".join([str(item).strip() for item in abnormalities if item])
        elif abnormalities:
            symptoms = str(abnormalities).strip()
        else:
            symptoms = "Observable physical discomfort and health distress signs detected."

        # 3. Issue Title extraction from Gemma possible_concern / title
        concern = (
            gemma_output.get("possible_concern") or 
            gemma_output.get("issue_title") or 
            gemma_output.get("title") or 
            raw_form_data.get("title")
        )
        if concern and str(concern).strip():
            title = str(concern).strip()
            if not title.lower().startswith("visual inspection") and not title.lower().startswith("suspected"):
                title = f"Suspected {title.title()}"
        else:
            title = f"{animal_type.title()} Health Incident - {symptoms[:40]}"

        # 4. Description & Farmer Action extraction
        action = (
            gemma_output.get("farmer_action") or 
            gemma_output.get("description") or 
            raw_form_data.get("description")
        )
        if action and str(action).strip():
            description = f"Visual inspection notes: {action}. Symptoms observed: {symptoms}."
        else:
            description = f"Gemma AI vision detected {symptoms} in {animal_type}. Immediate isolation and veterinary examination recommended."

        # 5. Severity / Urgency extraction
        severity = str(
            gemma_output.get("severity") or 
            gemma_output.get("urgency") or 
            raw_form_data.get("severity", "medium")
        ).lower()
        if severity not in ['low', 'medium', 'high', 'critical']:
            severity = 'high' if any(k in symptoms.lower() for k in ['lesion', 'ulcer', 'fever', 'blood', 'death']) else 'medium'

        confidence = float(gemma_output.get("confidence", 0.88))
        needs_vet_visit = bool(gemma_output.get("requires_vet_review", True))

        return {
            "animal_type": animal_type,
            "title": title,
            "issue_title": title,
            "description": description,
            "symptoms": symptoms,
            "symptoms_observed": symptoms,
            "severity": severity,
            "confidence": confidence,
            "needs_vet_visit": needs_vet_visit,
            "affected_count": int(raw_form_data.get("affected_count", 1))
        }
