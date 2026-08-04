"""Interfaccia PAS Connect del Metric Usage Registry."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .database import PASConnectDatabase
from .metric_usage import MODULES, USAGE_STATUSES, USAGE_TYPES, scan_metric_usage, usage_record


USAGE_COLUMNS = [
    "id", "canonical_metric", "module", "view_name", "usage_type", "status", "enabled",
    "required", "display_order", "notes", "created_at", "updated_at",
]
PREVIEW_COLUMNS = [
    "canonical_metric", "module", "view_name", "usage_type", "status",
    "source_file", "source_line", "evidence", "notes",
]


def render_metric_usage_section(database: PASConnectDatabase, code_root: Path) -> None:
    st.markdown("##### Utilizzo metriche PAS")
    st.caption(
        "Il registry descrive dove una metrica è usata. È indipendente dal provider e "
        "non modifica il comportamento di Dashboard, Drills, Match o report."
    )
    rows = database.list_metric_usage()
    catalog = [row for row in database.list_metric_catalog() if not bool(row.get("is_contextual"))]
    missing = database.catalog_metrics_without_usage()
    summary = st.columns(4)
    summary[0].metric("Associazioni totali", len(rows))
    summary[1].metric("Associazioni abilitate", sum(bool(row.get("enabled")) for row in rows))
    summary[2].metric("Moduli censiti", len({row.get("module") for row in rows}))
    summary[3].metric("Metriche senza utilizzo", len(missing))
    if rows:
        module_counts = pd.DataFrame(rows).groupby("module")["canonical_metric"].nunique()
        st.caption("Metriche usate per modulo · " + " · ".join(
            f"{module}: {int(count)}" for module, count in module_counts.items()
        ))
    status_counts = {status: sum(row.get("status") == status for row in rows) for status in USAGE_STATUSES}
    st.caption("Stato associazioni · " + " · ".join(
        f"{status}: {status_counts[status]}" for status in USAGE_STATUSES
    ))
    st.caption(
        "Legenda: VERIFIED = verificato nel codice · PROBABLE = alta confidenza · "
        "AMBIGUOUS = da validare · MANUAL = creato o confermato manualmente."
    )

    with st.expander("Preview censimento automatico (sola lettura)", expanded=not rows):
        if st.button("Analizza codice e metadati", key="pas_metric_usage_scan"):
            st.session_state["pas_metric_usage_preview"] = scan_metric_usage(code_root, catalog)
        proposals = st.session_state.get("pas_metric_usage_preview", [])
        if proposals:
            st.write(f"Associazioni proposte: {len(proposals)}. Nessuna è ancora stata salvata.")
            st.dataframe(
                pd.DataFrame(proposals).reindex(columns=PREVIEW_COLUMNS),
                hide_index=True, use_container_width=True,
            )
            if st.button("Conferma e salva associazioni proposte", key="pas_metric_usage_confirm"):
                inserted, updated = database.import_metric_usage_proposals(
                    [usage_record(item) for item in proposals]
                )
                st.success(f"Registry aggiornato: {inserted} create · {updated} aggiornate.")
                st.rerun()
        else:
            st.info("Avvia il censimento per generare una preview senza scritture nel database.")

    search = st.text_input("Cerca metrica utilizzata", key="pas_metric_usage_search").strip().casefold()
    filters = st.columns(6)
    metrics = tuple(sorted({str(row.get("canonical_metric")) for row in rows}))
    metric_filter = filters[0].selectbox("Metrica", ("Tutte", *metrics), key="usage_metric_filter")
    module_filter = filters[1].selectbox("Modulo", ("Tutti", *MODULES), key="usage_module_filter")
    views = tuple(sorted({str(row.get("view_name")) for row in rows}))
    view_filter = filters[2].selectbox("Vista", ("Tutte", *views), key="usage_view_filter")
    type_filter = filters[3].selectbox("Usage type", ("Tutti", *USAGE_TYPES), key="usage_type_filter")
    status_filter = filters[4].selectbox("Status", ("Tutti", *USAGE_STATUSES), key="usage_status_filter")
    enabled_filter = filters[5].selectbox("Enabled", ("Tutti", "Sì", "No"), key="usage_enabled_filter")
    filtered = []
    for row in rows:
        if search and search not in str(row.get("canonical_metric") or "").casefold():
            continue
        if metric_filter != "Tutte" and row.get("canonical_metric") != metric_filter:
            continue
        if module_filter != "Tutti" and row.get("module") != module_filter:
            continue
        if view_filter != "Tutte" and row.get("view_name") != view_filter:
            continue
        if type_filter != "Tutti" and row.get("usage_type") != type_filter:
            continue
        if status_filter != "Tutti" and row.get("status") != status_filter:
            continue
        if enabled_filter != "Tutti" and bool(row.get("enabled")) != (enabled_filter == "Sì"):
            continue
        filtered.append(row)
    if filtered:
        st.dataframe(pd.DataFrame(filtered).reindex(columns=USAGE_COLUMNS), hide_index=True, use_container_width=True)
    else:
        st.info("Nessuna associazione corrisponde ai filtri.")

    choices = [None, *rows]
    selected = st.selectbox(
        "Associazione da creare o aggiornare", choices,
        format_func=lambda item: "Nuova associazione" if item is None else (
            f"#{item['id']} · {item['canonical_metric']} · {item['module']} · {item['view_name']}"
        ), key="pas_metric_usage_selected",
    )
    current = selected or {}
    with st.form(f"pas_metric_usage_form_{current.get('id') or 'new'}"):
        catalog_metrics = tuple(sorted({str(row.get("canonical_metric")) for row in catalog}))
        current_metric = str(current.get("canonical_metric") or (catalog_metrics[0] if catalog_metrics else ""))
        canonical_metric = st.selectbox(
            "Canonical metric", catalog_metrics or (current_metric,),
            index=catalog_metrics.index(current_metric) if current_metric in catalog_metrics else 0,
        )
        current_module = str(current.get("module") or MODULES[0])
        module = st.selectbox("Modulo PAS", MODULES, index=MODULES.index(current_module))
        view_name = st.text_input("Nome vista", value=str(current.get("view_name") or ""))
        current_type = str(current.get("usage_type") or USAGE_TYPES[0])
        usage_type = st.selectbox("Usage type", USAGE_TYPES, index=USAGE_TYPES.index(current_type))
        enabled = st.checkbox("Enabled", value=bool(current.get("enabled", True)))
        required = st.checkbox("Required", value=bool(current.get("required", False)))
        display_order = st.number_input(
            "Display order", value=int(current.get("display_order") or 0), step=1,
        )
        notes = st.text_area("Note", value=str(current.get("notes") or ""))
        save = st.form_submit_button("Salva utilizzo metrica", use_container_width=True)
    if save:
        try:
            _, inserted = database.upsert_metric_usage({
                "id": current.get("id"), "canonical_metric": canonical_metric,
                "module": module, "view_name": view_name, "usage_type": usage_type,
                "status": "MANUAL",
                "enabled": enabled, "required": required, "display_order": display_order,
                "notes": notes,
            })
            st.success("Associazione creata." if inserted else "Associazione aggiornata.")
            st.rerun()
        except Exception as exc:
            st.error(f"Associazione non salvata: {exc}")

    st.markdown("###### Metriche senza utilizzo registrato")
    if missing:
        st.dataframe(pd.DataFrame({"canonical_metric": missing}), hide_index=True, use_container_width=True)
    else:
        st.success("Tutte le metriche del catalogo hanno almeno un utilizzo registrato.")
    orphans = database.orphan_metric_usage()
    if orphans:
        st.warning(f"Utilizzi metrici orfani: {len(orphans)}. Nessun record è stato eliminato.")
        st.dataframe(pd.DataFrame(orphans), hide_index=True, use_container_width=True)
