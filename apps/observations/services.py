from .models import Observation


def to_geojson(user):
    observations = Observation.objects.filter(user=user)
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [obs.longitude, obs.latitude],
            },
            "properties": {
                "id": str(obs.id),
                "speciesName": obs.species_name,
                "scientificName": obs.scientific_name,
                "topConfidence": obs.top_confidence,
                "notes": obs.notes,
                "observedAt": obs.observed_at.isoformat(),
            },
        }
        for obs in observations
    ]
    return {"type": "FeatureCollection", "features": features}
