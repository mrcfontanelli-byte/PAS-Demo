from __future__ import annotations

import pandas as pd


def _match_rows(df: pd.DataFrame) -> pd.DataFrame:
    values = df["Match Day +/-"].fillna("").astype(str)
    is_match = values.str.match(r"^MD\s+(?![+-]\d)", na=False)
    matches = (
        df.loc[is_match, ["Date", "Cycle", "Match Day +/-"]]
        .drop_duplicates()
        .sort_values("Date")
        .copy()
    )
    matches["Match Name"] = matches["Match Day +/-"].str.replace(r"^MD\s+", "", regex=True)
    return matches


def context_for_date(df: pd.DataFrame, selected_date: pd.Timestamp) -> dict:
    selected_date = pd.Timestamp(selected_date).normalize()
    day = df[df["Date"].dt.normalize().eq(selected_date)].copy()

    cycle = day["Cycle"].dropna().mode()
    cycle_value = cycle.iloc[0] if not cycle.empty else "N/D"

    length = day["Length Cycle"].dropna().mode()
    length_value = int(length.iloc[0]) if not length.empty else None

    combined = day["Match Day +/-"].dropna().mode()
    combined_value = combined.iloc[0] if not combined.empty else "N/D"

    md_minus = day["MD-"].dropna().mode()
    md_plus = day["MD+"].dropna().mode()

    if not md_minus.empty and str(md_minus.iloc[0]).startswith("MD -"):
        relative = str(md_minus.iloc[0])
    elif not md_plus.empty and str(md_plus.iloc[0]).startswith("MD +"):
        relative = str(md_plus.iloc[0])
    elif str(combined_value).startswith("MD "):
        relative = "Match Day"
    else:
        relative = str(combined_value)

    matches = _match_rows(df)
    previous = matches[matches["Date"].dt.normalize() < selected_date].tail(1)
    next_match = matches[matches["Date"].dt.normalize() >= selected_date].head(1)

    previous_info = None
    if not previous.empty:
        row = previous.iloc[0]
        previous_info = {
            "name": row["Match Name"],
            "date": row["Date"],
            "days": int((selected_date - row["Date"].normalize()).days),
        }

    next_info = None
    if not next_match.empty:
        row = next_match.iloc[0]
        next_info = {
            "name": row["Match Name"],
            "date": row["Date"],
            "days": int((row["Date"].normalize() - selected_date).days),
        }

    return {
        "date": selected_date,
        "cycle": cycle_value,
        "length_cycle": length_value,
        "relative_day": relative,
        "previous_match": previous_info,
        "next_match": next_info,
    }


def historical_similar_days(
    player_day: pd.DataFrame,
    selected_date: pd.Timestamp,
    same_cycle_length: bool = True,
) -> pd.DataFrame:
    selected_date = pd.Timestamp(selected_date).normalize()
    current = player_day[player_day["Date"].dt.normalize().eq(selected_date)]

    if current.empty:
        return player_day.iloc[0:0].copy()

    md_minus = current["MD-"].dropna().mode()
    md_plus = current["MD+"].dropna().mode()

    if not md_minus.empty and str(md_minus.iloc[0]).startswith("MD -"):
        column, value = "MD-", str(md_minus.iloc[0])
    elif not md_plus.empty and str(md_plus.iloc[0]).startswith("MD +"):
        column, value = "MD+", str(md_plus.iloc[0])
    else:
        column = "Match Day +/-"
        mode = current[column].dropna().mode()
        value = str(mode.iloc[0]) if not mode.empty else ""

    historical = player_day[
        player_day[column].astype(str).eq(value)
        & (player_day["Date"].dt.normalize() < selected_date)
    ].copy()

    if same_cycle_length:
        current_length = current["Length Cycle"].dropna().mode()
        if not current_length.empty:
            historical = historical[
                historical["Length Cycle"].eq(current_length.iloc[0])
            ]

    return historical
