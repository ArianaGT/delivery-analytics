# -*- coding: utf-8 -*-
"""
app.py - PANEL DE ANALISIS: RESTAURANTES, PRECIOS Y SERVICIO  (Streamlit)
=========================================================================
Junta los 4 reportes en pestañas. Cada reporte vive en su propio archivo y solo
entrega DataFrames y figuras; esta app los muestra y agrega los filtros como controles.

  📍 Reporte 1   reporte1_ubicacion.py     (Q4, Q17, Q20, Q25)
  🏆 Reporte 2A  reporte2a_productos.py    (Q16, Q21, Q26)
  🚦 Reporte 2B  reporte2b_servicio.py     (Q23, Q24)
  📈 Reporte 3   reporte3_trazabilidad.py  (Q18, Q19, Q22)

Instalar (una sola vez):   %pip install streamlit
Ejecutar (en una terminal, dentro de esta carpeta):
    python -m streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

from conexion import SERVIDOR, BASE, etiqueta_moneda, etiqueta_pais
import reporte1_ubicacion as r1
import reporte2a_productos as r2a
import reporte2b_servicio as r2b
import reporte3_trazabilidad as r3

st.set_page_config(page_title="Delivery Analytics", page_icon="🍽️", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; }
      [data-testid="stMetric"] {
          border: 1px solid rgba(128,128,128,.28); border-radius: 14px; padding: 12px 18px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------------
# CARGA DE DATOS (cada reporte se consulta una sola vez y queda en memoria)
# ----------------------------------------------------------------------
@st.cache_data(show_spinner="Consultando SQL Server (Reporte 1)…")
def datos_r1():
    return r1.cargar_datos()


@st.cache_data(show_spinner="Consultando SQL Server (Reporte 2A)…")
def datos_r2a():
    return r2a.cargar_datos()


@st.cache_data(show_spinner="Consultando SQL Server (Reporte 2B)…")
def datos_r2b():
    return r2b.cargar_datos()


@st.cache_data(show_spinner="Consultando SQL Server (Reporte 3)…")
def datos_r3():
    return r3.cargar_datos()


def cargar(nombre, funcion):
    """Si un reporte falla (por ejemplo, un nombre de columna), los demas siguen funcionando."""
    try:
        return funcion()
    except Exception as e:
        st.error(f"No se pudieron cargar los datos de **{nombre}**.\n\n`{type(e).__name__}: {e}`")
        return None


def mostrar(fig):
    """theme=None respeta los colores y estilos que definimos en cada grafico."""
    st.plotly_chart(fig, theme=None)


def estrellas(r):
    if pd.isna(r):
        return "s/d"
    n = int(round(float(r)))
    return "★" * n + "☆" * (5 - n) + f" {float(r):.1f}"


# ----------------------------------------------------------------------
# REPORTE 1 - RESTAURANTES Y UBICACION
# ----------------------------------------------------------------------
def render_reporte1(d):
    rest, cambios = d["q25_rest"], d["q25_cambios"]

    a, b, c, e = st.columns(4)
    a.metric("Restaurantes", f"{len(rest):,}")
    b.metric("Países", f"{rest['Country'].nunique():,}")
    c.metric("Ciudades", f"{rest['City'].nunique():,}")
    e.metric("Calificación promedio", f"{rest['Average_rating'].mean():.2f} ⭐")

    st.divider()
    st.caption("Q4 · Premiación anual de aliados estratégicos")
    mostrar(r1.fig_q4_top_resenas(d["q4"]))

    st.divider()
    st.caption("Q17 · Pricing: ¿qué restaurantes ajustan sus precios de forma más agresiva? "
               "Usa el menú del gráfico para cambiar de país.")
    mostrar(r1.fig_q17_ranking_mensual(d["q17"]))

    st.divider()
    st.caption("Q20 · Gerencia General: ¿dónde se concentra el encarecimiento? "
               "Usa el menú del gráfico para cambiar de país.")
    mostrar(r1.fig_q20_ciudades_pais(d["q20"]))

    st.divider()
    st.subheader("🍴 Explorador de restaurantes")
    st.caption("Q25 · Business Intelligence: filtra por ciudad, calificación mínima y fechas "
               "con cambios de precio.")

    if cambios.empty:
        fmin, fmax = date(2023, 1, 1), date(2023, 12, 31)
    else:
        fmin, fmax = cambios["Fecha"].min().date(), cambios["Fecha"].max().date()

    f1, f2, f3 = st.columns([1, 1, 1.3])
    ciudad = f1.selectbox("Ciudad", ["Todas"] + sorted(rest["City"].dropna().unique().tolist()))
    calif = f2.slider("Calificación mínima", 0.0, 5.0, 0.0, 0.1)
    rango = f3.date_input("Rango de fechas de cambios de precio", value=(fmin, fmax),
                          min_value=fmin, max_value=fmax)
    usar_fecha = st.checkbox("Solo restaurantes con cambios de precio en ese rango", value=True)

    fi = ff = None
    if usar_fecha:
        if isinstance(rango, (tuple, list)) and len(rango) == 2:
            fi, ff = rango
        else:
            st.info("Elige también la fecha final del rango.")

    filtrado = r1.filtrar_restaurantes(
        rest, cambios,
        ciudad=None if ciudad == "Todas" else ciudad,
        calif_min=calif if calif > 0 else None,
        fecha_ini=fi, fecha_fin=ff,
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Restaurantes encontrados", f"{len(filtrado):,}")
    k2.metric("Calificación promedio",
              f"{filtrado['Average_rating'].mean():.2f} ⭐" if len(filtrado) else "s/d")
    k3.metric("Reseñas en total", f"{int(filtrado['Review_count'].fillna(0).sum()):,}")
    k4.metric("Cambios de precio en el rango",
              f"{int(filtrado['CambiosEnRango'].sum()):,}" if "CambiosEnRango" in filtrado else "—")

    mostrar(r1.fig_q25_ranking(filtrado))

    if len(filtrado):
        t = pd.DataFrame({
            "Restaurante": filtrado["Restaurant_name"],
            "Ciudad": filtrado["City"],
            "País": filtrado["Country"].map(etiqueta_pais),
            "Calificación": filtrado["Average_rating"].map(estrellas),
            "Reseñas": filtrado["Review_count"],
        })
        if "CambiosEnRango" in filtrado:
            t["🔄 Cambios en el rango"] = filtrado["CambiosEnRango"]
        st.dataframe(t.head(20), hide_index=True)
        st.caption("Se muestran los 20 mejor calificados.")


# ----------------------------------------------------------------------
# REPORTE 2A - PRODUCTOS Y PRECIOS
# ----------------------------------------------------------------------
def dieta_txt(fila):
    partes = []
    if fila["Vegetarian"] == 1:
        partes.append("🥕 Vegetariano")
    if fila["Vegan"] == 1:
        partes.append("🌱 Vegano")
    if fila["Gluten_free"] == 1:
        partes.append("🌾 Sin gluten")
    return " · ".join(partes) if partes else "—"


def render_reporte2a(d):
    st.caption("Q16 · Dirección Comercial: productos premium de la app. "
               "Usa el menú del gráfico para cambiar de moneda.")
    mostrar(r2a.fig_q16_podio(d["q16"]))

    st.divider()
    st.caption("Q21 · Dirección Ejecutiva: precio promedio por categoría y región.")
    mostrar(r2a.fig_q21_mapa_calor(d["q21"]))

    st.divider()
    st.subheader("🍽️ Explorador de platillos")
    st.caption("Q26 · Producto: filtra por categoría, moneda, precio, calorías y opciones de dieta. "
               "Los precios solo se comparan dentro de una misma moneda.")

    q26 = d["q26"]
    monedas = sorted(q26["Currency_code"].dropna().unique().tolist())
    cats = sorted(q26["Categoria"].dropna().unique().tolist())
    moneda_ini = monedas.index(q26["Currency_code"].value_counts().idxmax())

    f1, f2 = st.columns(2)
    categoria = f1.selectbox("Categoría", ["Todas"] + cats)
    moneda = f2.selectbox("Moneda", monedas, index=moneda_ini, format_func=etiqueta_moneda)

    sub = q26[q26["Currency_code"] == moneda]
    precio_tope = max(float(sub["Price"].max()), 1.0)
    cal_tope = q26["Calories"].max()

    g1, g2 = st.columns(2)
    precio_max = g1.slider(f"Precio máximo ({moneda})", 0.0, precio_tope, precio_tope,
                           key=f"precio_{moneda}")
    cal_max = None
    if pd.notna(cal_tope) and cal_tope > 0:
        if g2.checkbox("Limitar calorías"):
            cal_max = g2.slider("Calorías máximas", 0, int(cal_tope), int(cal_tope), step=10)

    h1, h2, h3 = st.columns(3)
    veg = h1.checkbox("🥕 Vegetariano")
    vegano = h2.checkbox("🌱 Vegano")
    gluten = h3.checkbox("🌾 Sin gluten")

    filtrado = r2a.filtrar_platillos(
        q26, categoria=None if categoria == "Todas" else categoria, moneda=moneda,
        precio_max=precio_max, calorias_max=cal_max,
        vegetariano=veg, vegano=vegano, sin_gluten=gluten,
    )

    k1, k2, k3 = st.columns(3)
    k1.metric("Platillos encontrados", f"{len(filtrado):,}")
    k2.metric(f"Precio promedio ({moneda})",
              f"{filtrado['Price'].mean():,.2f}" if len(filtrado) else "s/d")
    k3.metric("Calorías promedio",
              f"{filtrado['Calories'].mean():,.0f}" if filtrado["Calories"].notna().any() else "s/d")

    mostrar(r2a.fig_q26_ranking(filtrado, moneda))

    if len(filtrado):
        top = filtrado.sort_values(["Price", "Menu_ID"], ascending=[False, True]).head(10)
        t = pd.DataFrame({
            "Platillo": top["Item_name"],
            "Categoría": top["Categoria"],
            f"Precio ({moneda})": top["Price"],
            "Calorías": top["Calories"],
            "Dieta": top.apply(dieta_txt, axis=1),
            "Restaurante": top["Restaurant_name"],
            "Ciudad": top["City"],
        })
        st.dataframe(t, hide_index=True)
        st.caption("Se muestran los 10 platillos más caros que cumplen los filtros.")


# ----------------------------------------------------------------------
# REPORTE 2B - CONDICIONES DEL SERVICIO
# ----------------------------------------------------------------------
def render_reporte2b(d):
    q24 = d["q24"].set_index("NivelRiesgo")["NumRestaurantes"]
    total = int(q24.sum())
    alto = int(q24.get("Alto", 0))

    a, b, c = st.columns(3)
    a.metric("Restaurantes con delivery", f"{total:,}")
    b.metric("En riesgo alto 🔴", f"{alto:,}")
    c.metric("% en riesgo alto", f"{alto / total:.1%}" if total else "s/d")

    st.divider()
    st.caption("Q23 · Cierre operativo: aumentos de precio acumulados del 1 al 15 de diciembre de 2023. "
               "Usa el menú del gráfico para cambiar de moneda.")
    mostrar(r2b.fig_q23_modalidades(d["q23"]))

    st.divider()
    st.caption("Q24 · Riesgo Operativo: nivel de servicio del delivery según el % de cancelación.")
    mostrar(r2b.fig_q24_riesgo(d["q24"]))


# ----------------------------------------------------------------------
# REPORTE 3 - TRAZABILIDAD DE PRECIOS
# ----------------------------------------------------------------------
def render_reporte3(d):
    st.caption("Q18 · Producto: ¿el encarecimiento de cada categoría se acelera o se frena?")
    mostrar(r3.fig_q18(d["q18"]))

    st.divider()
    st.caption("Q19 · Finanzas: ritmo semanal de los ajustes de precio en 2023. "
               "Usa el menú del gráfico para cambiar de moneda.")
    mostrar(r3.fig_q19_semanal(d["q19"]))

    st.divider()
    st.caption("Q19 · Todas las monedas en una misma escala (% del aumento anual ya aplicado). "
               "Clic en la leyenda para ocultar una moneda; doble clic para aislarla.")
    mostrar(r3.fig_q19_comparado(d["q19"]))

    st.divider()
    st.caption("Q22 · Finanzas: crecimiento acumulado del año, mes a mes, por región. "
               "Usa el menú del gráfico para cambiar de moneda.")
    mostrar(r3.fig_q22(d["q22"]))


# ----------------------------------------------------------------------
# PAGINA PRINCIPAL
# ----------------------------------------------------------------------
st.title("🍽️ Panel de análisis: restaurantes, precios y servicio")
st.caption("Reportes interactivos con Python, SQL Server y Plotly · "
           "pasa el cursor sobre los gráficos para ver el detalle")

tab1, tab2, tab3, tab4 = st.tabs([
    "📍 Restaurantes y ubicación",
    "🏆 Productos y precios",
    "🚦 Condiciones del servicio",
    "📈 Trazabilidad de precios",
])

with tab1:
    d1 = cargar("el Reporte 1", datos_r1)
    if d1:
        render_reporte1(d1)

with tab2:
    d2a = cargar("el Reporte 2A", datos_r2a)
    if d2a:
        render_reporte2a(d2a)

with tab3:
    d2b = cargar("el Reporte 2B", datos_r2b)
    if d2b:
        render_reporte2b(d2b)

with tab4:
    d3 = cargar("el Reporte 3", datos_r3)
    if d3:
        render_reporte3(d3)


# ----------------------------------------------------------------------
# BARRA LATERAL: conexion, actualizar y glosarios (leyendas de los codigos)
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Panel")
    st.caption(f"Base de datos **{BASE}** en `{SERVIDOR}`")
    if st.button("🔄 Actualizar datos"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("📖 Glosario")

    if d2a:
        with st.expander("Monedas en los datos"):
            codigos = sorted(d2a["q16"]["Currency_code"].dropna().unique().tolist())
            st.markdown("\n".join(f"- {etiqueta_moneda(c)}" for c in codigos))

    with st.expander("Niveles de riesgo del delivery"):
        st.markdown("\n".join(f"- {r2b.LEYENDA_RIESGO[n]}" for n in r2b.ORDEN_RIESGO))

    with st.expander("Modalidades de atención"):
        st.markdown("\n".join(f"- {r2b.MAP_MOD[m]}" for m in r2b.ORDEN_MOD))

    with st.expander("Tendencia del aumento de precios"):
        st.markdown("- 🔴 **Se acelera**: el aumento promedio fue mayor que el mes anterior\n"
                    "- 🟢 **Se frena**: el aumento fue menor que el mes anterior\n"
                    "- ⚪ **Estable** o sin mes anterior para comparar")
