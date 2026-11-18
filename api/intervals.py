from datetime import date
import requests
from requests.auth import HTTPBasicAuth
from config import INTERVALS_API_KEY


def upload_workout_to_intervals(
    workout_name: str, workout_steps: str, target_date: str = None
) -> bool:
    """Erstellt oder aktualisiert das heutige KI-Workout in Intervals.icu (inkl. Zwift-Sync)."""
    if not target_date:
        target_date = date.today().isoformat()

    url = "https://intervals.icu/api/v1/athlete/0/events/bulk?upsert=true"
    auth = HTTPBasicAuth("API_KEY", INTERVALS_API_KEY)

    payload = [
        {
            "category": "WORKOUT",
            "start_date_local": f"{target_date}T00:00:00",
            "type": "Ride",
            "name": workout_name,
            "description": workout_steps,
            "external_id": f"ai-coach-{target_date}",
        }
    ]

    try:
        response = requests.post(url, json=payload, auth=auth, timeout=15)
        if response.status_code in (200, 201):
            created = response.json()
            if created and created[0].get("workout_doc"):
                print(
                    f"Workout '{workout_name}' geparst & an Zwift übergeben!"
                )
                return True
            print(
                "Workout angelegt, aber Schritte konnten nicht geparst werden."
            )
            return False

        print(
            f"Intervals.icu API-Fehler ({response.status_code}): {response.text}"
        )
        return False

    except Exception as e:
        print(f"Verbindungsfehler zu Intervals.icu: {e}")
        return False


def get_todays_workout(target_date: str = None) -> str | None:
    """Liest das heute geplante Workout aus Intervals.icu für den Soll/Ist-Abgleich."""
    if not target_date:
        target_date = date.today().isoformat()

    url = (
        f"https://intervals.icu/api/v1/athlete/0/events"
        f"?oldest={target_date}&newest={target_date}"
    )
    auth = HTTPBasicAuth("API_KEY", INTERVALS_API_KEY)

    try:
        response = requests.get(url, auth=auth, timeout=15)
        if response.status_code == 200:
            for event in response.json():
                if event.get("category") == "WORKOUT":
                    return (
                        f"{event.get('name')}:\n{event.get('description', '')}"
                    )
        return None
    except Exception:
        return None
