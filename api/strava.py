import requests
from datetime import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def get_access_token():
    """Holt automatisch einen frischen 6-Stunden Access Token über den Refresh Token."""
    url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": "275702",
        "client_secret": "740ce866011b0166ea5bcf93305a4ef8bee777b6",
        "refresh_token": "aa5331cf77a83488b2d593c354796fe5a674c36b",
        "grant_type": "refresh_token",
    }

    response = requests.post(url, data=payload)
    if response.status_code == 200:
        logging.info(f"Access Token erfolgreich abgerufen: {response.json()}")
        return response.json().get("access_token")
    else:
        logging.error(f"Fehler beim Abrufen des Access Tokens: {response.status_code}, {response.text}")
        return None

def get_latest_activities(anzahl=5):
    """Ruft die neuesten Aktivitäten von Strava ab."""
    token = get_access_token()

    if not token:
        logging.error("Fehler: Access Token konnte nicht abgerufen werden.")
        return []

    url = f"https://www.strava.com/api/v3/activities?per_page={anzahl}"
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logging.info(f"Neueste Aktivitäten erfolgreich abgerufen: {len(response.json())} Einheiten")
        return response.json()
    else:
        logging.error(f"Fehler bei Strava API ({response.status_code}): {response.text}")
        return []