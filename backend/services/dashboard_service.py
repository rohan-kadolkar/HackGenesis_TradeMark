from models import db, Incident, District, FarmerProfile, VetProfile

class DashboardService:
    """
    Analytics & Aggregation Service for Vet, District, and State Dashboards.
    """
    @staticmethod
    def get_vet_incidents(vet_district_id, status_filter=None):
        query = Incident.query.filter_by(district_id=vet_district_id)
        if status_filter:
            query = query.filter_by(status=status_filter)
        return query.order_by(Incident.created_at.desc()).all()

    @staticmethod
    def get_district_dashboard(district_id):
        district = District.query.get(district_id)
        if not district:
            return None

        incidents = Incident.query.filter_by(district_id=district_id).order_by(Incident.created_at.desc()).all()
        
        # Build outbreak events for Medium/High/Critical cases
        outbreak_events = []
        for inc in incidents:
            if inc.severity in ['medium', 'high', 'critical']:
                outbreak_events.append({
                    "incident_id": inc.id,
                    "district": district.name,
                    "village": inc.village or "Unknown",
                    "taluka": inc.taluka or "Unknown",
                    "animal_type": inc.animal_type,
                    "symptoms": inc.symptoms,
                    "severity": inc.severity,
                    "risk_level": "red" if inc.severity in ['high', 'critical'] else "yellow",
                    "status": inc.status,
                    "vet_verified": inc.vet_verified,
                    "map_marker": {
                        "lat": district.latitude or 12.9716,
                        "lng": district.longitude or 77.5946
                    }
                })

        return {
            "district_id": district.id,
            "district_name": district.name,
            "risk_level": district.risk_level,
            "vaccination_coverage": district.vaccination_coverage,
            "total_incidents": len(incidents),
            "active_outbreaks": len(outbreak_events),
            "outbreak_events": outbreak_events
        }

    @staticmethod
    def get_state_dashboard():
        districts = District.query.all()
        incidents = Incident.query.all()

        verified_incidents = [i for i in incidents if i.vet_verified is True]

        red_zones = [d.name for d in districts if d.risk_level == 'red']
        yellow_zones = [d.name for d in districts if d.risk_level == 'yellow']

        # Aggregated disease trends
        disease_counts = {}
        for i in verified_incidents:
            atype = i.animal_type or "other"
            disease_counts[atype] = disease_counts.get(atype, 0) + 1

        return {
            "total_districts": len(districts),
            "total_incidents": len(incidents),
            "total_verified": len(verified_incidents),
            "red_zones_count": len(red_zones),
            "red_zone_districts": red_zones,
            "yellow_zones_count": len(yellow_zones),
            "yellow_zone_districts": yellow_zones,
            "disease_trends": disease_counts,
            "heatmap_points": [
                {
                    "district": d.name,
                    "lat": d.latitude,
                    "lng": d.longitude,
                    "risk": d.risk_level,
                    "cases": Incident.query.filter_by(district_id=d.id).count()
                }
                for d in districts
            ]
        }
