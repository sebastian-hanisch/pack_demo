"""
Feedback-Logging für die Frage "War diese Demo hilfreich?" - identisches
Muster wie in der Touren-Demo (vrp_feedback.py), hier eigenständig gehalten,
damit jede Demo unabhängig deploybar bleibt.

Hinweis für den produktiven Einsatz: Auf Streamlit Community Cloud ist das
Dateisystem nicht dauerhaft persistent (Reset bei Neustart/Redeploy). Für
zuverlässige Langzeit-Auswertung eignet sich z. B. eine Anbindung an ein
Google Sheet oder eine kleine Datenbank besser als diese CSV-Lösung.
"""

import csv
import os
import time

from pack_constants import FEEDBACK_FILE

# Absolut statt relativ zum aktuellen Arbeitsverzeichnis aufgelöst: mehrere
# Demos in diesem Workspace teilen sich denselben Dateinamen "feedback_log.csv"
# und werden teils aus einem gemeinsamen übergeordneten Verzeichnis gestartet
# (siehe .claude/launch.json) - ein relativer Pfad hätte alle Demos in dieselbe
# Datei schreiben lassen, ununterscheidbar nach Demo.
FEEDBACK_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), FEEDBACK_FILE)


def log_feedback(vote, feedback_file=FEEDBACK_FILE_PATH):
    try:
        with open(feedback_file, "a", newline="", encoding="utf-8") as f:
            # Header-Bedarf erst NACH dem Öffnen im Append-Modus per f.tell()
            # geprüft (statt vorher per os.path.exists) - schließt das Zeitfenster
            # zwischen Prüfung und Schreiben, in dem zwei nahezu gleichzeitige
            # Streamlit-Sessions sonst beide eine Kopf-Zeile schreiben könnten.
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(["timestamp", "vote"])
            writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), vote])
        return True
    except Exception:
        return False


def get_feedback_counts(feedback_file=FEEDBACK_FILE_PATH):
    try:
        if not os.path.exists(feedback_file):
            return 0, 0
        up, down = 0, 0
        with open(feedback_file, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("vote") == "up":
                    up += 1
                elif row.get("vote") == "down":
                    down += 1
        return up, down
    except Exception:
        return 0, 0
