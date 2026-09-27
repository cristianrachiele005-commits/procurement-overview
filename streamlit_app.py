import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="Procurement Overview", page_icon="📦", layout="wide")

PFLICHTSPALTEN = ["Bestellnummer", "Bestelldatum", "Lieferant", "Artikel", "Menge", "Preis CHF"]


def chf(wert):
    """Zahl im Schweizer Format, z. B. 12'345"""
    return f"CHF {wert:,.0f}".replace(",", "'")


@st.cache_data
def beispieldaten(anzahl=400):
    rng = np.random.default_rng(42)
    lieferanten = [
        "Muster Metall AG", "Alpen Elektro GmbH", "Präzisionsteile Meier",
        "Kunststoff Huber AG", "Schrauben Frei", "Hydraulik Suisse SA",
        "Verpackung Keller", "Antriebe Weber AG",
    ]
    artikel = [
        "Wellenlager 40mm", "Steuerplatine V2", "Gehäuse Alu", "Dichtungsset",
        "Sechskantschraube M8", "Hydraulikzylinder", "Kartonbox 60x40",
        "Getriebemotor 0.75kW", "Kabelbaum 2m", "Frästeil Stahl",
    ]
    start = date(2026, 1, 1)
    bestelldatum = [start + timedelta(days=int(d)) for d in rng.integers(0, 265, anzahl)]
    df = pd.DataFrame({
        "Bestellnummer": [f"B-{26000 + i}" for i in range(anzahl)],
        "Bestelldatum": pd.to_datetime(bestelldatum),
        "Lieferant": rng.choice(lieferanten, anzahl, p=[.22, .18, .14, .12, .1, .1, .08, .06]),
        "Artikel": rng.choice(artikel, anzahl),
        "Menge": rng.integers(1, 200, anzahl),
        "Preis CHF": rng.uniform(2, 450, anzahl).round(2),
        "Status": rng.choice(["Offen", "Bestätigt", "Geliefert"], anzahl, p=[.2, .3, .5]),
    })
    return df


def daten_laden(datei):
    if datei.name.lower().endswith(".csv"):
        df = pd.read_csv(datei, sep=None, engine="python")
    else:
        df = pd.read_excel(datei)
    fehlend = [s for s in PFLICHTSPALTEN if s not in df.columns]
    if fehlend:
        st.error(f"In der Datei fehlen diese Spalten: {', '.join(fehlend)}")
        st.stop()
    df["Bestelldatum"] = pd.to_datetime(df["Bestelldatum"], dayfirst=True, errors="coerce")
    if "Status" not in df.columns:
        df["Status"] = "Unbekannt"
    return df


# ---------------- Seitenleiste: Daten & Filter ----------------
st.sidebar.header("Daten")
upload = st.sidebar.file_uploader("Bestellungen hochladen (Excel oder CSV)", type=["xlsx", "csv"])
st.sidebar.caption("Benötigte Spalten: " + ", ".join(PFLICHTSPALTEN) + " (optional: Status)")

if upload:
    df = daten_laden(upload)
else:
    df = beispieldaten()
    st.sidebar.info("Es werden Beispieldaten angezeigt.")

df["Bestellwert CHF"] = (df["Menge"] * df["Preis CHF"]).round(2)

st.sidebar.header("Filter")
min_d, max_d = df["Bestelldatum"].min().date(), df["Bestelldatum"].max().date()
zeitraum = st.sidebar.date_input("Zeitraum", (min_d, max_d), min_value=min_d, max_value=max_d)
lief_auswahl = st.sidebar.multiselect("Lieferanten", sorted(df["Lieferant"].unique()))
status_auswahl = st.sidebar.multiselect("Status", sorted(df["Status"].unique()))

gefiltert = df.copy()
if isinstance(zeitraum, tuple) and len(zeitraum) == 2:
    von, bis = pd.to_datetime(zeitraum[0]), pd.to_datetime(zeitraum[1])
    gefiltert = gefiltert[gefiltert["Bestelldatum"].between(von, bis)]
if lief_auswahl:
    gefiltert = gefiltert[gefiltert["Lieferant"].isin(lief_auswahl)]
if status_auswahl:
    gefiltert = gefiltert[gefiltert["Status"].isin(status_auswahl)]

# ---------------- Hauptbereich ----------------
st.title("📦 Procurement Overview")
st.caption("Übersicht über Bestellvolumen, Lieferanten und alle Bestellungen")

if gefiltert.empty:
    st.warning("Keine Bestellungen für diese Filter gefunden.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Bestellvolumen", chf(gefiltert["Bestellwert CHF"].sum()))
k2.metric("Bestellungen", f"{gefiltert['Bestellnummer'].nunique():,}".replace(",", "'"))
k3.metric("Lieferanten", gefiltert["Lieferant"].nunique())
k4.metric("Ø Bestellwert", chf(gefiltert["Bestellwert CHF"].mean()))

st.divider()

links, rechts = st.columns(2)
with links:
    st.subheader("Umsatz pro Lieferant")
    pro_lieferant = (gefiltert.groupby("Lieferant")["Bestellwert CHF"].sum()
                     .sort_values(ascending=False))
    st.bar_chart(pro_lieferant, horizontal=True, y_label="", x_label="CHF")

with rechts:
    st.subheader("Bestellvolumen pro Monat")
    pro_monat = (gefiltert.set_index("Bestelldatum")["Bestellwert CHF"]
                 .resample("MS").sum())
    pro_monat.index = pro_monat.index.strftime("%Y-%m")
    st.bar_chart(pro_monat, y_label="CHF", x_label="")

st.subheader("Lieferanten-Ranking")
ranking = (gefiltert.groupby("Lieferant")
           .agg(Bestellungen=("Bestellnummer", "nunique"),
                Umsatz=("Bestellwert CHF", "sum"))
           .sort_values("Umsatz", ascending=False))
ranking["Anteil"] = ranking["Umsatz"] / ranking["Umsatz"].sum() * 100
st.dataframe(
    ranking,
    use_container_width=True,
    column_config={
        "Umsatz": st.column_config.NumberColumn("Umsatz CHF", format="%.0f"),
        "Anteil": st.column_config.ProgressColumn("Anteil", format="%.1f %%", min_value=0, max_value=100),
    },
)

st.subheader("Alle Bestellungen")
suche = st.text_input("Suche (Bestellnummer, Artikel, Lieferant)")
tabelle = gefiltert.sort_values("Bestelldatum", ascending=False)
if suche:
    maske = tabelle[["Bestellnummer", "Artikel", "Lieferant"]].astype(str).apply(
        lambda s: s.str.contains(suche, case=False)).any(axis=1)
    tabelle = tabelle[maske]

st.dataframe(
    tabelle,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Bestelldatum": st.column_config.DateColumn("Bestelldatum", format="DD.MM.YYYY"),
        "Preis CHF": st.column_config.NumberColumn(format="%.2f"),
        "Bestellwert CHF": st.column_config.NumberColumn(format="%.2f"),
    },
)
st.download_button(
    "Tabelle als CSV herunterladen",
    tabelle.to_csv(index=False, sep=";").encode("utf-8-sig"),
    file_name="bestellungen.csv",
    mime="text/csv",
)
