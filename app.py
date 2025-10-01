import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import textwrap

# ---------------- Configuración ----------------
st.set_page_config(
    page_title="Dashboard GRD - MINEDU",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.title("📊 Dashboard — Gestión de la Información y del Conocimiento en GRD")

# ---- CSS simple para mejor visualización en móvil/tablet ----
st.markdown("""
<style>
.block-container { padding-top: 0.75rem; padding-bottom: 0.75rem; }
[data-testid="stHorizontalBlock"]>div { padding-right: 0.5rem; padding-left: 0.5rem; }
@media (max-width: 992px){
  .block-container { padding-left: 0.75rem; padding-right: 0.75rem; }
  h1 { font-size: 1.4rem; }
  h2 { font-size: 1.2rem; }
  h3 { font-size: 1.05rem; }
}
</style>
""", unsafe_allow_html=True)

# ---------------- Utilidades ----------------
@st.cache_data
def leer_excel_relativo(nombre_archivo: str) -> pd.DataFrame:
    """Lee un Excel usando ruta relativa al archivo app.py."""
    ruta = Path(__file__).parent / nombre_archivo
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo '{nombre_archivo}'. "
            "Asegúrate de colocarlo en el mismo directorio que app.py "
            "o súbelo al repositorio."
        )
    df = pd.read_excel(ruta)
    # limpieza menor
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
    return df

def normalizar_instancia(s: pd.Series) -> pd.Series:
    s2 = s.fillna("").astype(str).str.upper()
    out = pd.Series("OTRAS", index=s2.index)
    out = out.mask(s2.str.contains("UGEL"), "UGEL")
    out = out.mask(s2.str.contains("DRE") | s2.str.contains("GRE"), "DRE/GRE")
    out = out.mask(s2.str.contains("ODENAGED"), "ODENAGED")
    out = out.mask(s2.str.contains("MINEDU"), "MINEDU")
    out = out.mask((s2 == "") | s2.isna() | s2.isin(["-", "NAN", "NONE"]), "Sin especificar")
    return out

def canonizar_respuestas(series: pd.Series) -> pd.Series:
    s = series.astype("string").fillna("Sin respuesta").str.strip()
    m = {"Si": "Sí", "si": "Sí", "SI": "Sí", "SÍ": "Sí",
         "No se": "No sé", "No Se": "No sé", "NO SE": "No sé", "NO SÉ": "No sé"}
    return s.replace(m)

def tabla_frecuencias(series: pd.Series) -> pd.DataFrame:
    s = canonizar_respuestas(series)
    t = s.value_counts(dropna=False).rename_axis("Respuesta").reset_index(name="Frecuencia")
    total = int(t["Frecuencia"].sum())
    t["Porcentaje (%)"] = (t["Frecuencia"] * 100 / total).round().astype(int)
    t_total = pd.DataFrame([{"Respuesta": "Total", "Frecuencia": total, "Porcentaje (%)": 100}])
    return pd.concat([t, t_total], ignore_index=True)

def ordenar_respuestas(df_freq: pd.DataFrame) -> pd.DataFrame:
    ordenes = [
        ["Nunca", "Rara vez", "A veces", "Frecuentemente", "Siempre", "Sin respuesta", "Total"],
        ["Muy en desacuerdo", "En desacuerdo", "Neutral", "De acuerdo", "Muy de acuerdo", "Sin respuesta", "Total"],
        ["No", "No sé", "Sí", "Sin respuesta", "Total"],
        ["Sí", "No", "No sé", "Sin respuesta", "Total"],
    ]
    vals = df_freq["Respuesta"].tolist()
    for orden in ordenes:
        if set(vals).issubset(set(orden)):
            df_freq["Respuesta"] = pd.Categorical(df_freq["Respuesta"], categories=orden, ordered=True)
            return df_freq.sort_values("Respuesta").reset_index(drop=True)
    df_ = df_freq[df_freq["Respuesta"] != "Total"].sort_values("Respuesta")
    total_row = df_freq[df_freq["Respuesta"] == "Total"]
    return pd.concat([df_, total_row], ignore_index=True)

def wrap_label(txt: str, width: int = 18) -> str:
    return "<br>".join(textwrap.wrap(str(txt), width=width)) if isinstance(txt, str) else str(txt)

def grafico_barras_responsive(df_freq: pd.DataFrame, titulo: str):
    df_plot = df_freq[df_freq["Respuesta"] != "Total"].copy()
    etiquetas = df_plot["Respuesta"].astype(str).tolist()
    largo_max = max((len(x) for x in etiquetas), default=0)
    usar_horizontal = (len(etiquetas) > 5) or (largo_max > 18)
    df_plot["RespuestaWrapped"] = [wrap_label(x, 18) for x in etiquetas]

    if usar_horizontal:
        fig = px.bar(
            df_plot, y="RespuestaWrapped", x="Frecuencia",
            text="Porcentaje (%)", orientation="h",
            title=titulo, labels={"Frecuencia": "N° de respuestas", "RespuestaWrapped": "Opción"},
        )
        fig.update_yaxes(automargin=True)
    else:
        fig = px.bar(
            df_plot, x="RespuestaWrapped", y="Frecuencia",
            text="Porcentaje (%)",
            title=titulo, labels={"Frecuencia": "N° de respuestas", "RespuestaWrapped": "Opción"},
        )
        fig.update_xaxes(automargin=True)

    fig.update_traces(texttemplate="%{text}%", textposition="outside", cliponaxis=False)
    fig.update_layout(autosize=True, margin=dict(t=60, r=20, b=20, l=20),
                      xaxis_title="", yaxis_title="Frecuencia", showlegend=False)
    return fig

# ---------------- Carga de datos (ruta relativa oculta al usuario) ----------------
NOMBRE_EXCEL = "encuesta_limpia.xlsx"  # Debe estar junto a app.py
try:
    df = leer_excel_relativo(NOMBRE_EXCEL)
except Exception as e:
    st.error(str(e))
    st.stop()

# Validaciones mínimas
COL_REGION = "Región en la que trabaja"
COL_INSTANCIA = "Instancia del MINEDU donde trabaja"
for c in [COL_REGION, COL_INSTANCIA]:
    if c not in df.columns:
        st.error(f"Falta la columna obligatoria: **{c}** en el archivo.")
        st.stop()

# Normalizar instancia
df["Instancia (Normalizada)"] = normalizar_instancia(df[COL_INSTANCIA])

# ---------------- Sidebar: SOLO filtros ----------------
st.sidebar.header("🎯 Filtros")
regiones = ["Todas"] + sorted(df[COL_REGION].dropna().unique().tolist())
instancias = ["Todas"] + sorted(df["Instancia (Normalizada)"].dropna().unique().tolist())
region_sel = st.sidebar.selectbox("Región:", regiones, index=0)
inst_sel = st.sidebar.selectbox("Instancia (Normalizada):", instancias, index=0)

mask = pd.Series(True, index=df.index)
if region_sel != "Todas":
    mask &= (df[COL_REGION] == region_sel)
if inst_sel != "Todas":
    mask &= (df["Instancia (Normalizada)"] == inst_sel)
df_f = df[mask].copy()
if df_f.empty:
    st.warning("No hay datos para la combinación seleccionada.")
    st.stop()

# ---------------- KPIs ----------------
c1, c2, c3 = st.columns(3)
c1.metric("Total de respuestas (filtro)", f"{len(df_f)}")
c2.metric("Regiones (filtro)", f"{df_f[COL_REGION].nunique()}")
c3.metric("Instancias normalizadas (filtro)", f"{df_f['Instancia (Normalizada)'].nunique()}")

st.markdown("---")

# ---------------- 1) Resumen por región ----------------
st.subheader("📍 Resumen por región")
res_region = df_f.groupby(COL_REGION).size().reset_index(name="Respuestas")
res_region["% del total"] = (res_region["Respuestas"] * 100 / res_region["Respuestas"].sum()).round().astype(int)
fila_total = pd.DataFrame([{COL_REGION: "Total", "Respuestas": int(res_region["Respuestas"].sum()), "% del total": 100}])
res_region_tot = pd.concat([res_region, fila_total], ignore_index=True)

colA, colB = st.columns([1.1, 1])
with colA:
    st.dataframe(res_region_tot, use_container_width=True)
    st.download_button(
        "⬇️ Descargar resumen por región (CSV)",
        data=res_region_tot.to_csv(index=False).encode("utf-8"),
        file_name="resumen_por_region.csv",
        mime="text/csv"
    )
with colB:
    fig_reg = px.bar(
        res_region, x=COL_REGION, y="Respuestas", text="% del total",
        title="Respuestas por región", labels={"Respuestas": "N° de respuestas", COL_REGION: "Región"},
    )
    fig_reg.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_reg.update_layout(autosize=True, xaxis_title="", yaxis_title="Frecuencia",
                          showlegend=False, margin=dict(t=60, r=20, b=20, l=20))
    st.plotly_chart(fig_reg, use_container_width=True)

# ---------------- 2) Análisis por preguntas ----------------
st.markdown("---")
st.subheader("📝 Análisis por preguntas")

excluir = {
    "ID", "Hora de inicio", "Hora de finalización",
    COL_REGION, COL_INSTANCIA, "Instancia (Normalizada)",
    "Seleccione su cargo: ", "Seleccione sus años de experiencia: ",
    "Especificar otro cargo", "Especificar si seleccionó otros"
}
preguntas = [c for c in df_f.columns if c not in excluir]
sel_pregs = st.multiselect("Selecciona preguntas a visualizar:", preguntas, default=preguntas)

if not sel_pregs:
    st.info("Selecciona al menos una pregunta para ver resultados.")
else:
    tabs = st.tabs([f"Q{i+1}" for i in range(len(sel_pregs))])
    for tab, q in zip(tabs, sel_pregs):
        with tab:
            st.markdown(f"**{q}**")
            frec = tabla_frecuencias(df_f[q])
            frec = ordenar_respuestas(frec)
            st.dataframe(frec, use_container_width=True)
            st.download_button(
                "⬇️ Descargar tabla (CSV)",
                data=frec.to_csv(index=False).encode("utf-8"),
                file_name=f"frecuencias_{q[:40].replace(' ', '_')}.csv",
                mime="text/csv",
                key=f"dl_{q}"
            )
            st.plotly_chart(
                grafico_barras_responsive(frec, f"Distribución de respuestas — {q}"),
                use_container_width=True
            )

st.markdown("---")
st.caption("Dasbhoard - Encuesta de conocimiento - GRD - MINEDU")
