from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from modules.config import METRICS
from modules.pas_knowledge import FOLLOW_UP_PREFIXES, METRIC_ALIASES, SECTION_KEYWORDS
from modules.pas_load_index import PLI_COMPONENTS, calculate_pli


@dataclass
class AssistantRequest:
    query: str
    players: list[str]
    roles: list[str]
    metric: str | None
    date: pd.Timestamp | None
    operator: str | None
    threshold: float | None
    threshold_source: str | None
    top_n: int | None
    bottom_n: int | None
    drill: str | None
    compare_history: bool
    compare_team: bool
    compare_role: bool
    starter_statuses: list[str]
    max_speed_percent: bool
    composite_load: bool
    session_overview: bool
    cycles: list[str]
    period_start: pd.Timestamp | None
    period_end: pd.Timestamp | None


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9.,><=]+", " ", text.lower()).strip()


def _metric_aliases() -> dict[str, str]:
    aliases = dict(METRIC_ALIASES)
    for name in METRICS:
        aliases[_norm(name)] = name
    return aliases


def _find_metric(text: str) -> str | None:
    for alias, name in sorted(_metric_aliases().items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
            return name
    return None


def _find_players(text: str, data: pd.DataFrame) -> list[str]:
    found: list[str] = []
    for player in sorted(data["Athlete"].dropna().astype(str).unique(), key=len, reverse=True):
        full = _norm(player)
        tokens = [token for token in full.split() if len(token) >= 4]
        candidates = [full, *tokens]
        if any(re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", text) for candidate in candidates):
            found.append(player)
    return list(dict.fromkeys(found))


def _role_column(data: pd.DataFrame) -> str | None:
    for column in ("Role Clean", "Role", "Position"):
        if column in data.columns:
            return column
    return None


def _find_roles(text: str, data: pd.DataFrame) -> list[str]:
    column = _role_column(data)
    if not column:
        return []
    found: list[str] = []
    for role in sorted(data[column].dropna().astype(str).unique(), key=len, reverse=True):
        normalized = _norm(role)
        if normalized and re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text):
            found.append(role)
    return found


ROLE_ALIASES = {
    "portieri": ("GOALKEEPER",), "portiere": ("GOALKEEPER",),
    "difensori centrali": ("Centre Back", "center back"), "centrali": ("Centre Back", "center back"),
    "terzini": ("Full Back", "Full back", "Side Back", "side back"),
    "quinti": ("Wing Back", "wing backs"), "esterni": ("Wing Back", "wing backs", "Winger"),
    "centrocampisti": ("Central Midfielder", "Midfielder", "midfileder", "Play", "playmaker"),
    "trequartisti": ("Attacking Midfielder",), "ali": ("Winger",),
    "attaccanti": ("Forward", "Foward", "forward"), "punte": ("Forward", "Foward", "forward"),
}

def _find_starter_statuses(text: str) -> list[str]:
    """Riconosce S/NS dal linguaggio naturale senza sovrapposizioni."""
    normalized = _norm(text)
    has_ns_words = bool(re.search(
        r"(?<!\w)(?:no\s+starters?|non\s+starters?|non\s+titolari?|riserve|ns)(?!\w)",
        normalized,
    ))
    # Rimuove prima le espressioni NS, così "no starters" non attiva anche "starters".
    starter_text = re.sub(
        r"(?<!\w)(?:no\s+starters?|non\s+starters?|non\s+titolari?|riserve|ns)(?!\w)",
        " ",
        normalized,
    )
    has_s_words = bool(re.search(
        r"(?<!\w)(?:starters?|titolari?|s)(?!\w)",
        starter_text,
    ))
    statuses: list[str] = []
    if has_s_words:
        statuses.append("S")
    if has_ns_words:
        statuses.append("NS")
    return statuses

def _find_role_aliases(text: str, data: pd.DataFrame) -> list[str]:
    direct = _find_roles(text, data)
    role_col = _role_column(data)
    available = set(data[role_col].dropna().astype(str)) if role_col else set()
    for alias, candidates in ROLE_ALIASES.items():
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
            direct.extend(candidate for candidate in candidates if candidate in available)
    return list(dict.fromkeys(direct))

def _available_dates(data: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(data["Date"], errors="coerce").dropna().dt.normalize()


def _latest_reference_date(data: pd.DataFrame) -> pd.Timestamp | None:
    full_training_dates = pd.to_datetime(
        data.loc[data["Drill"].eq("Full Training"), "Date"], errors="coerce"
    ).dropna().dt.normalize()
    dates = _available_dates(data)
    if not full_training_dates.empty:
        return pd.Timestamp(full_training_dates.max())
    return pd.Timestamp(dates.max()) if not dates.empty else None


def _find_date(query: str, text: str, data: pd.DataFrame) -> pd.Timestamp | None:
    latest = _latest_reference_date(data)
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", query)
    if match:
        day, month, year = match.groups()
        year_value = int(year) if year else int(latest.year if latest is not None else pd.Timestamp.today().year)
        if year_value < 100:
            year_value += 2000
        try:
            return pd.Timestamp(year=year_value, month=int(month), day=int(day))
        except ValueError:
            return latest
    dates = sorted(pd.Timestamp(value) for value in _available_dates(data).unique())
    if "ieri" in text and latest is not None:
        previous = [value for value in dates if value < latest]
        return previous[-1] if previous else latest
    return latest



def _cycle_order(data: pd.DataFrame) -> list[str]:
    if "Cycle" not in data.columns or "Date" not in data.columns:
        return []
    frame = data[["Cycle", "Date"]].dropna().copy()
    if frame.empty:
        return []
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return (frame.dropna(subset=["Date"])
            .groupby("Cycle", as_index=False)["Date"].max()
            .sort_values("Date")["Cycle"].astype(str).tolist())


def _find_cycles(text: str, data: pd.DataFrame) -> list[str]:
    cycles = _cycle_order(data)
    if not cycles:
        return []
    found = [cycle for cycle in cycles if _norm(cycle) in text]
    match = re.search(r"(?:ultimi|ultime|precedenti|scorsi)\s*(\d+)\s*(?:cicli|microcicli)(?:\s*gara)?", text)
    if match:
        count = max(1, int(match.group(1)))
        return cycles[-count:]
    if any(term in text for term in ("ciclo attuale", "ciclo gara attuale", "ciclo corrente", "ciclo gara corrente", "questo ciclo", "microciclo attuale")):
        return cycles[-1:]
    if any(term in text for term in ("ciclo precedente", "ciclo gara precedente", "ciclo scorso", "microciclo precedente")):
        return cycles[-2:-1] if len(cycles) > 1 else cycles[-1:]
    return list(dict.fromkeys(found))



def _find_period_range(text: str, data: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Riconosce intervalli naturali inclusivi, riferiti all'ultimo dato disponibile."""
    dates = _available_dates(data)
    latest = pd.Timestamp(dates.max()) if not dates.empty else None
    if latest is None:
        return None, None

    match = re.search(r"(?:ultimi|ultime)\s*(\d+)\s*giorni", text)
    if match:
        days = max(1, int(match.group(1)))
        return latest - pd.Timedelta(days=days - 1), latest

    match = re.search(r"(?:ultime|ultimi)\s*(\d+)\s*settimane", text)
    if match:
        weeks = max(1, int(match.group(1)))
        return latest - pd.Timedelta(days=weeks * 7 - 1), latest

    if any(term in text for term in ("questa settimana", "settimana corrente")):
        start = latest - pd.Timedelta(days=int(latest.weekday()))
        return start.normalize(), latest

    if any(term in text for term in ("settimana scorsa", "settimana precedente")):
        current_start = latest - pd.Timedelta(days=int(latest.weekday()))
        return (current_start - pd.Timedelta(days=7)).normalize(), (current_start - pd.Timedelta(days=1)).normalize()

    if any(term in text for term in ("questo mese", "mese corrente")):
        return latest.replace(day=1).normalize(), latest

    return None, None

def _find_drill(text: str, data: pd.DataFrame, date: pd.Timestamp | None) -> str | None:
    frame = data
    if date is not None:
        frame = frame[pd.to_datetime(frame["Date"], errors="coerce").dt.normalize().eq(date.normalize())]
    drills = frame["Drill"].dropna().astype(str).unique().tolist()
    for drill in sorted(drills, key=len, reverse=True):
        if _norm(drill) in text:
            return drill
    return "Full Training" if "Full Training" in drills else (drills[0] if drills else None)


def _convert_threshold(value: float, unit: str, metric: str) -> float:
    unit = unit.lower().replace(" ", "")
    meta = METRICS[metric]
    if meta.get("format") == "duration":
        if unit in {"h", "ora", "ore"}:
            return value * 3600
        if unit in {"s", "sec", "secondo", "secondi"}:
            return value
        return value * 60
    if meta.get("unit") == "m" and unit in {"km", "chilometro", "chilometri"}:
        return value * 1000
    if meta.get("unit") == "min" and unit in {"h", "ora", "ore"}:
        return value * 60
    return value


def _find_threshold(text: str, metric: str | None) -> tuple[str | None, float | None, str | None]:
    if metric is None:
        return None, None, None
    number = r"(\d+(?:[.,]\d+)?)"
    unit = r"\s*(%|percento|percentuale|km/h|kmh|km|m|minuti|minuto|min|ore|ora|h|secondi|secondo|sec|s|eventi|accelerazioni|decelerazioni)?"
    patterns = [
        # Le forme negative devono precedere quelle positive per evitare che
        # "non ha raggiunto" venga intercettato come "ha raggiunto".
        (rf"(?:non ha raggiunto|non hanno raggiunto|non ha superato|non hanno superato|sotto|inferiore a|meno di)\s*(?:i|il|la|le|lo|l['’])?\s*{number}{unit}", "<"),
        (rf"(?:al massimo|pari o inferiore a|<=)\s*(?:i|il|la|le|lo|l['’])?\s*{number}{unit}", "<="),
        (rf"(?:almeno|raggiunt[oa]|raggiunti|raggiunte|ha raggiunto|hanno raggiunto|pari o superiore a|>=)\s*(?:i|il|la|le|lo|l['’])?\s*{number}{unit}", ">="),
        (rf"(?:superat[oa]|superati|superate|ha superato|hanno superato|sopra|maggiore di|piu di|oltre)\s*(?:i|il|la|le|lo|l['’])?\s*{number}{unit}", ">"),
    ]
    for pattern, operator in patterns:
        match = re.search(pattern, text)
        if match:
            raw = float(match.group(1).replace(",", "."))
            unit_value = (match.group(2) or "").strip()
            return operator, _convert_threshold(raw, unit_value, metric), f"{raw:g}{(' ' + unit_value) if unit_value else ''}"
    return None, None, None


def parse_request(query: str, data: pd.DataFrame) -> AssistantRequest:
    text = _norm(query)
    metric = _find_metric(text)
    if (
        metric is None
        and re.search(r"(?<!\w)km(?![/\w])", text)
        and not any(term in text for term in ("velocita", "speed", "km/h", "kmh"))
    ):
        metric = "Distance (m)"
    date = _find_date(query, text, data)
    top = re.search(r"\b(?:top|primi|migliori)\s*(\d+)\b", text)
    bottom = re.search(r"\b(?:bottom|peggiori)\s*(\d+)\b", text)
    if bottom is None:
        bottom = re.search(r"\bultimi\s*(\d+)\s*(?:giocatori|atleti|valori|posti)\b", text)
    composite_n = re.search(r"\b(\d+)\s+giocatori\b", text) if any(term in text for term in ("carico maggiore", "maggior carico", "maggiore carico", "carico piu alto", "carico complessivo", "carico totale", "carico piu elevato")) else None
    period_start, period_end = _find_period_range(text, data)
    operator, threshold, source = _find_threshold(text, metric)
    max_speed_percent = ("max speed" in text or "velocita massima" in text or "massima velocita" in text) and ("%" in query or "percentuale" in text or "percento" in text)
    if max_speed_percent:
        # La soglia è sempre espressa su scala percentuale 0-100.
        operator, threshold, source = _find_threshold(text, "Max Speed (km/h)")
        pct_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|percento|percentuale)", query.lower())
        if pct_match:
            threshold = float(pct_match.group(1).replace(",", "."))
            source = f"{threshold:g}%"
            if any(term in text for term in (
                "non ha raggiunto", "non hanno raggiunto",
                "non ha superato", "non hanno superato",
                "sotto", "meno di", "inferiore a",
            )):
                operator = "<"
            elif any(term in text for term in ("al massimo", "pari o inferiore", "<=")):
                operator = "<="
            elif any(term in text for term in (
                "almeno", "ha raggiunto", "hanno raggiunto",
                "raggiunto", "raggiunti", "raggiunte",
                "pari o superiore", ">=",
            )):
                operator = ">="
            else:
                operator = ">"
    session_overview = any(term in text for term in (
        "cosa possiamo dire della seduta", "cosa dire della seduta",
        "analizza la seduta", "analisi della seduta", "com e stata la seduta",
        "com e andata la seduta", "riepilogo della seduta", "overview della seduta",
        "panoramica della seduta", "seduta di oggi"
    )) and not any(term in text for term in ("chi ha", "quanti", "top ", "sopra", "sotto", "superato", "raggiunto"))
    composite_load = session_overview or any(term in text for term in (
        "carico maggiore", "maggior carico", "maggiore carico", "carico piu alto",
        "carico complessivo", "carico totale", "carico piu elevato",
        "pas load index", " pli ", "modello gara", "modello prestativo"
    ))
    return AssistantRequest(
        query=query.strip(),
        players=_find_players(text, data),
        roles=_find_role_aliases(text, data),
        metric=metric,
        date=date,
        operator=operator,
        threshold=threshold,
        threshold_source=source,
        top_n=int(top.group(1)) if top else (int(composite_n.group(1)) if composite_n else None),
        bottom_n=int(bottom.group(1)) if bottom else None,
        drill=_find_drill(text, data, date),
        compare_history=any(term in text for term in ("storico", "media storica", "suo storico", "andamento")),
        compare_team=any(term in text for term in ("media squadra", "media della squadra", "con la squadra")),
        compare_role=any(term in text for term in ("media ruolo", "media del ruolo", "con il ruolo")),
        starter_statuses=_find_starter_statuses(text),
        max_speed_percent=max_speed_percent,
        composite_load=composite_load,
        session_overview=session_overview,
        cycles=_find_cycles(text, data),
        period_start=period_start,
        period_end=period_end,
    )


def _metric_value_frame(data: pd.DataFrame, request: AssistantRequest) -> pd.DataFrame:
    if request.metric is None:
        return pd.DataFrame(columns=["Athlete", "value"])
    frame = data.copy()
    if request.cycles and "Cycle" in frame.columns:
        frame = frame[frame["Cycle"].astype(str).isin(request.cycles)]
    if request.period_start is not None and request.period_end is not None:
        dates = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        frame = frame[dates.between(request.period_start.normalize(), request.period_end.normalize())]
    if request.date is not None:
        frame = frame[pd.to_datetime(frame["Date"], errors="coerce").dt.normalize().eq(request.date.normalize())]
    if request.drill:
        frame = frame[frame["Drill"].eq(request.drill)]
    role_column = _role_column(frame)
    if request.roles and role_column:
        frame = frame[frame[role_column].astype(str).isin(request.roles)]
    if request.starter_statuses and "Starters / No Starters" in frame.columns:
        frame = frame[frame["Starters / No Starters"].astype(str).str.upper().isin(request.starter_statuses)]
    if request.players:
        frame = frame[frame["Athlete"].isin(request.players)]
    meta = METRICS[request.metric]
    column = meta["column"]
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=["Athlete", "value"])
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    result = frame.groupby("Athlete", as_index=False).agg(value=(column, meta.get("aggregation", "sum")))
    result = result.dropna(subset=["value"])
    if request.max_speed_percent and request.metric == "Max Speed (km/h)" and not result.empty:
        result["absolute_value"] = result["value"]
        historical = data[["Athlete", column]].copy()
        historical[column] = pd.to_numeric(historical[column], errors="coerce")
        historical = historical.groupby("Athlete", as_index=False)[column].max().rename(columns={column: "historical_max"})
        result = result.merge(historical, on="Athlete", how="left")
        result["value"] = result["value"] / result["historical_max"] * 100.0
        result = result.drop(columns=["historical_max"]).dropna(subset=["value"])
    return result


def _format_value(value: float, metric: str, percent_mode: bool = False) -> str:
    if percent_mode:
        return f"{value:.1f}%".replace(".", ",")
    meta = METRICS[metric]
    decimals = int(meta.get("decimals", 0))
    if meta.get("format") == "duration":
        seconds = max(0, int(round(value)))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"
    return f"{value:,.{decimals}f} {meta.get('unit', '')}".replace(",", "X").replace(".", ",").replace("X", ".").strip()


def _metric_display_name(request: AssistantRequest) -> str:
    if request.max_speed_percent:
        return "% Max Speed individuale"
    return request.metric or ""


def _analysis_header(request: AssistantRequest) -> str:
    parts: list[str] = []
    if request.date is not None:
        parts.append(request.date.strftime("%d/%m/%Y"))
    if request.drill:
        parts.append(request.drill)
    if request.metric:
        parts.append(_metric_display_name(request))
    return " · ".join(parts)


def _comparison_analysis(data: pd.DataFrame, request: AssistantRequest) -> None:
    assert request.metric is not None
    result = _metric_value_frame(data, request).sort_values("value", ascending=False)
    if result.empty:
        st.warning("Non sono disponibili dati per il confronto richiesto.")
        return
    team_request = AssistantRequest(**{**request.__dict__, "players": []})
    team_values = _metric_value_frame(data, team_request)
    team_mean = float(team_values["value"].mean()) if not team_values.empty else float("nan")
    best = result.iloc[0]
    sentences = [
        f"Ho confrontato **{', '.join(result['Athlete'].astype(str))}** per **{request.metric}**.",
        f"Il valore più alto è di **{best['Athlete']}** con **{_format_value(float(best['value']), request.metric)}**.",
    ]
    if len(result) >= 2:
        second = result.iloc[1]
        difference = float(best["value"] - second["value"])
        pct = difference / float(second["value"]) * 100 if float(second["value"]) else 0.0
        sentences.append(
            f"La differenza rispetto a **{second['Athlete']}** è **{_format_value(difference, request.metric)}** ({pct:+.1f}%)."
        )
    if pd.notna(team_mean):
        sentences.append(f"La media della squadra nella stessa vista è **{_format_value(team_mean, request.metric)}**.")
    st.markdown(" ".join(sentences))
    fig = go.Figure(go.Bar(
        x=result["Athlete"], y=result["value"],
        marker_color=METRICS[request.metric]["color"],
        text=[_format_value(float(v), request.metric) for v in result["value"]],
        textposition="outside",
        hovertemplate="%{x}<br>%{y}<extra></extra>",
    ))
    if pd.notna(team_mean):
        fig.add_hline(y=team_mean, line_dash="dash", annotation_text="Media squadra")
    fig.update_layout(title=f"Confronto — {request.metric}", xaxis_title="", yaxis_title=METRICS[request.metric].get("unit", ""), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(result.rename(columns={"Athlete": "Giocatore", "value": request.metric}), use_container_width=True, hide_index=True)


def _history_analysis(data: pd.DataFrame, request: AssistantRequest) -> None:
    assert request.metric is not None
    player = request.players[0]
    meta = METRICS[request.metric]
    column = meta["column"]
    frame = data[data["Athlete"].eq(player)].copy()
    if request.drill:
        frame = frame[frame["Drill"].eq(request.drill)]
    if frame.empty or column not in frame.columns:
        st.warning("Non sono disponibili dati storici per la richiesta.")
        return
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["Session Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
    history = frame.groupby("Session Date", as_index=False).agg(
        value=(column, meta.get("aggregation", "sum"))
    ).rename(columns={"Session Date": "Date"}).dropna(subset=["Date", "value"]).sort_values("Date")
    if history.empty:
        st.warning("Non sono disponibili dati storici per la richiesta.")
        return
    target_date = request.date.normalize() if request.date is not None else pd.Timestamp(history["Date"].max()).normalize()
    current_rows = history[pd.to_datetime(history["Date"]).dt.normalize().eq(target_date)]
    if current_rows.empty:
        current_rows = history.tail(1)
        target_date = pd.Timestamp(current_rows.iloc[0]["Date"]).normalize()
    current = float(current_rows.iloc[0]["value"])
    previous = history[pd.to_datetime(history["Date"]).dt.normalize().lt(target_date)]
    historical_mean = float(previous["value"].mean()) if not previous.empty else float("nan")
    historical_max = float(previous["value"].max()) if not previous.empty else float("nan")
    historical_min = float(previous["value"].min()) if not previous.empty else float("nan")
    if pd.notna(historical_mean) and historical_mean:
        delta_pct = (current - historical_mean) / historical_mean * 100
        direction = "superiore" if delta_pct >= 0 else "inferiore"
        text = (
            f"Nella seduta del **{target_date.strftime('%d/%m/%Y')}**, **{player}** ha registrato "
            f"**{_format_value(current, request.metric)}** in **{request.metric}**. "
            f"Il valore è **{direction} del {abs(delta_pct):.1f}%** rispetto alla sua media storica "
            f"di **{_format_value(historical_mean, request.metric)}**."
        )
        if pd.notna(historical_max):
            text += f" Nello storico precedente il range va da **{_format_value(historical_min, request.metric)}** a **{_format_value(historical_max, request.metric)}**."
    else:
        text = f"Per **{player}** la seduta mostra **{_format_value(current, request.metric)}** in **{request.metric}**; non ci sono abbastanza sedute precedenti per un confronto affidabile."
    st.markdown(text)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history["Date"], y=history["value"], mode="lines+markers", name=player,
        line=dict(color=METRICS[request.metric]["color"]),
        hovertemplate="%{x|%d/%m/%Y}<br>%{y}<extra></extra>",
    ))
    if pd.notna(historical_mean):
        fig.add_hline(y=historical_mean, line_dash="dash", annotation_text="Media storica")
    fig.add_trace(go.Scatter(
        x=[target_date], y=[current], mode="markers", name="Seduta richiesta",
        marker=dict(size=14, symbol="diamond", color=METRICS[request.metric]["color"], line=dict(width=2, color="white")),
        hovertemplate="Seduta richiesta<br>%{x|%d/%m/%Y}<br>%{y}<extra></extra>",
    ))
    fig.update_layout(title=f"Storico di {player} — {request.metric}", xaxis_title="Data", yaxis_title=meta.get("unit", ""))
    st.plotly_chart(fig, use_container_width=True)


def _ranking_analysis(data: pd.DataFrame, request: AssistantRequest) -> None:
    assert request.metric is not None
    result = _metric_value_frame(data, request)
    if result.empty:
        st.warning("Non sono disponibili dati per la richiesta.")
        return
    if request.operator and request.threshold is not None:
        masks = {
            ">": result["value"] > request.threshold,
            ">=": result["value"] >= request.threshold,
            "<": result["value"] < request.threshold,
            "<=": result["value"] <= request.threshold,
        }
        result = result[masks[request.operator]]
    ascending = request.bottom_n is not None or request.operator in {"<", "<="}
    result = result.sort_values("value", ascending=ascending)
    limit = request.top_n or request.bottom_n
    if limit:
        result = result.head(limit)
    if result.empty:
        st.info("Nessun giocatore soddisfa la condizione richiesta.")
        return
    if request.operator and request.threshold is not None:
        condition = f"{request.operator} {_format_value(request.threshold, request.metric, request.max_speed_percent)}"
        intro = f"**{len(result)} giocatori** soddisfano la condizione **{request.metric} {condition}**."
    elif request.bottom_n:
        intro = f"Ecco gli ultimi **{len(result)} giocatori** per **{request.metric}**."
    else:
        intro = f"Ecco i primi **{len(result)} giocatori** per **{request.metric}**."
    leader = result.iloc[0]
    st.markdown(f"{intro} Il primo valore visualizzato è **{leader['Athlete']}** con **{_format_value(float(leader['value']), request.metric)}**.")
    fig = go.Figure(go.Bar(
        x=result["value"], y=result["Athlete"], orientation="h",
        marker_color=METRICS[request.metric]["color"],
        text=[_format_value(float(v), request.metric) for v in result["value"]],
        textposition="outside",
        hovertemplate="%{y}<br>%{x}<extra></extra>",
    ))
    fig.update_layout(title=f"Risultato — {request.metric}", xaxis_title=METRICS[request.metric].get("unit", ""), yaxis_title="", yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(result.rename(columns={"Athlete": "Giocatore", "value": request.metric}), use_container_width=True, hide_index=True)


def _multi_metric_summary(data: pd.DataFrame, request: AssistantRequest) -> None:
    if not request.players:
        st.info("Indica almeno un giocatore oppure una metrica nella richiesta.")
        return
    metrics = ["Distance (m)", "Distance 19.8-25.2 km/h (m)", "Distance >25.2 km/h (m)", "Acc Events (n°)", "Dec Events (n°)", "Max Speed (km/h)"]
    rows: list[dict[str, object]] = []
    for metric in metrics:
        metric_request = AssistantRequest(**{**request.__dict__, "metric": metric})
        values = _metric_value_frame(data, metric_request)
        for _, row in values.iterrows():
            rows.append({"Giocatore": row["Athlete"], "Metrica": metric, "Valore": _format_value(float(row["value"]), metric)})
    if not rows:
        st.warning("Non sono disponibili dati per il riepilogo richiesto.")
        return
    st.markdown(f"Ho preparato il riepilogo della seduta per **{', '.join(request.players)}** sulle principali metriche GPS.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)



def _daily_metric_analysis(data: pd.DataFrame, request: AssistantRequest) -> None:
    """Produce un'analisi descrittiva oggettiva della metrica nella seduta."""
    assert request.metric is not None
    result = _metric_value_frame(data, request).sort_values("value", ascending=False)
    if result.empty:
        st.warning("Non sono disponibili dati per la metrica e la giornata selezionate.")
        return

    values = result["value"].astype(float)
    mean_value = float(values.mean())
    median_value = float(values.median())
    maximum = result.iloc[0]
    minimum = result.iloc[-1]
    above = result[result["value"] > mean_value]
    below = result[result["value"] < mean_value]

    date_text = request.date.strftime("%d/%m/%Y") if request.date is not None else "giornata selezionata"
    drill_text = f" nel drill **{request.drill}**" if request.drill else ""
    st.markdown(
        f"Nella seduta del **{date_text}**{drill_text}, la metrica **{request.metric}** "
        f"ha una media di **{_format_value(mean_value, request.metric)}** e una mediana di "
        f"**{_format_value(median_value, request.metric)}**. "
        f"Il valore più alto è di **{maximum['Athlete']}** con "
        f"**{_format_value(float(maximum['value']), request.metric)}**, mentre il più basso è di "
        f"**{minimum['Athlete']}** con **{_format_value(float(minimum['value']), request.metric)}**. "
        f"Sono **{len(above)}** i giocatori sopra la media e **{len(below)}** quelli sotto la media."
    )

    fig = go.Figure(go.Bar(
        x=result["value"],
        y=result["Athlete"],
        orientation="h",
        marker_color=METRICS[request.metric]["color"],
        text=[_format_value(float(v), request.metric) for v in result["value"]],
        textposition="outside",
        hovertemplate="%{y}<br>%{x}<extra></extra>",
    ))
    fig.add_vline(x=mean_value, line_dash="dash", annotation_text="Media squadra")
    fig.update_layout(
        title=f"Analisi della giornata — {request.metric}",
        xaxis_title=METRICS[request.metric].get("unit", ""),
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
    display = result.rename(columns={"Athlete": "Giocatore", "value": request.metric}).copy()
    display["Rispetto alla media"] = [
        "Sopra" if float(value) > mean_value else "Sotto" if float(value) < mean_value else "In media"
        for value in result["value"]
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)

def _render_analysis(data: pd.DataFrame, request: AssistantRequest) -> None:
    st.markdown("### PAS Analysis")
    header = _analysis_header(request)
    if header:
        st.caption(header)
    if request.compare_history:
        if not request.players:
            st.warning("Per il confronto con lo storico indica il giocatore.")
            return
        if request.metric is None:
            st.warning("Per il confronto con lo storico indica anche la metrica.")
            return
        _history_analysis(data, request)
        return
    if request.metric is None:
        _multi_metric_summary(data, request)
        return
    if len(request.players) >= 2:
        _comparison_analysis(data, request)
        return
    if request.operator or request.top_n or request.bottom_n or not request.players:
        _ranking_analysis(data, request)
        return
    _comparison_analysis(data, request)



def _percentile_rank(values: pd.Series, value: float) -> float:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return float("nan")
    return float((numeric <= value).mean() * 100)


def _contextual_key_insights(data: pd.DataFrame, request: AssistantRequest) -> list[str]:
    """Genera insight contestuali esclusivamente descrittivi e verificabili."""
    if request.composite_load:
        details, used_metrics = _composite_load_details(data, request)
        ranking = details.sort_values("value", ascending=False).reset_index(drop=True)
        if ranking.empty:
            return []
        limit = request.top_n or (5 if request.session_overview else 1)
        selected = ranking.head(limit)
        highest = ranking.iloc[0]
        lowest = ranking.iloc[-1]
        mean_index = float(ranking["value"].mean())
        median_index = float(ranking["value"].median())
        std_index = float(ranking["value"].std(ddof=0)) if len(ranking) > 1 else 0.0
        cv_index = (std_index / mean_index * 100) if mean_index else 0.0
        insights = [
            f"**Carico complessivo maggiore:** **{highest['Athlete']}** con PLI **{float(highest['value']):.1f}%** del modello gara.",
            f"**Carico complessivo minore:** **{lowest['Athlete']}** con PLI **{float(lowest['value']):.1f}%** del modello gara.",
            f"PLI medio squadra **{mean_index:.1f}%**, mediana **{median_index:.1f}%** del modello gara; variabilità relativa **{cv_index:.1f}%**.",
        ]
        if _wants_starter_comparison(request):
            group_means: dict[str, float] = {}
            for status in ("S", "NS"):
                status_request = AssistantRequest(**{**request.__dict__, "starter_statuses": [status]})
                status_details, _ = _composite_load_details(data, status_request)
                if not status_details.empty:
                    group_means[status] = float(status_details["value"].mean())
            if group_means:
                parts = [f"{_status_label(status)} **{value:.1f}%**" for status, value in group_means.items()]
                insights.append("**Media del carico per gruppo:** " + " · ".join(parts) + ".")
        if len(selected) > 1:
            insights.append(f"**Carico maggiore — Top {len(selected)}:** **{', '.join(selected['Athlete'].astype(str))}**.")
        for component in used_metrics:
            component_values = details[["Athlete", component]].dropna().sort_values(component, ascending=False).reset_index(drop=True)
            if component_values.empty:
                continue
            numeric = pd.to_numeric(component_values[component], errors="coerce").dropna()
            maximum = component_values.iloc[0]
            minimum = component_values.iloc[-1]
            mean_value = float(numeric.mean())
            median_value = float(numeric.median())
            std_value = float(numeric.std(ddof=0)) if len(numeric) > 1 else 0.0
            cv_value = (std_value / mean_value * 100) if mean_value else 0.0
            insights.append(
                f"**{component}** — valore maggiore **{maximum['Athlete']}** "
                f"(**{float(maximum[component]):.1f}%** del modello gara); valore minore **{minimum['Athlete']}** "
                f"(**{float(minimum[component]):.1f}%**); media **{mean_value:.1f}%**, "
                f"mediana **{median_value:.1f}%**, dispersione relativa **{cv_value:.1f}%**."
            )
        insights.append(
            "Il PAS Load Index è la media delle sei componenti disponibili, con peso uguale: "
            "Volume, Alta velocità, Sprint, Componente neuromuscolare, Velocità massima e Carico interno. "
            "Ogni componente è espressa come percentuale del modello gara individuale; Duration usa 90 minuti e RPE usa il riferimento 8."
        )
        return insights
    if request.metric is None:
        if request.players:
            return [
                f"La vista è focalizzata su **{len(request.players)} giocatore/i**: "
                + ", ".join(request.players) + ".",
                "Le card e i grafici sottostanti mantengono le metriche originali della Dashboard.",
            ]
        return []

    values = _metric_value_frame(data, request)
    if values.empty:
        return []
    values = values.sort_values("value", ascending=False).reset_index(drop=True)
    mean_value = float(values["value"].mean())
    median_value = float(values["value"].median())
    maximum = values.iloc[0]
    minimum = values.iloc[-1]
    insights: list[str] = []

    if _wants_starter_comparison(request):
        group_parts: list[str] = []
        for status in ("S", "NS"):
            status_values = _status_metric_values(data, request, status)
            if not status_values.empty:
                group_parts.append(
                    f"{_status_label(status)} media **{_format_value(float(status_values['value'].mean()), request.metric, request.max_speed_percent)}**"
                )
        if group_parts:
            insights.append("**Confronto S/NS:** " + " · ".join(group_parts) + ".")

    if request.compare_history and request.players:
        player = request.players[0]
        meta = METRICS[request.metric]
        column = meta["column"]
        frame = data[data["Athlete"].eq(player)].copy()
        if request.drill:
            frame = frame[frame["Drill"].eq(request.drill)]
        if column in frame.columns and not frame.empty:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
            frame["Session Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
            history = frame.groupby("Session Date", as_index=False).agg(
                value=(column, meta.get("aggregation", "sum"))
            ).dropna(subset=["Session Date", "value"]).sort_values("Session Date")
            if not history.empty:
                target = request.date.normalize() if request.date is not None else pd.Timestamp(history["Session Date"].max()).normalize()
                current_rows = history[history["Session Date"].eq(target)]
                if current_rows.empty:
                    current_rows = history.tail(1)
                    target = pd.Timestamp(current_rows.iloc[0]["Session Date"]).normalize()
                current = float(current_rows.iloc[0]["value"])
                previous = history[history["Session Date"].lt(target)]
                if not previous.empty:
                    historical_mean = float(previous["value"].mean())
                    delta_pct = ((current - historical_mean) / historical_mean * 100) if historical_mean else 0.0
                    insights.append(
                        f"**{player}** è {abs(delta_pct):.1f}% {'sopra' if delta_pct >= 0 else 'sotto'} la propria media storica "
                        f"di **{_format_value(historical_mean, request.metric)}**."
                    )
                    rank = int((previous["value"] > current).sum()) + 1
                    total = len(previous) + 1
                    insights.append(f"La seduta richiesta è la **{rank}ª prestazione su {total}** nello storico disponibile.")
                    percentile = _percentile_rank(previous["value"], current)
                    insights.append(f"Il valore è superiore al **{percentile:.0f}%** delle sedute precedenti.")
                else:
                    insights.append("Non sono presenti sedute precedenti sufficienti per un confronto storico.")
        return insights[:4]

    if request.operator and request.threshold is not None:
        masks = {
            ">": values["value"] > request.threshold,
            ">=": values["value"] >= request.threshold,
            "<": values["value"] < request.threshold,
            "<=": values["value"] <= request.threshold,
        }
        matched = values[masks[request.operator]].copy()
        matched = matched.sort_values(
            "value", ascending=request.operator in {"<", "<="}
        )
        insights.append(
            f"**{len(matched)} su {len(values)} giocatori** soddisfano la soglia "
            f"**{request.operator} {_format_value(request.threshold, request.metric, request.max_speed_percent)}**."
        )
        if not matched.empty:
            names = matched["Athlete"].astype(str).tolist()
            visible_names = names[:8]
            names_text = ", ".join(visible_names)
            if len(names) > len(visible_names):
                names_text += f" + altri {len(names) - len(visible_names)}"
            insights.append(f"Giocatori nella condizione: **{names_text}**.")
            matched_mean = float(matched["value"].mean())
            insights.append(f"La media del gruppo filtrato è **{_format_value(matched_mean, request.metric, request.max_speed_percent)}**.")
            top = matched.iloc[0]
            insights.append(f"Il valore più rappresentativo della condizione è **{top['Athlete']}** con **{_format_value(float(top['value']), request.metric, request.max_speed_percent)}**.")
        return insights[:4]

    if request.top_n or request.bottom_n:
        ordered = values.sort_values("value", ascending=request.bottom_n is not None)
        limit = request.top_n or request.bottom_n or len(ordered)
        selected = ordered.head(limit)
        first = selected.iloc[0]
        insights.append(f"La selezione comprende **{len(selected)} giocatori** ordinati per **{_metric_display_name(request)}**.")
        insights.append(f"Il primo valore mostrato è **{first['Athlete']}** con **{_format_value(float(first['value']), request.metric, request.max_speed_percent)}**.")
        if len(selected) > 1:
            spread = float(selected["value"].max() - selected["value"].min())
            insights.append(f"L’intervallo tra i valori visualizzati è **{_format_value(spread, request.metric)}**.")
        return insights[:4]

    if len(request.players) >= 2:
        selected = values[values["Athlete"].isin(request.players)].sort_values("value", ascending=False)
        if not selected.empty:
            leader = selected.iloc[0]
            insights.append(f"Tra i giocatori richiesti, **{leader['Athlete']}** registra il valore più alto: **{_format_value(float(leader['value']), request.metric)}**.")
            if len(selected) >= 2:
                second = selected.iloc[1]
                diff = float(leader["value"] - second["value"])
                pct = diff / float(second["value"]) * 100 if float(second["value"]) else 0.0
                insights.append(f"Il vantaggio su **{second['Athlete']}** è **{_format_value(diff, request.metric)}** ({pct:.1f}%).")
            above = selected[selected["value"] > mean_value]["Athlete"].astype(str).tolist()
            if above:
                insights.append("Sopra la media della vista: **" + ", ".join(above) + "**.")
        return insights[:4]

    insights.append(f"Il leader della giornata è **{maximum['Athlete']}** con **{_format_value(float(maximum['value']), request.metric)}**.")
    insights.append(f"La media è **{_format_value(mean_value, request.metric)}** e la mediana **{_format_value(median_value, request.metric)}**.")
    above_count = int((values["value"] > mean_value).sum())
    insights.append(f"**{above_count} giocatori** sono sopra la media della vista.")
    spread = float(maximum["value"] - minimum["value"])
    insights.append(f"La distanza tra massimo e minimo è **{_format_value(spread, request.metric)}**.")
    return insights[:4]


def _render_contextual_key_insights(data: pd.DataFrame, request: AssistantRequest) -> None:
    insights = _contextual_key_insights(data, request)
    if not insights:
        return
    st.markdown("#### Key Insights")
    for insight in insights:
        st.markdown(f"- {insight}")

def _clear_legacy_controller_state() -> None:
    for key in (
        "pas_dashboard_controller_active",
        "pas_dashboard_controller_players",
        "pas_dashboard_controller_summary",
    ):
        st.session_state.pop(key, None)


def _matching_players(data: pd.DataFrame, request: AssistantRequest) -> list[str]:
    """Restituisce i giocatori coerenti con soglia, Top/Bottom e ruolo."""
    values = _metric_value_frame(data, request)
    if values.empty:
        return []
    if request.operator and request.threshold is not None:
        masks = {
            ">": values["value"] > request.threshold,
            ">=": values["value"] >= request.threshold,
            "<": values["value"] < request.threshold,
            "<=": values["value"] <= request.threshold,
        }
        values = values[masks[request.operator]]
    ascending = request.bottom_n is not None or request.operator in {"<", "<="}
    values = values.sort_values("value", ascending=ascending)
    limit = request.top_n or request.bottom_n
    if limit:
        values = values.head(limit)
    return values["Athlete"].dropna().astype(str).tolist()


def _dashboard_route(request: AssistantRequest, data: pd.DataFrame) -> tuple[bool, str]:
    """Mappa la richiesta sui widget originali della Dashboard."""
    metric = request.metric
    text = _norm(request.query)
    players = list(request.players)

    scoped = data.copy()
    if request.date is not None:
        scoped = scoped[pd.to_datetime(scoped["Date"], errors="coerce").dt.normalize().eq(request.date.normalize())]
    if request.drill:
        scoped = scoped[scoped["Drill"].eq(request.drill)]

    if request.roles:
        role_col = _role_column(scoped)
        if role_col:
            role_players = (
                scoped.loc[scoped[role_col].astype(str).isin(request.roles), "Athlete"]
                .dropna().astype(str).unique().tolist()
            )
            players = list(dict.fromkeys(players + sorted(role_players)))

    valid_players = set(scoped["Athlete"].dropna().astype(str).unique())
    players = [player for player in players if player in valid_players]

    if metric and (request.operator or request.top_n or request.bottom_n):
        matched = _matching_players(data, request)
        if not matched:
            return False, "Nessun giocatore soddisfa la condizione richiesta; la Dashboard non è stata modificata."
        players = matched

    # Data e drill pilotano i filtri standard.
    if request.date is not None:
        st.session_state["dashboard_reference_date"] = request.date.date()
    if request.drill:
        st.session_state["dashboard_selected_drill"] = request.drill

    # La metrica richiesta viene portata per prima nella panoramica e nei dettagli.
    if metric:
        st.session_state["dashboard_overview_metrics"] = [metric]
        st.session_state["dashboard_detail_metrics"] = [metric]

    # Storico/profilo individuale: usa la Player Overview originale con box storico.
    wants_player_overview = (
        request.compare_history
        or "panoramica" in text
        or "profilo" in text
        or "riepilogo" in text
        or "storico" in text
    ) and len(players) == 1

    if wants_player_overview:
        st.session_state["dashboard_overview_mode"] = "Player Overview"
        st.session_state["dashboard_overview_player"] = players[0]
        st.session_state["dashboard_selected_players"] = players
        st.session_state["dashboard_day_players_mode"] = "Solo giocatori selezionati"
        action = f"Player Overview di {players[0]}"
    else:
        st.session_state["dashboard_overview_mode"] = "Team Overview"
        if players:
            st.session_state["dashboard_selected_players"] = players
            st.session_state["dashboard_day_players_mode"] = "Solo giocatori selezionati"
            action = f"confronto di {len(players)} giocatori"
        else:
            st.session_state["dashboard_selected_players"] = []
            st.session_state["dashboard_day_players_mode"] = "Tutta la squadra"
            action = "panoramica squadra"

    details = [action]
    if metric:
        details.append(_metric_display_name(request))
    if request.operator and request.threshold is not None:
        details.append(f"filtro {request.operator} {_format_value(request.threshold, metric, request.max_speed_percent)}")
    if request.top_n:
        details.append(f"Top {request.top_n}")
    if request.bottom_n:
        details.append(f"Bottom {request.bottom_n}")
    if request.roles:
        details.append("ruolo: " + ", ".join(request.roles))
    if request.starter_statuses:
        details.append("gruppo: " + ", ".join(request.starter_statuses))
    if request.composite_load:
        details.append("PAS Load Index rispetto al modello gara")
    return True, " · ".join(details)


def _apply_dashboard_request(query: str, selected_metric: str, data: pd.DataFrame) -> None:
    request = parse_request(query, data)
    if request.metric is None:
        request.metric = selected_metric
        request.operator, request.threshold, request.threshold_source = _find_threshold(
            _norm(query), request.metric
        )
    routed, summary = _dashboard_route(request, data)
    st.session_state["pas_dashboard_route_summary"] = summary
    st.session_state["pas_dashboard_route_query"] = query
    st.session_state["pas_dashboard_route_success"] = routed
    if routed:
        st.session_state["pas_dashboard_route_request"] = request
    else:
        st.session_state.pop("pas_dashboard_route_request", None)



@dataclass
class IntelligenceRoute:
    target_page: str
    intent: str
    summary: str


def _infer_target_page(request: AssistantRequest, current_page: str) -> IntelligenceRoute:
    """Determina la sezione PAS più coerente con la richiesta."""
    text = _norm(request.query)
    if request.period_start is not None and request.period_end is not None:
        return IntelligenceRoute("📊 Period Load", "period_load", "Apertura di Period Load")
    for target, keywords in SECTION_KEYWORDS.items():
        if any(term in text for term in keywords):
            labels = {
                "🗓️ Planner": ("planner", "Apertura del Planner"),
                "🔮 Forecast": ("forecast", "Apertura del Forecast"),
                "⚽ Match Analysis": ("match", "Apertura di Match Analysis"),
                "🧩 Drills": ("drills", "Apertura di Drills Analysis"),
                "📊 Period Load": ("period_load", "Apertura di Period Load"),
                "🏥 Return To Play": ("rtp", "Apertura di Return To Play"),
            }
            intent, summary = labels[target]
            return IntelligenceRoute(target, intent, summary)
    return IntelligenceRoute("🏠 Dashboard", "dashboard", "Apertura della Dashboard")


def _apply_section_route(request: AssistantRequest, data: pd.DataFrame, current_page: str) -> tuple[bool, str, str]:
    route = _infer_target_page(request, current_page)
    target = route.target_page
    text = _norm(request.query)

    if target == "🏠 Dashboard":
        routed, summary = _dashboard_route(request, data)
        return routed, target, summary

    if target == "🧩 Drills":
        if request.players:
            st.session_state["drills_analysis_mode"] = "Players"
            st.session_state["drills_player_mode"] = "Selected players"
            st.session_state["drills_players"] = request.players
        elif request.roles:
            st.session_state["drills_analysis_mode"] = "Roles"
            st.session_state["drills_roles"] = request.roles
        available_drills = sorted(data.loc[~data["Drill"].isin(["Full Training", "Different Training"]), "Drill"].dropna().astype(str).unique())
        named = [d for d in available_drills if _norm(d) in text]
        if named:
            st.session_state["drills_selected"] = named
        if request.cycles:
            st.session_state["drills_intelligence_cycles"] = request.cycles
        else:
            st.session_state.pop("drills_intelligence_cycles", None)
        st.session_state["drills_intelligence_request"] = request
        if request.metric:
            drill_metric_map = {
                "Relative Distance (m/min)": "Relative Distance (m/min)",
                "Acc Events (n°)": "Acc Events (n°/min)",
                "Dec Events (n°)": "Dec Events (n°/min)",
                "Distance 19.8-25.2 km/h (m)": "19.8-25.2 km/h (m/min)",
                "Distance >25.2 km/h (m)": ">25.2 km/h (m/min)",
                "Speed Events (n°)": "Speed Events (n°/min)",
            }
            mapped_metric = drill_metric_map.get(request.metric)
            if mapped_metric:
                st.session_state["drills_metrics"] = [mapped_metric]
        details = [route.summary]
        if request.players: details.append("giocatori: " + ", ".join(request.players))
        if request.roles: details.append("ruoli: " + ", ".join(request.roles))
        if named: details.append("drill: " + ", ".join(named))
        if request.cycles: details.append("cicli: " + ", ".join(request.cycles))
        if request.metric: details.append(request.metric)
        return True, target, " · ".join(details)

    if target == "📊 Period Load":
        cycles: list[str] = []
        if request.period_start is not None and request.period_end is not None:
            st.session_state["period_totals_mode"] = "Intervallo di date"
            st.session_state["period_totals_dates"] = (
                request.period_start.date(),
                request.period_end.date(),
            )
        else:
            cycles = request.cycles or _cycle_order(data)[-1:]
            if cycles:
                st.session_state["period_totals_mode"] = "Uno o più Match Cycle"
                st.session_state["period_totals_cycles"] = cycles
        if request.players:
            st.session_state["period_totals_players"] = request.players
        if request.metric:
            st.session_state["period_totals_metrics"] = [request.metric]
        st.session_state["period_intelligence_request"] = request
        details = [route.summary]
        if request.period_start is not None and request.period_end is not None:
            details.append(f"periodo: {request.period_start.strftime('%d/%m/%Y')} → {request.period_end.strftime('%d/%m/%Y')}")
        if cycles: details.append("cicli: " + ", ".join(cycles))
        if request.players: details.append("giocatori: " + ", ".join(request.players))
        if request.roles: details.append("ruoli: " + ", ".join(request.roles))
        if request.starter_statuses: details.append("gruppo: " + ", ".join(request.starter_statuses))
        if request.metric: details.append(request.metric)
        return True, target, " · ".join(details)

    if target == "⚽ Match Analysis":
        if request.metric:
            st.session_state["comparison_metrics"] = [request.metric]
        if len(request.players) == 1:
            st.session_state["comparison_subject"] = request.players[0]
        return True, target, route.summary + (f" · {request.metric}" if request.metric else "")

    return True, target, route.summary


def _inherit_context(request: AssistantRequest) -> AssistantRequest:
    previous = st.session_state.get("pas_intelligence_request")
    if not isinstance(previous, AssistantRequest):
        return request
    text = _norm(request.query)
    is_follow_up = text.startswith(FOLLOW_UP_PREFIXES) or len(text.split()) <= 4
    if not is_follow_up:
        return request
    if not request.players:
        request.players = list(previous.players)
    if not request.roles:
        request.roles = list(previous.roles)
    if not request.starter_statuses:
        request.starter_statuses = list(previous.starter_statuses)
    if not request.max_speed_percent:
        request.max_speed_percent = previous.max_speed_percent
    if not request.composite_load:
        request.composite_load = previous.composite_load
    if not request.cycles:
        request.cycles = list(previous.cycles)
    if request.period_start is None and request.period_end is None and previous.period_start is not None and previous.period_end is not None:
        request.period_start = previous.period_start
        request.period_end = previous.period_end
    if request.metric is None:
        request.metric = previous.metric
    if request.drill is None:
        request.drill = previous.drill
    if request.date is None:
        request.date = previous.date
    return request


def _request_confidence(request: AssistantRequest, target_page: str) -> int:
    score = 55
    if request.metric: score += 15
    if request.players or request.roles or request.starter_statuses: score += 10
    if request.drill: score += 8
    if request.period_start is not None and request.period_end is not None: score += 8
    if request.operator or request.top_n or request.bottom_n or request.compare_history or request.composite_load: score += 7
    if target_page != "🏠 Dashboard": score += 5
    return min(score, 99)


def _apply_intelligence_request(query: str, selected_metric: str, data: pd.DataFrame, current_page: str) -> None:
    request = _inherit_context(parse_request(query, data))
    preliminary_target = _infer_target_page(request, current_page).target_page
    if preliminary_target == "📊 Period Load" or request.cycles:
        request.date = None
        request.drill = None
    elif preliminary_target == "🧩 Drills":
        # In Drills non forzare Full Training quando non è stato nominato un esercizio.
        available = sorted(data.loc[~data["Drill"].isin(["Full Training", "Different Training"]), "Drill"].dropna().astype(str).unique())
        if request.drill not in available:
            request.drill = None
    if request.max_speed_percent:
        request.metric = "Max Speed (km/h)"
        request.operator, request.threshold, request.threshold_source = _find_threshold(_norm(query), request.metric)
    elif request.metric is None and not request.composite_load:
        request.metric = selected_metric
        request.operator, request.threshold, request.threshold_source = _find_threshold(_norm(query), request.metric)
    routed, target_page, summary = _apply_section_route(request, data, current_page)
    st.session_state["pas_intelligence_summary"] = summary
    st.session_state["pas_intelligence_query"] = query
    st.session_state["pas_intelligence_success"] = routed
    st.session_state["pas_intelligence_target"] = target_page
    st.session_state["pas_intelligence_request"] = request if routed else None
    st.session_state["pas_intelligence_confidence"] = _request_confidence(request, target_page)
    if routed and target_page != current_page:
        st.session_state["pas_pending_navigation"] = target_page


def _reset_dashboard_route() -> None:
    for key in (
        "pas_dashboard_route_summary",
        "pas_dashboard_route_query",
        "pas_dashboard_route_success",
        "pas_dashboard_route_request",
        "pas_conversational_request",
        "pas_conversational_analysis_mode",
        "pas_conversational_selected_metric",
        "pas_conversational_query",
    ):
        st.session_state.pop(key, None)


def _request_filtered_frame(data: pd.DataFrame, request: AssistantRequest) -> pd.DataFrame:
    """Applica alla sorgente i filtri semantici della richiesta, senza alterare i widget."""
    frame = data.copy()
    if request.cycles and "Cycle" in frame.columns:
        frame = frame[frame["Cycle"].astype(str).isin(request.cycles)]
    if request.period_start is not None and request.period_end is not None:
        dates = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        frame = frame[dates.between(request.period_start.normalize(), request.period_end.normalize())]
    if request.date is not None:
        dates = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        frame = frame[dates.eq(request.date.normalize())]
    if request.drill:
        frame = frame[frame["Drill"].astype(str).eq(request.drill)]
    role_column = _role_column(frame)
    if request.roles and role_column:
        frame = frame[frame[role_column].astype(str).isin(request.roles)]
    if request.starter_statuses and "Starters / No Starters" in frame.columns:
        frame = frame[frame["Starters / No Starters"].astype(str).str.upper().isin(request.starter_statuses)]
    if request.players:
        frame = frame[frame["Athlete"].isin(request.players)]
    return frame


def _composite_load_details(data: pd.DataFrame, request: AssistantRequest) -> tuple[pd.DataFrame, list[str]]:
    """Restituisce il PAS Load Index e le sei componenti individuali."""
    current = _request_filtered_frame(data, request)
    pli = calculate_pli(current, reference_source=data)
    if pli.player_scores.empty:
        return pd.DataFrame(columns=["Athlete", "value"]), []
    details = pli.player_scores.rename(columns={"PLI": "value"}).copy()
    component_wide = pli.component_long.pivot(index="Athlete", columns="Component", values="Percent").reset_index()
    component_wide.columns.name = None
    details = details.merge(component_wide, on="Athlete", how="left")
    for field in ("Value", "Reference", "Percent"):
        metric_wide = pli.metric_long.pivot(index="Athlete", columns="Metric", values=field).reset_index()
        metric_wide.columns.name = None
        metric_wide = metric_wide.rename(
            columns={metric: f"metric::{field.lower()}::{metric}" for metric in metric_wide.columns if metric != "Athlete"}
        )
        details = details.merge(metric_wide, on="Athlete", how="left")
    for component in PLI_COMPONENTS:
        details[f"component::{component}"] = details.get(component)
    return details, list(PLI_COMPONENTS.keys())



def _pli_metric_value_label(metric: str, value: float) -> str:
    if pd.isna(value):
        return "N/D"
    if metric in {"Distance (m)", "Distance 19.8-25.2 km/h (m)", "Distance >25.2 km/h (m)"}:
        return f"{float(value):.0f} m"
    if metric == "Duration (min)":
        return f"{float(value):.0f} min"
    if metric == "Max Speed (km/h)":
        return f"{float(value):.1f} km/h"
    if metric == "% Max Speed individuale":
        return f"{float(value):.1f}%"
    if metric == "RPE":
        return f"{float(value):.1f}"
    return f"{float(value):.0f}"


def _pli_component_detail(row: pd.Series, component: str, include_reference: bool = False) -> str:
    parts: list[str] = []
    for metric in PLI_COMPONENTS.get(component, ()): 
        value = pd.to_numeric(pd.Series([row.get(f"metric::value::{metric}")]), errors="coerce").iloc[0]
        if pd.isna(value):
            continue
        label = metric.replace("Distance 19.8-25.2 km/h (m)", "19.8–25.2").replace("Distance >25.2 km/h (m)", ">25.2").replace("Speed Events (n°)", "Speed Events").replace("Acc Events (n°)", "Acc").replace("Dec Events (n°)", "Dec").replace("Duration (min)", "Durata").replace("Distance (m)", "Distance")
        item = f"{label}: {_pli_metric_value_label(metric, value)}"
        if include_reference:
            reference = pd.to_numeric(pd.Series([row.get(f"metric::reference::{metric}")]), errors="coerce").iloc[0]
            if pd.notna(reference):
                item += f" / rif. {_pli_metric_value_label(metric, reference)}"
        parts.append(item)
    return " · ".join(parts)

def _composite_load_frame(data: pd.DataFrame, request: AssistantRequest) -> pd.DataFrame:
    details, _ = _composite_load_details(data, request)
    if details.empty:
        return pd.DataFrame(columns=["Athlete", "value", "components_available"])
    return details[["Athlete", "value", "components_available"]].copy()


def _wants_starter_comparison(request: AssistantRequest) -> bool:
    return set(request.starter_statuses) == {"S", "NS"}


def _status_label(status: str) -> str:
    return "Starters (S)" if status == "S" else "No Starters (NS)"


def _status_metric_values(data: pd.DataFrame, request: AssistantRequest, status: str) -> pd.DataFrame:
    status_request = AssistantRequest(**{**request.__dict__, "starter_statuses": [status]})
    return _metric_value_frame(data, status_request).sort_values("value", ascending=False).reset_index(drop=True)


def _render_status_metric_comparison(data: pd.DataFrame, request: AssistantRequest, title: str) -> bool:
    """Due pannelli S/NS per una metrica della Dashboard."""
    if request.metric is None or not _wants_starter_comparison(request):
        return False
    panels = {status: _status_metric_values(data, request, status) for status in ("S", "NS")}
    if all(frame.empty for frame in panels.values()):
        return False
    meta = METRICS[request.metric]
    fig = make_subplots(rows=1, cols=2, subplot_titles=[_status_label("S"), _status_label("NS")], horizontal_spacing=0.12)
    max_rows = 0
    for col, status in enumerate(("S", "NS"), start=1):
        values = panels[status]
        limit = request.top_n or request.bottom_n
        if request.bottom_n:
            values = values.sort_values("value", ascending=True)
        if limit:
            values = values.head(limit)
        max_rows = max(max_rows, len(values))
        fig.add_trace(go.Bar(
            x=values["value"], y=values["Athlete"], orientation="h",
            name=_status_label(status),
            text=[_format_value(float(v), request.metric, request.max_speed_percent) for v in values["value"]],
            textposition="outside",
            hovertemplate=f"{_status_label(status)}<br>%{{y}}<br>%{{x}}<extra></extra>",
        ), row=1, col=col)
        fig.update_yaxes(autorange="reversed", title_text="", row=1, col=col)
        fig.update_xaxes(title_text=meta.get("unit", ""), row=1, col=col)
    fig.update_layout(
        title=title,
        showlegend=False,
        height=max(390, 34 * max_rows + 150),
        margin=dict(t=90, b=45, l=35, r=25),
    )
    st.plotly_chart(fig, use_container_width=True)
    return True


def _render_status_composite_comparison(data: pd.DataFrame, request: AssistantRequest) -> bool:
    """Confronta il PAS Load Index tra S e NS in due pannelli."""
    if not request.composite_load or not _wants_starter_comparison(request):
        return False
    status_details: dict[str, pd.DataFrame] = {}
    for status in ("S", "NS"):
        status_request = AssistantRequest(**{**request.__dict__, "starter_statuses": [status]})
        details, _ = _composite_load_details(data, status_request)
        status_details[status] = details.sort_values("value", ascending=False).reset_index(drop=True)
    if all(frame.empty for frame in status_details.values()):
        return False
    fig = make_subplots(rows=1, cols=2, subplot_titles=[_status_label("S"), _status_label("NS")], horizontal_spacing=0.12)
    max_rows = 0
    for col, status in enumerate(("S", "NS"), start=1):
        values = status_details[status]
        limit = request.top_n or (min(10, len(values)) if request.session_overview else len(values))
        if limit:
            values = values.head(limit)
        max_rows = max(max_rows, len(values))
        fig.add_trace(go.Bar(
            x=values["value"], y=values["Athlete"], orientation="h",
            name=_status_label(status), text=[f"{v:.1f}%" for v in values["value"]], textposition="outside",
            hovertemplate=f"{_status_label(status)}<br>%{{y}}<br>PLI: %{{x:.1f}}%<extra></extra>",
        ), row=1, col=col)
        if not values.empty:
            fig.add_vline(x=float(values["value"].mean()), line_dash="dash", row=1, col=col)
        fig.update_yaxes(autorange="reversed", title_text="", row=1, col=col)
        fig.update_xaxes(title_text="PLI (% modello gara)", rangemode="tozero", row=1, col=col)
    fig.update_layout(
        title="PAS Load Index — Starters vs No Starters",
        showlegend=False,
        height=max(410, 36 * max_rows + 165),
        margin=dict(t=95, b=45, l=35, r=25),
    )
    st.plotly_chart(fig, use_container_width=True)
    return True


def _period_load_visual(data: pd.DataFrame, request: AssistantRequest) -> bool:
    if request.metric is None:
        return False
    allowed = {"Full Training", "Match", "Active Recovery", "Recovery", "Different Training", "Different Traning"}
    frame = data[data["Drill"].isin(allowed)].copy()
    if request.cycles and "Cycle" in frame.columns:
        frame = frame[frame["Cycle"].astype(str).isin(request.cycles)]
    if request.period_start is not None and request.period_end is not None:
        dates = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        frame = frame[dates.between(request.period_start.normalize(), request.period_end.normalize())]
    if request.players:
        frame = frame[frame["Athlete"].isin(request.players)]
    role_col = _role_column(frame)
    if request.roles and role_col:
        frame = frame[frame[role_col].astype(str).isin(request.roles)]
    compare_statuses = _wants_starter_comparison(request) and "Starters / No Starters" in frame.columns
    if request.starter_statuses and not compare_statuses and "Starters / No Starters" in frame.columns:
        frame = frame[frame["Starters / No Starters"].astype(str).str.upper().isin(request.starter_statuses)]
    meta = METRICS[request.metric]
    column = meta["column"]
    if frame.empty or column not in frame.columns:
        return False
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if compare_statuses:
        status_col = "Starters / No Starters"
        if request.cycles and len(request.cycles) > 1:
            grouped = frame.groupby(["Cycle", status_col, "Athlete"], as_index=False).agg(value=(column, meta.get("aggregation", "sum")))
            means = grouped.groupby(["Cycle", status_col], as_index=False)["value"].mean()
            fig = make_subplots(rows=1, cols=2, subplot_titles=[_status_label("S"), _status_label("NS")], horizontal_spacing=0.12)
            for col_idx, status in enumerate(("S", "NS"), start=1):
                status_rows = means[means[status_col].astype(str).str.upper().eq(status)].set_index("Cycle").reindex(request.cycles).reset_index()
                fig.add_trace(go.Bar(x=status_rows["Cycle"], y=status_rows["value"], name=_status_label(status), text=[_format_value(float(v), request.metric) if pd.notna(v) else "" for v in status_rows["value"]], textposition="outside"), row=1, col=col_idx)
                fig.update_xaxes(title_text="Match Cycle", row=1, col=col_idx)
                fig.update_yaxes(title_text=meta.get("unit", ""), row=1, col=col_idx)
            fig.update_layout(title=f"Confronto cicli gara — {request.metric} · S vs NS", showlegend=False, height=430)
        else:
            totals = frame.groupby([status_col, "Athlete"], as_index=False).agg(value=(column, meta.get("aggregation", "sum"))).dropna(subset=["value"])
            fig = make_subplots(rows=1, cols=2, subplot_titles=[_status_label("S"), _status_label("NS")], horizontal_spacing=0.12)
            max_rows = 0
            for col_idx, status in enumerate(("S", "NS"), start=1):
                status_rows = totals[totals[status_col].astype(str).str.upper().eq(status)].sort_values("value", ascending=request.bottom_n is not None)
                limit = request.top_n or request.bottom_n
                if limit:
                    status_rows = status_rows.head(limit)
                max_rows = max(max_rows, len(status_rows))
                fig.add_trace(go.Bar(x=status_rows["value"], y=status_rows["Athlete"], orientation="h", name=_status_label(status), text=[_format_value(float(v), request.metric) for v in status_rows["value"]], textposition="outside"), row=1, col=col_idx)
                fig.update_yaxes(autorange="reversed", title_text="", row=1, col=col_idx)
                fig.update_xaxes(title_text=meta.get("unit", ""), row=1, col=col_idx)
            fig.update_layout(title=f"Totale periodo — {request.metric} · Starters vs No Starters", showlegend=False, height=max(400, 34 * max_rows + 150))
        st.plotly_chart(fig, use_container_width=True)
        if request.cycles:
            st.caption("Match Cycle: " + ", ".join(request.cycles))
        return True
    if request.cycles and len(request.cycles) > 1:
        grouped = frame.groupby(["Cycle", "Athlete"], as_index=False).agg(value=(column, meta.get("aggregation", "sum")))
        if request.players:
            pivot = grouped.pivot(index="Cycle", columns="Athlete", values="value").reindex(request.cycles)
            fig = go.Figure()
            for player in pivot.columns:
                fig.add_trace(go.Bar(name=str(player), x=pivot.index, y=pivot[player]))
            fig.update_layout(barmode="group", title=f"Confronto cicli gara — {request.metric}", xaxis_title="Match Cycle", yaxis_title=meta.get("unit", ""))
        else:
            totals = grouped.groupby("Cycle", as_index=False)["value"].mean().set_index("Cycle").reindex(request.cycles).reset_index()
            fig = go.Figure(go.Bar(x=totals["Cycle"], y=totals["value"], marker_color=meta["color"], text=[_format_value(float(v), request.metric) for v in totals["value"]], textposition="outside"))
            fig.update_layout(title=f"Media giocatore per ciclo gara — {request.metric}", xaxis_title="Match Cycle", yaxis_title=meta.get("unit", ""), showlegend=False)
    else:
        totals = frame.groupby("Athlete", as_index=False).agg(value=(column, meta.get("aggregation", "sum"))).dropna().sort_values("value", ascending=False)
        limit = request.top_n or request.bottom_n
        if request.bottom_n:
            totals = totals.sort_values("value", ascending=True)
        if limit:
            totals = totals.head(limit)
        fig = go.Figure(go.Bar(x=totals["value"], y=totals["Athlete"], orientation="h", marker_color=meta["color"], text=[_format_value(float(v), request.metric) for v in totals["value"]], textposition="outside"))
        fig.update_layout(title=f"Totale periodo — {request.metric}", xaxis_title=meta.get("unit", ""), yaxis_title="", yaxis=dict(autorange="reversed"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    if request.cycles:
        st.caption("Match Cycle: " + ", ".join(request.cycles))
    return True


def _drills_visual(data: pd.DataFrame, request: AssistantRequest) -> bool:
    if request.metric is None:
        return False
    frame = data[~data["Drill"].isin(["Full Training", "Different Training", "Different Traning"])].copy()
    if request.cycles and "Cycle" in frame.columns:
        frame = frame[frame["Cycle"].astype(str).isin(request.cycles)]
    if request.period_start is not None and request.period_end is not None:
        dates = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        frame = frame[dates.between(request.period_start.normalize(), request.period_end.normalize())]
    if request.drill:
        frame = frame[frame["Drill"].eq(request.drill)]
    if request.players:
        frame = frame[frame["Athlete"].isin(request.players)]
    role_col = _role_column(frame)
    if request.roles and role_col:
        frame = frame[frame[role_col].astype(str).isin(request.roles)]
    if request.starter_statuses and "Starters / No Starters" in frame.columns:
        frame = frame[frame["Starters / No Starters"].astype(str).str.upper().isin(request.starter_statuses)]
    meta = METRICS[request.metric]
    column = meta["column"]
    if frame.empty or column not in frame.columns:
        return False
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
    occurrences = frame.groupby(["Date", "Drill", "Athlete"], as_index=False).agg(value=(column, meta.get("aggregation", "sum")))
    if request.drill and request.players:
        result = occurrences.groupby("Athlete", as_index=False)["value"].mean().sort_values("value", ascending=False)
        title = f"{request.drill} — confronto giocatori · {request.metric}"
        ycol = "Athlete"
    else:
        result = occurrences.groupby("Drill", as_index=False)["value"].mean().sort_values("value", ascending=False)
        title = f"Drills — media per occorrenza · {request.metric}"
        ycol = "Drill"
    limit = request.top_n or request.bottom_n
    if request.bottom_n:
        result = result.sort_values("value", ascending=True)
    if limit:
        result = result.head(limit)
    fig = go.Figure(go.Bar(x=result["value"], y=result[ycol], orientation="h", marker_color=meta["color"], text=[_format_value(float(v), request.metric) for v in result["value"]], textposition="outside"))
    fig.update_layout(title=title, xaxis_title=meta.get("unit", ""), yaxis_title="", yaxis=dict(autorange="reversed"), showlegend=False, height=max(360, 34 * len(result) + 110))
    st.plotly_chart(fig, use_container_width=True)
    if request.cycles:
        st.caption("Match Cycle: " + ", ".join(request.cycles))
    return True


def _render_priority_visual(data: pd.DataFrame, request: AssistantRequest) -> None:
    """Mostra immediatamente il risultato visivo principale della richiesta."""
    target = st.session_state.get("pas_intelligence_target")
    if target == "📊 Period Load" and _period_load_visual(data, request):
        return
    if target == "🧩 Drills" and _drills_visual(data, request):
        return
    if _render_status_composite_comparison(data, request):
        return
    if request.metric is not None and _render_status_metric_comparison(
        data, request, f"{_metric_display_name(request)} — Starters vs No Starters"
    ):
        return
    if request.composite_load:
        details, used_metrics = _composite_load_details(data, request)
        values = details.sort_values("value", ascending=False).reset_index(drop=True)
        if values.empty:
            return
        limit = request.top_n or (min(10, len(values)) if request.session_overview else 1)
        selected = values.head(limit)
        bar_colors = ["#1F77B4" if i < max(1, min(5, limit)) else "#AEB8C6" for i in range(len(selected))]
        fig = go.Figure(go.Bar(
            x=selected["value"], y=selected["Athlete"], orientation="h",
            marker_color=bar_colors, text=[f"{v:.1f}%" for v in selected["value"]], textposition="outside",
            hovertemplate="%{y}<br>PLI: %{x:.1f}%<extra></extra>",
        ))
        fig.add_vline(x=float(values["value"].mean()), line_dash="dash", annotation_text="Media squadra")
        fig.update_layout(
            title="PAS Load Index della seduta",
            xaxis_title="PLI (% modello gara)", yaxis_title="",
            yaxis=dict(autorange="reversed"), showlegend=False,
            height=max(320, 38 * len(selected) + 150),
        )
        st.plotly_chart(fig, use_container_width=True)

        if request.session_overview:
            distribution = go.Figure()
            distribution.add_trace(go.Box(
                x=values["value"], name="Squadra", boxpoints="all", jitter=0.35, pointpos=0,
                text=values["Athlete"], hovertemplate="%{text}<br>PLI: %{x:.1f}%<extra></extra>"
            ))
            distribution.update_layout(
                title="Distribuzione del PAS Load Index", xaxis_title="PLI (% modello gara)",
                yaxis_title="", showlegend=False, height=260, margin=dict(t=55, b=35, l=30, r=20)
            )
            st.plotly_chart(distribution, use_container_width=True)

        profile_players = values.head(min(5, len(values))) if request.session_overview else selected
        profile_rows = []
        for _, row in profile_players.iterrows():
            for metric in used_metrics:
                pct_col = f"component::{metric}"
                if pct_col in row and pd.notna(row[pct_col]):
                    absolute_detail = _pli_component_detail(row, metric, include_reference=False)
                    reference_detail = _pli_component_detail(row, metric, include_reference=True)
                    compact_detail = absolute_detail.replace(" · ", "<br>")
                    profile_rows.append({
                        "Athlete": row["Athlete"],
                        "Metric": metric,
                        "Percentile": float(row[pct_col]),
                        "AbsoluteDetail": absolute_detail,
                        "ReferenceDetail": reference_detail,
                        "Label": f"{float(row[pct_col]):.1f}%<br>{compact_detail}",
                    })
        if profile_rows:
            profile = pd.DataFrame(profile_rows)
            profile_fig = go.Figure()
            for athlete in profile_players["Athlete"].astype(str):
                athlete_rows = profile[profile["Athlete"].eq(athlete)]
                profile_fig.add_trace(go.Bar(
                    name=athlete, x=athlete_rows["Metric"], y=athlete_rows["Percentile"],
                    text=athlete_rows["Label"], textposition="outside",
                    customdata=athlete_rows[["AbsoluteDetail", "ReferenceDetail"]],
                    hovertemplate=(
                        f"<b>{athlete}</b><br>%{{x}}: %{{y:.1f}}% modello gara<br>"
                        "Valori: %{customdata[0]}<br>Valori / riferimenti: %{customdata[1]}<extra></extra>"
                    ),
                ))
            profile_fig.update_layout(
                title="Profilo PLI dei giocatori con carico maggiore",
                xaxis_title="", yaxis_title="% modello gara",
                yaxis=dict(rangemode="tozero"), barmode="group",
                legend_title_text="Giocatore", height=520,
                uniformtext_minsize=8, uniformtext_mode="hide",
                margin=dict(t=70, b=110, l=40, r=30),
            )
            st.plotly_chart(profile_fig, use_container_width=True)
        return
    if request.metric is None:
        return
    values = _metric_value_frame(data, request)
    if values.empty:
        return

    if request.compare_history and len(request.players) == 1:
        player = request.players[0]
        meta = METRICS[request.metric]
        column = meta["column"]
        frame = data[data["Athlete"].eq(player)].copy()
        if request.drill:
            frame = frame[frame["Drill"].eq(request.drill)]
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.normalize()
        history = frame.groupby("Date", as_index=False).agg(
            value=(column, meta.get("aggregation", "sum"))
        ).dropna()
        if not history.empty:
            fig = go.Figure(go.Scatter(
                x=history["Date"], y=history["value"], mode="lines+markers",
                name=player, line=dict(color=meta["color"])
            ))
            fig.update_layout(
                title=f"Storico di {player} — {request.metric}",
                xaxis_title="Data", yaxis_title=meta.get("unit", ""),
                margin=dict(t=55, b=30, l=30, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)
            return

    # Le richieste con soglia mantengono l'intero gruppo come contesto.
    if request.operator and request.threshold is not None:
        masks = {
            ">": values["value"] > request.threshold,
            ">=": values["value"] >= request.threshold,
            "<": values["value"] < request.threshold,
            "<=": values["value"] <= request.threshold,
        }
        matched_mask = masks[request.operator]
        values = values.assign(matched=matched_mask).sort_values(
            "value", ascending=request.operator in {"<", "<="}
        )
        metric_color = METRICS[request.metric]["color"]
        neutral_color = "#D9DEE7"
        bar_colors = [metric_color if flag else neutral_color for flag in values["matched"]]
        if request.max_speed_percent and "absolute_value" in values.columns:
            text_values = [
                (
                    f"{_format_value(float(abs_value), request.metric)}<br>"
                    f"{_format_value(float(value), request.metric, True)}"
                ) if flag else ""
                for value, abs_value, flag in zip(
                    values["value"], values["absolute_value"], values["matched"]
                )
            ]
            customdata = list(zip(
                values["absolute_value"], values["value"], values["matched"]
            ))
            hovertemplate = (
                "%{y}<br>Max Speed: %{customdata[0]:.1f} km/h"
                "<br>% individuale: %{customdata[1]:.1f}%<extra></extra>"
            )
        else:
            text_values = [
                _format_value(float(value), request.metric, request.max_speed_percent) if flag else ""
                for value, flag in zip(values["value"], values["matched"])
            ]
            customdata = list(values["matched"])
            hovertemplate = "%{y}<br>%{x}<extra></extra>"
        fig = go.Figure(go.Bar(
            x=values["value"], y=values["Athlete"], orientation="h",
            marker_color=bar_colors, text=text_values, textposition="outside",
            customdata=customdata,
            hovertemplate=hovertemplate,
        ))
        fig.add_vline(
            x=request.threshold, line_dash="dash", line_width=2,
            line_color=metric_color,
            annotation_text=f"Soglia: {_format_value(request.threshold, request.metric, request.max_speed_percent)}",
            annotation_position="top",
        )
        annotations = []
        for athlete, matched in zip(values["Athlete"], values["matched"]):
            label = f"<b>{athlete}</b>" if matched else str(athlete)
            annotations.append(dict(
                x=-0.012, xref="paper", y=athlete, yref="y", text=label,
                showarrow=False, xanchor="right", align="right",
                font=dict(color=metric_color if matched else "#7A8494", size=12),
            ))
        fig.update_layout(
            title=(
                "Max Speed (km/h) · % del massimo individuale — soglia richiesta"
                if request.max_speed_percent
                else f"{_metric_display_name(request)} — soglia richiesta"
            ),
            xaxis_title="% Max Speed individuale" if request.max_speed_percent else METRICS[request.metric].get("unit", ""),
            yaxis_title="", yaxis=dict(autorange="reversed", showticklabels=False),
            showlegend=False, annotations=annotations,
            height=max(360, 32 * len(values) + 100),
            margin=dict(t=70, b=35, l=165, r=45),
        )
        st.plotly_chart(fig, use_container_width=True)
        return

    ascending = request.bottom_n is not None
    values = values.sort_values("value", ascending=ascending)
    limit = request.top_n or request.bottom_n
    if limit:
        values = values.head(limit)
    if values.empty:
        return
    horizontal = len(values) >= 6
    if request.max_speed_percent and "absolute_value" in values.columns:
        result_text = [
            f"{_format_value(float(abs_value), request.metric)}<br>"
            f"{_format_value(float(value), request.metric, True)}"
            for value, abs_value in zip(values["value"], values["absolute_value"])
        ]
        result_customdata = list(zip(values["absolute_value"], values["value"]))
        result_hover = (
            "Max Speed: %{customdata[0]:.1f} km/h"
            "<br>% individuale: %{customdata[1]:.1f}%<extra></extra>"
        )
    else:
        result_text = [
            _format_value(float(v), request.metric, request.max_speed_percent)
            for v in values["value"]
        ]
        result_customdata = None
        result_hover = None
    fig = go.Figure(go.Bar(
        x=values["value"] if horizontal else values["Athlete"],
        y=values["Athlete"] if horizontal else values["value"],
        orientation="h" if horizontal else "v",
        marker_color=METRICS[request.metric]["color"],
        text=result_text,
        textposition="outside",
        customdata=result_customdata,
        hovertemplate=result_hover,
    ))
    fig.update_layout(
        title=(
            "Max Speed (km/h) · % del massimo individuale — risultato richiesta"
            if request.max_speed_percent
            else f"{request.metric} — risultato richiesta"
        ),
        xaxis_title=METRICS[request.metric].get("unit", "") if horizontal else "",
        yaxis_title="" if horizontal else METRICS[request.metric].get("unit", ""),
        yaxis=dict(autorange="reversed") if horizontal else None,
        showlegend=False, margin=dict(t=55, b=30, l=30, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def _quick_action_query(action: str, request: AssistantRequest) -> str:
    players = " e ".join(request.players)
    metric = request.metric or "Distance"
    if action == "Storico" and players:
        return f"Mostra lo storico di {players} per {metric}"
    if action == "Top 5":
        return f"Top 5 per {metric}"
    if action == "Confronta ruolo" and players:
        return f"Confronta {players} con la media del ruolo per {metric}"
    if action == "Squadra":
        return f"Mostra la squadra per {metric}"
    return request.query


def render_pas_assistant(data: pd.DataFrame, page: str) -> None:
    _clear_legacy_controller_state()

    st.markdown(
        """
        <style>
        .pas-analysis-heading {display:flex;align-items:baseline;gap:.65rem;margin:.1rem 0 .35rem 0;}
        .pas-analysis-title {font-size:1.05rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;}
        .pas-analysis-subtitle {font-size:.78rem;opacity:.62;}
        div[data-testid="stForm"] {border:1px solid rgba(128,128,128,.22);border-radius:.65rem;padding:.55rem .65rem .35rem .65rem;margin-bottom:.35rem;}
        </style>
        <div class="pas-analysis-heading">
          <span class="pas-analysis-title">PAS Intelligence</span>
          <span class="pas-analysis-subtitle">Navigation & analysis engine</span>
        </div>
        """, unsafe_allow_html=True,
    )

    metric_names = list(METRICS.keys())
    default_metric = "Distance (m)" if "Distance (m)" in metric_names else metric_names[0]
    with st.form("pas_intelligence_form", clear_on_submit=False):
        col_query, col_metric, col_ask = st.columns([5.2, 1.8, 1.2])
        with col_query:
            query = st.text_input(
                "Analysis request",
                placeholder="Cosa vuoi analizzare?",
                key="pas_intelligence_input", label_visibility="collapsed",
            )
        with col_metric:
            selected_metric = st.selectbox(
                "Metrica di contesto", metric_names,
                index=metric_names.index(default_metric),
                key="pas_intelligence_metric", label_visibility="collapsed",
            )
        with col_ask:
            submitted = st.form_submit_button("Esegui", type="primary", use_container_width=True)

    helper_col, reset_col = st.columns([7, 1])
    helper_col.caption(
        "PAS sceglie la sezione più adatta e applica i filtri disponibili. "
        "Se la richiesta non indica una metrica, usa quella selezionata."
    )
    if reset_col.button("Ripristina", use_container_width=True, key="pas_intelligence_reset"):
        _reset_dashboard_route()
        for key in ("pas_intelligence_summary", "pas_intelligence_query", "pas_intelligence_success",
                    "pas_intelligence_target", "pas_intelligence_request", "pas_pending_navigation"):
            st.session_state.pop(key, None)
        st.rerun()

    if submitted:
        if not query.strip():
            st.warning("Inserisci una richiesta da analizzare.")
        else:
            _apply_intelligence_request(query.strip(), selected_metric, data, page)
            st.rerun()

    summary = st.session_state.get("pas_intelligence_summary")
    query_used = st.session_state.get("pas_intelligence_query")
    success = st.session_state.get("pas_intelligence_success")
    target = st.session_state.get("pas_intelligence_target")
    if summary:
        status = "Configurazione applicata" if success else "Richiesta non applicata"
        with st.expander(f"{status} · {query_used or 'PAS Intelligence'}", expanded=True):
            if success:
                req = st.session_state.get("pas_intelligence_request")
                confidence = st.session_state.get("pas_intelligence_confidence", 0)
                st.caption(f"Sezione: {target} · Confidenza interpretazione: {confidence}%")
                if isinstance(req, AssistantRequest):
                    _render_priority_visual(data, req)
                    _render_contextual_key_insights(data, req)
                    st.markdown(f"**Configurazione applicata:** {summary}")
                    actions = ["Top 5", "Squadra"]
                    if req.players:
                        actions = ["Storico", "Confronta ruolo", *actions]
                    cols = st.columns(len(actions))
                    for col, action in zip(cols, actions):
                        if col.button(action, key=f"pas_quick_{action}", use_container_width=True):
                            next_query = _quick_action_query(action, req)
                            _apply_intelligence_request(next_query, req.metric or selected_metric, data, page)
                            st.rerun()
                st.caption("Il grafico viene mostrato per primo; la sezione selezionata resta disponibile subito sotto con i propri componenti originali.")
            else:
                st.warning(summary)

    st.divider()
