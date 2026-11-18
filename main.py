import argparse
import os
import sys
from datetime import date

sys.path.append("./bot")
sys.path.append("./api")

from api.garmin import fetch_garmin_data
from api.gemini import (
    generate_activity_feedback,
    generate_evening_feedback,
    generate_morning_plan,
)
from api.intervals import get_todays_workout, upload_workout_to_intervals
from api.strava import get_latest_activities
from bot import telegram_bot

LAST_ACTIVITY_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "last_activity_id.txt"
)


def _extract_strava_summary(activity: dict) -> dict:
    """Filtert GPS-Polylines heraus und behält nur relevante Trainingswerte."""
    if not activity:
        return {}
    return {
        "name": activity.get("name"),
        "type": activity.get("sport_type") or activity.get("type"),
        "date": activity.get("start_date_local"),
        "distance_km": round(activity.get("distance", 0) / 1000, 2),
        "moving_time_min": round(activity.get("moving_time", 0) / 60, 1),
        "elevation_gain_m": activity.get("total_elevation_gain"),
        "avg_watts": activity.get("average_watts"),
        "weighted_avg_watts": activity.get("weighted_average_watts"),
        "max_watts": activity.get("max_watts"),
        "avg_hr": activity.get("average_heartrate"),
        "max_hr": activity.get("max_heartrate"),
        "avg_cadence": activity.get("average_cadence"),
        "suffer_score": activity.get("suffer_score"),
        "kilojoules": activity.get("kilojoules"),
    }


def get_formatted_garmin_text(garmin_data):
    """Formatiert die direkt via API abgeholten Garmin-Daten für Telegram (HTML)."""
    if not garmin_data:
        return "Keine Garmin-Daten über die API erhalten.\n\n"

    datum_clean = garmin_data.get("date", str(date.today()))
    rhr = garmin_data.get("rhr", "N/A")
    bb_max = garmin_data.get("body_battery_max", "N/A")
    bb_charged = garmin_data.get("body_battery_charged", "N/A")
    steps = garmin_data.get("steps", "N/A")

    total_sleep = garmin_data.get("total_sleep_hours", "N/A")
    sleep_score = garmin_data.get("sleep_score", "N/A")
    hrv_last = garmin_data.get("hrv_last_night", "N/A")
    hrv_status = garmin_data.get("hrv_status", "N/A")

    return (
        f"<b>DEIN GARMIN-BERICHT</b> ({datum_clean})\n"
        f"================================\n\n"
        f"<b>Aktivität & Herzfrequenz:</b>\n"
        f"  • Ruhepuls (RHR): {rhr} BPM\n\n"
        f"<b>Energie & Belastung:</b>\n"
        f"  • Body Battery: Max {bb_max}\n"
        f"  • Regeneration: +{bb_charged} geladen\n"
        f"  • Schritte: {steps}\n\n"
        f"<b>Schlaf-Analyse:</b>\n"
        f"  • Gesamtschlaf: {total_sleep} Std.\n"
        f"  • Schlafwert: {sleep_score}\n\n"
        f"<b>Herzratenvariabilität (HFV):</b>\n"
        f"  • Letzte Nacht: {hrv_last} ms\n"
        f"  • Status: {hrv_status}\n\n"
        f"================================\n\n"
    )


def run_morning_report():
    print("Generiere Morgenbericht & Zwift-Workout...")
    today_str = date.today().isoformat()

    garmin_data = fetch_garmin_data(today_str)
    garmin_text = get_formatted_garmin_text(garmin_data)

    strava_activities = get_latest_activities(1)
    latest_ride = (
        _extract_strava_summary(strava_activities[0])
        if strava_activities
        else {}
    )

    plan = generate_morning_plan(
        strava_data=latest_ride, garmin_data=garmin_text
    )

    if not plan:
        return None

    sync_hinweis = ""
    if plan.create_workout and plan.intervals_workout_steps.strip():
        erfolg = upload_workout_to_intervals(
            workout_name=plan.workout_name,
            workout_steps=plan.intervals_workout_steps,
            target_date=today_str,
        )
        if erfolg:
            sync_hinweis = (
                f"\n\n<b>Zwift-Workout hochgeladen:</b> {plan.workout_name}\n"
                f"<i>(In Zwift unter Workouts → Custom → Intervals.icu)</i>"
            )

    gesamte_nachricht = (
        garmin_text
        + "<b>KI-COACH MORGEN-EMPFEHLUNG:</b>\n\n"
        + plan.coach_message
        + sync_hinweis
    )
    telegram_bot.send_message(gesamte_nachricht)
    print("Morgenbericht & Zwift-Sync abgeschlossen!")


def run_evening_report():
    print("Generiere Abendbericht...")
    today_str = date.today().isoformat()

    garmin_data = fetch_garmin_data(today_str)
    garmin_text = get_formatted_garmin_text(garmin_data)

    strava_activities = get_latest_activities(1)
    latest_ride = (
        _extract_strava_summary(strava_activities[0])
        if strava_activities
        else {}
    )

    ki_empfehlung = generate_evening_feedback(
        strava_data=latest_ride, garmin_data=garmin_text
    )

    gesamte_nachricht = (
        garmin_text + "<b>KI-COACH ABEND-FAZIT:</b>\n\n" + ki_empfehlung
    )
    telegram_bot.send_message(gesamte_nachricht)
    print("Abendbericht erfolgreich gesendet!")


def run_activity_report():
    print("Prüfe auf neue Strava-Aktivität...")
    strava_activities = get_latest_activities(1)

    if not strava_activities:
        print("Keine Aktivität gefunden.")
        return

    latest_ride = strava_activities[0]
    activity_id = str(latest_ride.get("id", ""))

    if os.path.exists(LAST_ACTIVITY_FILE):
        with open(LAST_ACTIVITY_FILE, "r", encoding="utf-8") as f:
            if f.read().strip() == activity_id:
                print(f"Aktivität {activity_id} wurde bereits analysiert.")
                return

    clean_ride = _extract_strava_summary(latest_ride)
    planned = get_todays_workout(date.today().isoformat())
    ki_empfehlung = generate_activity_feedback(
        strava_data=clean_ride, planned_workout=planned
    )

    gesamte_nachricht = (
        f"<b>NEUE STRAVA-EINHEIT ANALYSIERT</b>\n"
        f"================================\n\n"
        f"<b>ANALYSE & ZONEN-AUSWERTUNG:</b>\n\n" + ki_empfehlung
    )
    telegram_bot.send_message(gesamte_nachricht)

    with open(LAST_ACTIVITY_FILE, "w", encoding="utf-8") as f:
        f.write(activity_id)

    print(f"Aktivitätsbericht ({activity_id}) erfolgreich gesendet!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cycling AI-Coach")
    parser.add_argument(
        "--morning",
        action="store_true",
        help="Sendet den morgendlichen Readiness-Bericht",
    )
    parser.add_argument(
        "--evening", action="store_true", help="Sendet den Abendbericht"
    )
    parser.add_argument(
        "--activity",
        action="store_true",
        help="Analysiert die letzte Strava-Aktivität",
    )

    args = parser.parse_args()

    if args.morning:
        run_morning_report()
    elif args.evening:
        run_evening_report()
    elif args.activity:
        run_activity_report()
    else:
        print(
            "Bitte einen Modus angeben: python main.py --morning, --evening oder"
            " --activity"
        )
