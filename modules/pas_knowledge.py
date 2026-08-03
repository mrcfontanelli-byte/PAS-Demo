"""Base di conoscenza iniziale del PAS Intelligence Engine.

Contiene solo sinonimi e regole di navigazione deterministiche. Le regole
interpretative calcistiche verranno aggiunte in release successive.
"""

METRIC_ALIASES = {
    "rpe": "RPE",
    "percezione sforzo": "RPE",
    "distanza totale": "Distance (m)",
    "total distance": "Distance (m)",
    "distance": "Distance (m)",
    "distanza": "Distance (m)",
    "metri totali": "Distance (m)",
    "relative distance": "Relative Distance (m/min)",
    "distanza relativa": "Relative Distance (m/min)",
    "metri al minuto": "Relative Distance (m/min)",
    "hsr": "Distance 19.8-25.2 km/h (m)",
    "alta intensita": "Distance 19.8-25.2 km/h (m)",
    "distanza 19.8 25.2": "Distance 19.8-25.2 km/h (m)",
    "distanza sopra 25.2": "Distance >25.2 km/h (m)",
    "distance sopra 25.2": "Distance >25.2 km/h (m)",
    "distance >25.2": "Distance >25.2 km/h (m)",
    "distanza >25.2": "Distance >25.2 km/h (m)",
    "sprint distance": "Distance >25.2 km/h (m)",
    "distanza sprint": "Distance >25.2 km/h (m)",
    "sprint": "Distance >25.2 km/h (m)",
    "accelerazioni": "Acc Events (n°)",
    "accelerazione": "Acc Events (n°)",
    "acc events": "Acc Events (n°)",
    "decelerazioni": "Dec Events (n°)",
    "decelerazione": "Dec Events (n°)",
    "dec events": "Dec Events (n°)",
    "velocita massima": "Max Speed (km/h)",
    "massima velocita": "Max Speed (km/h)",
    "max speed": "Max Speed (km/h)",
    "speed events": "Speed Events (n°)",
    "eventi velocita": "Speed Events (n°)",
    "durata": "Duration (min)",
    "minuti": "Duration (min)",
}

SECTION_KEYWORDS = {
    "🗓️ Planner": ("planner", "calendario", "agenda", "pianificazione"),
    "🔮 Forecast": ("forecast", "previsione", "programma seduta", "carico previsto"),
    "⚽ Match Analysis": ("partita", "partite", "match", "avversario"),
    "🧩 Drills": ("drill", "drills", "esercitazione", "esercitazioni", "possesso", "possession", "small sided"),
    "📊 Period Load": ("accumulo", "carico cumulativo", "period load", "match cycle", "ciclo gara", "cicli gara", "microciclo", "microcicli", "ultimi 7 giorni", "ultimi 14 giorni", "ultimi 28 giorni"),
    "🏥 Return To Play": ("return to play", "rtp", "riabilitazione"),
}

FOLLOW_UP_PREFIXES = (
    "ora ", "adesso ", "poi ", "e ", "invece ", "solo ", "anche ",
)
