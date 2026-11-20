import logging
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import config

logging.basicConfig(level=logging.INFO)

GEMINI_API_KEY = getattr(config, "gemini_api_key", None) or getattr(
    config, "GEMINI_API_KEY", ""
)

MODELS_TO_TRY = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.8-flash",
]


def _get_client() -> genai.Client:
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta"},
    )


class MorningPlan(BaseModel):
    coach_message: str = Field(
        description=(
            "Deine ausführliche Analyse und Trainingsempfehlung für Telegram. "
            "Nutze ausschließlich <b>fett</b>, <i>kursiv</i> und normale Zeilenumbrüche (\\n). "
            "Verwende KEINE <br>-Tags, kein Markdown (** oder ###) und keine Emojis."
        )
    )
    create_workout: bool = Field(
        description="True, wenn heute ein Radtraining sinnvoll ist. False bei komplettem Ruhetag."
    )
    workout_name: str = Field(
        description="Kurzer Workout-Titel für Zwift (z. B. 'KI-Coach: GA1 Locker' oder 'KI-Coach: 3x8m Sweetspot')."
    )
    intervals_workout_steps: str = Field(
        description=(
            "Reiner Workout-Text in offizieller Intervals.icu Workout-Builder-Syntax ohne Erklärungen. "
            "Jeder Schritt beginnt mit '- ', gefolgt von optionalem Label, Dauer (10m, 30s), "
            "Leistung in % FTP (z. B. 55%, 90-95%, ramp 50-75%) und optional Trittfrequenz (z. B. 90rpm). "
            "Wiederholungen als 'Main Set 3x' vor den Schritten schreiben.\n"
            "Beispiel:\n"
            "Warmup\n"
            "- 10m ramp 50-75% 90rpm\n\n"
            "Main Set 3x\n"
            "- Belastung 8m 90-95% 95rpm\n"
            "- Locker 4m 55% 85rpm\n\n"
            "Cooldown\n"
            "- 10m ramp 65-45% 85rpm"
        )
    )


def generate_morning_plan(strava_data, garmin_data=None) -> MorningPlan | None:
    prompt = f"""
    Du bist ein hochspezialisierter Radsport-Coach für einen Fahrer des RSV Wattenscheid.

    Deine Aufgabe:
    1. Analysiere die gestrige Strava-Aktivität und die heutigen Garmin-Morgenwerte.
    2. Entscheide, ob heute ein Ruhetag (create_workout=False) oder ein strukturiertes Zwift-Workout (create_workout=True) sinnvoll ist.
    3. Wenn create_workout=True: Erstelle ein passendes Workout in exakter Intervals.icu-Syntax (nur % FTP und rpm verwenden, keine absoluten Wattwerte).
    4. Verwende in deiner Antwort keine Emojis.

    GARMIN MORGENBERICHT (HEUTE):
    {garmin_data}

    STRAVA TRAININGSDATEN (VORTAG):
    {strava_data if strava_data else "Keine Einheit am Vortag verzeichnet."}
    """

    if not GEMINI_API_KEY:
        logging.error("Fehler: Kein Gemini-API-Key in config.py vorhanden.")
        return None

    client = _get_client()

    for attempt, model_name in enumerate(MODELS_TO_TRY, start=1):
        try:
            logging.info(
                f"Versuch {attempt}: Sende Morgenplan-Anfrage an Modell {model_name}"
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MorningPlan,
                ),
            )
            if response.text:
                logging.info(
                    f"Gemini-Morgenplan über {model_name} erfolgreich abgerufen."
                )
                return MorningPlan.model_validate_json(response.text)

        except Exception as e:
            print(f"Gemini-Fehler ({model_name}, Versuch {attempt}): {e}")
            time.sleep(5 * attempt)

    print(
        "KRITISCHER GEMINI-FEHLER: Morgenplan konnte nicht erstellt werden."
    )
    return None


def generate_evening_feedback(strava_data, garmin_data=None) -> str:
    prompt = f"""
    Du bist ein hochspezialisierter Radsport-Coach für einen Fahrer des RSV Wattenscheid.
    
    Deine Aufgabe: Bewerte den heutigen Tagesverlauf (Aktivität, Schritte, Stress, Body Battery) und bereite den Athleten optimal auf die Nachtruhe vor.
    Nutze ausschließlich <b>fett</b>, <i>kursiv</i> und normale Zeilenumbrüche (\\n). Verwende KEINE <br>-Tags, kein Markdown (*) und keine Emojis.

    GARMIN TAGESDATEN:
    {garmin_data}

    STRAVA HEUTIGE EINHEIT:
    {strava_data if strava_data else "Keine Einheit heute."}
    """
    return _query_gemini(prompt)


def generate_activity_feedback(strava_data, planned_workout=None) -> str:
    prompt = f"""
    Du bist ein hochspezialisierter Radsport-Coach für einen Fahrer des RSV Wattenscheid.
    
    Deine Aufgabe: Analysiere eine soeben hochgeladene Einheit direkt nach dem Training.

    GEPLANTES WORKOUT HEUTE (INTERVALS.ICU):
    {planned_workout if planned_workout else "Freie Einheit (kein Workout geplant)."}

    STRAVA AKTIVITÄTSDATEN:
    {strava_data}

    Erstelle deine Analyse strikt in folgenden Abschnitten (nutze ausschließlich <b>fett</b>, <i>kursiv</i> und normale Zeilenumbrüche \\n, KEINE <br>-Tags, kein Markdown * und keine Emojis):
    1. <b>Leistung & Soll/Ist-Abgleich:</b> Bewertung von Watt/Pace/Pacing, Herzfrequenzbereichen und ob das geplante Workout getroffen wurde.
    2. <b>Belastungs-Check (Suffer/NP):</b> War die Einheit im Zielbereich oder wurde überpaced/getrödelt?
    3. <b>Sofort-Regeneration (Post-Workout):</b> Konkrete Empfehlung für Carbs, Proteine und Flüssigkeit direkt nach der Einheit.
    """
    return _query_gemini(prompt)


def _query_gemini(prompt: str) -> str:
    if not GEMINI_API_KEY:
        logging.error("Fehler: Kein Gemini-API-Key in config.py vorhanden.")
        return "KI-Analyse nicht verfügbar: Es ist kein Gemini-API-Key konfiguriert."

    client = _get_client()

    for attempt, model_name in enumerate(MODELS_TO_TRY, start=1):
        try:
            logging.info(
                f"Versuch {attempt}: Sende Anfrage an Modell {model_name}"
            )
            response = client.models.generate_content(
                model=model_name, contents=prompt
            )
            if response.text:
                logging.info(
                    f"Gemini-Anfrage über {model_name} erfolgreich abgerufen."
                )
                return response.text

        except Exception as e:
            print(f"Gemini-Fehler ({model_name}, Versuch {attempt}): {e}")
            time.sleep(5 * attempt)

    print("KRITISCHER GEMINI-FEHLER: Alle Modell-Aufrufe schlugen fehl.")
    return "KI-Analyse nicht verfügbar. Bitte Gemini-API-Key und Auslastung prüfen."
