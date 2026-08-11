"""Interfaccia Streamlit isolata per il catalogo metriche PAS."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .database import PASConnectDatabase
from .metric_catalog import (
    METRIC_TYPES,
    PROVIDER_REGISTRY,
    VALUE_TYPES,
    catalog_preview_from_csv,
    planned_provider_entries,
)


def _catalog_frame(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "id", "canonical_metric", "display_name", "provider", "acquisition_mode",
        "provider_metric_name", "category", "metric_type", "canonical_unit",
        "provider_unit", "value_type", "requires_profile", "active", "description",
        "source_template",
    ]
    return pd.DataFrame(rows).reindex(columns=columns)


def render_metric_catalog_section(
    database: PASConnectDatabase, *, embedded: bool = False
) -> None:
    st.markdown("##### Catalogo metriche PAS")
    st.caption(
        "Il catalogo descrive le metriche disponibili e i mapping provider. "
        "Non attiva analisi e non modifica profili Team, sessioni o database Excel."
    )
    rows = database.list_metric_catalog()
    performance = [row for row in rows if not bool(row.get("is_contextual"))]
    contextual = [row for row in rows if bool(row.get("is_contextual"))]
    metric_cols = st.columns(4)
    metric_cols[0].metric("Metriche totali", len(performance))
    metric_cols[1].metric("Metriche attive", sum(bool(row.get("active")) for row in performance))
    metric_cols[2].metric(
        "Richiedono profilo", sum(bool(row.get("requires_profile")) for row in performance)
    )
    provider_counts = " · ".join(
        f"{provider}: {sum(row.get('provider') == provider for row in performance)}"
        for provider in PROVIDER_REGISTRY
    )
    metric_cols[3].metric("Provider catalogati", len({row.get("provider") for row in performance}))
    st.caption(provider_counts or "Nessun mapping provider salvato.")

    import_panel = (
        st.container(border=True)
        if embedded
        else st.expander("Importa intestazioni template CSV", expanded=not rows)
    )
    with import_panel:
        if embedded:
            st.markdown("###### Importa intestazioni template CSV")
        template = st.file_uploader(
            "Template CSV", type=["csv"], key="pas_metric_catalog_template",
            help="Viene letta esclusivamente la riga delle intestazioni; le righe dati non sono importate.",
        )
        include_firstbeat = st.checkbox(
            "Includi metriche PAS previste per Firstbeat (inattive e senza mapping)", value=True,
            key="pas_metric_catalog_include_firstbeat",
        )
        if template is not None:
            try:
                proposals = catalog_preview_from_csv(template, provider="GPExe")
                if include_firstbeat:
                    proposals.extend(planned_provider_entries())
                st.session_state["pas_metric_catalog_preview"] = proposals
            except Exception as exc:
                st.error(f"Template catalogo non valido: {exc}")
        proposals = st.session_state.get("pas_metric_catalog_preview", [])
        if proposals:
            proposal_frame = _catalog_frame(proposals)
            st.write(
                f"Preview: {len(proposals)} colonne/mapping · "
                f"{sum(bool(item.get('is_contextual')) for item in proposals)} contestuali · "
                f"{sum(not bool(item.get('is_contextual')) for item in proposals)} prestativi."
            )
            st.dataframe(proposal_frame, hide_index=True, use_container_width=True)
            if st.button("Salva preview nel catalogo", key="pas_metric_catalog_save_preview"):
                inserted, preserved = database.import_metric_catalog_proposals(proposals)
                st.success(
                    f"Catalogo aggiornato: {inserted} nuovi mapping · "
                    f"{preserved} mapping esistenti preservati."
                )
                st.rerun()

    search = st.text_input(
        "Cerca nome PAS o provider", key="pas_metric_catalog_search",
        placeholder="Nome metrica o nome colonna provider",
    ).strip().casefold()
    filter_cols = st.columns(5)
    provider_filter = filter_cols[0].selectbox("Provider", ("Tutti", *PROVIDER_REGISTRY))
    categories = tuple(sorted({str(row.get("category")) for row in performance}))
    category_filter = filter_cols[1].selectbox("Categoria", ("Tutte", *categories))
    type_filter = filter_cols[2].selectbox("Tipo", ("Tutti", *METRIC_TYPES))
    active_filter = filter_cols[3].selectbox("Stato", ("Tutte", "Attive", "Inattive"))
    profile_filter = filter_cols[4].selectbox("Richiede profilo", ("Tutte", "Sì", "No"))

    filtered = []
    for row in performance:
        searchable = f"{row.get('canonical_metric', '')} {row.get('display_name', '')} {row.get('provider_metric_name', '')}".casefold()
        if search and search not in searchable:
            continue
        if provider_filter != "Tutti" and row.get("provider") != provider_filter:
            continue
        if category_filter != "Tutte" and row.get("category") != category_filter:
            continue
        if type_filter != "Tutti" and row.get("metric_type") != type_filter:
            continue
        if active_filter != "Tutte" and bool(row.get("active")) != (active_filter == "Attive"):
            continue
        if profile_filter != "Tutte" and bool(row.get("requires_profile")) != (profile_filter == "Sì"):
            continue
        filtered.append(row)
    st.markdown("###### Metriche prestative")
    if filtered:
        st.dataframe(_catalog_frame(filtered), hide_index=True, use_container_width=True)
    else:
        st.info("Nessuna metrica prestativa corrisponde ai filtri.")
    st.markdown("###### Campi contestuali")
    if contextual:
        st.dataframe(_catalog_frame(contextual), hide_index=True, use_container_width=True)
    else:
        st.info("Nessun campo contestuale catalogato.")

    choices = [None, *rows]
    selected = st.selectbox(
        "Mapping da creare o aggiornare", choices,
        format_func=lambda item: "Nuovo mapping" if item is None else (
            f"#{item['id']} · {item['provider']} · {item['display_name']}"
        ),
        key="pas_metric_catalog_selected_mapping",
    )
    current = selected or {}
    form_key = str(current.get("id") or "new")
    with st.form(f"pas_metric_catalog_form_{form_key}"):
        canonical_metric = st.text_input(
            "Metrica canonica PAS", value=str(current.get("canonical_metric") or ""),
            disabled=selected is not None,
        )
        display_name = st.text_input("Display name", value=str(current.get("display_name") or ""))
        provider_names = tuple(PROVIDER_REGISTRY)
        current_provider = str(current.get("provider") or "GPExe")
        provider = st.selectbox(
            "Provider", provider_names,
            index=provider_names.index(current_provider) if current_provider in provider_names else 0,
            disabled=selected is not None,
        )
        provider_metric_name = st.text_input(
            "Nome metrica provider", value=str(current.get("provider_metric_name") or ""),
            disabled=selected is not None,
        )
        category = st.text_input("Categoria", value=str(current.get("category") or "GPS"))
        field_cols = st.columns(3)
        current_type = str(current.get("metric_type") or "direct")
        metric_type = field_cols[0].selectbox(
            "Tipo", METRIC_TYPES, index=METRIC_TYPES.index(current_type) if current_type in METRIC_TYPES else 0,
        )
        canonical_unit = field_cols[1].text_input(
            "Unità canonica", value=str(current.get("canonical_unit") or "")
        )
        provider_unit = field_cols[2].text_input(
            "Unità provider", value=str(current.get("provider_unit") or "")
        )
        current_value_type = str(current.get("value_type") or "numeric")
        value_type = st.selectbox(
            "Value type", VALUE_TYPES,
            index=VALUE_TYPES.index(current_value_type) if current_value_type in VALUE_TYPES else 0,
        )
        requires_profile = st.checkbox(
            "Richiede profilo Team/stagione", value=bool(current.get("requires_profile"))
        )
        active = st.checkbox("Attiva", value=bool(current.get("active")))
        description = st.text_area("Descrizione", value=str(current.get("description") or ""))
        save = st.form_submit_button("Salva mapping catalogo", use_container_width=True)
    if save:
        try:
            _, inserted = database.upsert_metric_catalog_entry({
                "id": current.get("id"), "canonical_metric": canonical_metric,
                "display_name": display_name, "provider": provider,
                "acquisition_mode": PROVIDER_REGISTRY[provider].acquisition_mode,
                "provider_metric_name": provider_metric_name, "category": category,
                "metric_type": metric_type, "canonical_unit": canonical_unit,
                "provider_unit": provider_unit, "value_type": value_type,
                "requires_profile": requires_profile, "active": active,
                "is_contextual": bool(current.get("is_contextual")),
                "description": description, "source_template": current.get("source_template"),
            })
            st.success("Mapping creato." if inserted else "Mapping aggiornato.")
            st.rerun()
        except Exception as exc:
            st.error(f"Mapping non salvato: {exc}")

    orphans = database.orphan_metric_profiles()
    if orphans:
        st.warning(
            f"Profili metrici orfani: {len(orphans)}. Non sono stati eliminati; "
            "aggiungi la relativa metrica canonica al catalogo."
        )
        st.dataframe(pd.DataFrame(orphans), hide_index=True, use_container_width=True)
