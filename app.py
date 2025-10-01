import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ---------------- Configuración ----------------
st.set_page_config(page_title="Dashboard GRD - MINEDU", layout="wide")
st.title("📊 Dashboard General — Encuesta: Gestión de la Información y del Conocimiento en GRD")

# ---------------- Utilidades ----------------
@st.cache_data
def leer_archivo(f) -> pd.DataFrame:
    """Lee Excel o CSV desde ruta Path/str o desde un file-like (uploader)."""
    # Detectar extensión
    if isinstance(f, (str, Path)):
        suf = Path(f).suffix.lower()
    else:
        suf = Path(getattr(f, "name", "archivo")).suffix.lower()

    if suf in [".xlsx", ".xlsm", ".xlsb", ".xls"]:
        return pd.read_excel(f)
    elif suf == ".csv":
        return pd.read_csv(f, encoding="utf-8")
    else:
        raise ValueError("Formato no soportado. Usa .xlsx o .csv")

def normalizar_instancia(s: pd.Series) -> pd.Series:
    s2 = s.fillna("").astype(str).str.upper()
    out = pd.Series("OTRAS", index=s2.index)
    out = out.mask(s2.str.contains("UGEL"), "UGEL")
    out = out.mask(s2.str.contains("DRE") | s2.str.contains("GRE"), "DRE/GRE")
    out = out.mask(s2.str.contains("ODENAGED"), "ODENAGED")
    out = out.mask(s2.str.contains("MINEDU"), "MINEDU")
    out = out.mask((s2 == "") | s2.isna() | s2.isin(["-", "NAN", "NONE"]), "Sin especificar")
    return out

def _canonizar_respuestas(series: pd.Series) -> pd.Series:
    s = series.astype("string").fillna("Sin respuesta").str.strip()
    m = {"Si": "Sí", "si": "Sí", "SI": "Sí",
         "No se": "No sé", "No Se": "No sé", "NO SE": "No sé", "NO SÉ": "No sé",
         "SÍ": "Sí"}
    return s.replace(m)

def tabla_frecuencias(series: pd.Series) -> pd.DataFrame:
    s = _canonizar_respuestas(series)
    t = s.value_counts(dropna=False).rename_axis("Respuesta").reset_index(name="Frecuencia")
    total = int(t["Frecuencia"].sum())
    t["Porcentaje (%)"] = (t["Frecuencia"] * 100 / total).round().astype(int)
    t_total = pd.DataFrame([{"Respuesta": "Total", "Frecuencia": total, "Porcentaje (%)": 100}])
    t = pd.concat([t, t_total], ignore_index=True)
    return t

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

def grafico_barras(df_freq: pd.DataFrame, titulo: str):
    df_plot = df_freq[df_freq["Respuesta"] != "Total"].copy()
    fig = px.bar(
        df_plot,
        x="Respuesta",
        y="Frecuencia",
        text="Porcentaje (%)",
        title=titulo,
        labels={"Frecuencia": "N° de respuestas", "Respuesta": "Opción"},
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(xaxis_title="", yaxis_title="Frecuencia", showlegend=False, margin=dict(t=60, r=20, b=20, l=20))
    return fig

# ---------------- Fuente de datos (repo o subida) ----------------
st.sidebar.header("📁 Datos")
opcion = st.sidebar.radio("Fuente de datos:", ["Archivo del repo", "Subir archivo"], index=0, horizontal=True)

df = None
if opcion == "Archivo del repo":
    nombre_relativo = st.sidebar.text_input("Nombre del archivo en el repo:", "encuesta_limpia.xlsx")
    ruta_rel = Path(__file__).parent / nombre_relativo
    if not ruta_rel.exists():
        st.error(f"No encuentro **{nombre_relativo}** en el repo. Sube el archivo con 'Subir archivo' o agrega el Excel al repositorio.")
        st.stop()
    df = leer_archivo(ruta_rel)
else:
    up = st.sidebar.file_uploader("Sube Excel/CSV limpio", type=["xlsx", "csv"])
    if up is None:
        st.info("Sube un archivo para continuar.")
        st.stop()
    df = leer_archivo(up)

# Limpieza ligera de columnas
df.columns = [c.strip() for c in df.columns]
for col in df.columns:
    if df[col].dtype == "object":
        df[col] = df[col].astype(str).str.strip()

# Validaciones mínimas
col_region = "Región en la que trabaja"
col_instancia = "Instancia del MINEDU donde trabaja"
for c in [col_region, col_instancia]:
    if c not in df.columns:
        st.error(f"Falta la columna obligatoria: **{c}**.")
        st.stop()

# Normalizar instancia
df["Instancia (Normalizada)"] = normalizar_instancia(df[col_instancia])

# Mostrar datos (opcional)
with st.expander("🔍 Ver datos brutos"):
    st.dataframe(df, use_container_width=True)

# ---------------- Filtros ----------------
st.sidebar.header("🎯 Filtros")
regiones = ["Todas"] + sorted(df[col_region].dropna().unique().tolist())
instancias = ["Todas"] + sorted(df["Instancia (Normalizada)"].dropna().unique().tolist())

region_sel = st.sidebar.selectbox("Región:", regiones, index=0)
inst_sel = st.sidebar.selectbox("Instancia (Normalizada):", instancias, index=0)

mask = pd.Series(True, index=df.index)
if region_sel != "Todas":
    mask &= (df[col_region] == region_sel)
if inst_sel != "Todas":
    mask &= (df["Instancia (Normalizada)"] == inst_sel)

df_f = df[mask].copy()
if df_f.empty:
    st.warning("No hay datos para la combinación seleccionada.")
    st.stop()

# ---------------- KPIs ----------------
c1, c2, c3 = st.columns(3)
c1.metric("Total de respuestas (filtro)", f"{len(df_f)}")
c2.metric("Regiones (filtro)", f"{df_f[col_region].nunique()}")
c3.metric("Instancias normalizadas (filtro)", f"{df_f['Instancia (Normalizada)'].nunique()}")

st.markdown("---")

# ---------------- 1) Resumen por región ----------------
st.subheader("📍 Resumen por región")
res_region = df_f.groupby(col_region).size().reset_index(name="Respuestas")
res_region["% del total"] = (res_region["Respuestas"] * 100 / res_region["Respuestas"].sum()).round().astype(int)
fila_total = pd.DataFrame([{col_region: "Total", "Respuestas": int(res_region["Respuestas"].sum()), "% del total": 100}])
res_region_tot = pd.concat([res_region, fila_total], ignore_index=True)

colA, colB = st.columns([1.1, 1])
with colA:
    st.dataframe(res_region_tot, use_container_width=True)
    st.download_button("⬇️ Descargar resumen por región (CSV)",
                       data=res_region_tot.to_csv(index=False).encode("utf-8"),
                       file_name="resumen_por_region.csv",
                       mime="text/csv")
with colB:
    fig_reg = px.bar(res_region, x=col_region, y="Respuestas", text="% del total",
                     title="Respuestas por región", labels={"Respuestas": "N° de respuestas", col_region: "Región"})
    fig_reg.update_traces(texttemplate="%{text}%", textposition="outside")
    fig_reg.update_layout(xaxis_title="", yaxis_title="Frecuencia", showlegend=False, margin=dict(t=60, r=20, b=20, l=20))
    st.plotly_chart(fig_reg, use_container_width=True)

# ---------------- 2) Análisis por preguntas ----------------
st.markdown("---")
st.subheader("📝 Análisis por preguntas")

excluir = {
    "ID", "Hora de inicio", "Hora de finalización",
    col_region, col_instancia, "Instancia (Normalizada)",
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

            st.download_button("⬇️ Descargar tabla (CSV)",
                               data=frec.to_csv(index=False).encode("utf-8"),
                               file_name=f"frecuencias_{q[:40].replace(' ', '_')}.csv",
                               mime="text/csv",
                               key=f"dl_{q}")

            st.plotly_chart(grafico_barras(frec, f"Distribución de respuestas — {q}"), use_container_width=True)

st.markdown("---")
st.caption("MINEDU · Dashboard GRD · Números y porcentajes incluyen fila Total.")
