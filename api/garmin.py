from datetime import date
from garmin_personal_api import (
    GarminPersonalApiClient,
    PersonalApiAuthenticator,
    resolve_api_key,
)


def fetch_garmin_data(target_date: str = None):
    if not target_date:
        target_date = date.today().isoformat()

    print(f"Authentifiziere mit Garmin Personal API ({target_date})...")

    with PersonalApiAuthenticator() as authenticator:
        token = authenticator.obtain_token(resolve_api_key())

    with GarminPersonalApiClient(token.access_token) as client:
        summaries = client.get_daily_summaries(target_date, target_date)
        sleep_data = client.get_daily_sleep(target_date)
        hrv_data = client.get_daily_hrv(target_date)

        data_list = (
            summaries.get("data", [])
            if isinstance(summaries, dict)
            else summaries
        )
        summary = (
            data_list[0] if isinstance(data_list, list) and data_list else {}
        )
        sleep = sleep_data if isinstance(sleep_data, dict) else {}
        hrv_summary = (
            (hrv_data.get("hrvSummary") or {})
            if isinstance(hrv_data, dict)
            else {}
        )
        sleep_sec = sleep.get("sleepTimeSeconds") or 0

        return {
            "date": target_date,
            "rhr": (summary.get("heartRate") or {}).get("restingValue", "N/A"),
            "body_battery_max": (summary.get("bodyBattery") or {}).get(
                "maxValue", "N/A"
            ),
            "body_battery_charged": (summary.get("bodyBattery") or {}).get(
                "chargedValue", "N/A"
            ),
            "steps": (
                ((summary.get("movement") or {}).get("steps") or {}).get(
                    "value", "N/A"
                )
            ),
            "sleep_score": (
                ((sleep.get("sleepScores") or {}).get("overall") or {}).get(
                    "value", "N/A"
                )
            ),
            "total_sleep_hours": (
                round(sleep_sec / 3600, 1) if sleep_sec else "N/A"
            ),
            "hrv_last_night": hrv_summary.get("lastNightAvg", "N/A"),
            "hrv_status": hrv_summary.get("status", "N/A"),
        }