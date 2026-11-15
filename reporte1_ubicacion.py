# -*- coding: utf-8 -*-
"""
REPORTE 1 - RESTAURANTES Y UBICACION   (Q4, Q17, Q20, Q25)
==========================================================
Cada grafico es una funcion que RECIBE un DataFrame y DEVUELVE una figura de plotly,
para usarla igual en este script (F5) o en la app de Streamlit.

Graficos:
  1. Q4   Podio de los 3 restaurantes con mas reseñas   (altura = reseñas, circulo = calificacion)
  2. Q17  Ranking mensual por pais                       (selector de pais, 🥇 y 🥈 de cada mes)
  3. Q20  Donut: % del encarecimiento por ciudad         (selector de pais)
  4. Q25  Explorador de restaurantes                     (filtros: ciudad, calificacion, fechas)

Codigos con leyenda: paises y monedas en español (Perú, "PEN · Sol peruano", ...).
"""
import json
import os
import textwrap
import webbrowser

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from conexion import (consulta, SALIDA, PALETA, NOMBRE_PAIS,
                      etiqueta_moneda, etiqueta_pais, corto)

# ----------------------------------------------------------------------
# CONSULTAS SQL (las tuyas; comentarios quitados)
# Q17 y Q20 llevan una columna extra (Currency_code) para mostrar la moneda.
# Q25 no usa SQL dinamico: se traen los restaurantes y sus fechas de cambio de
# precio, y el filtrado se hace en Python (Streamlit) o en el navegador (HTML).
# ----------------------------------------------------------------------
SQL_Q4 = """
SELECT TOP (3)
    r.Restaurant_ID,
    r.Restaurant_name,
    r.Review_count AS Total_resenas,
    r.Average_rating AS Calificacion_promedio
FROM RESTAURANTE AS r
WHERE r.Review_count IS NOT NULL
ORDER BY r.Review_count DESC,
         r.Average_rating DESC,
         r.Restaurant_ID;
"""

SQL_Q17 = """
WITH AumentoMensual AS (
    SELECT P.Country,
           P.Currency_code,
           R.Restaurant_ID,
           R.Restaurant_name,
           FORMAT(CAST(HP.Timestamp AS DATETIME2), 'yyyy-MM') AS Mes,
           ROUND(SUM(IM.Price - HP.Previous_price), 2)        AS MontoAumento
    FROM Historial_Precio AS HP
    JOIN Item_Menu   AS IM ON IM.Menu_ID      = HP.Menu_ID
    JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Pais        AS P  ON P.ISO_code      = R.ISO_code
    WHERE IM.Price > HP.Previous_price
    GROUP BY P.Country, P.Currency_code, R.Restaurant_ID, R.Restaurant_name,
             FORMAT(CAST(HP.Timestamp AS DATETIME2), 'yyyy-MM')
),
Ranking AS (
    SELECT Country, Currency_code, Mes, Restaurant_name, MontoAumento,
           RANK() OVER (PARTITION BY Country, Mes
                        ORDER BY MontoAumento DESC) AS Posicion
    FROM AumentoMensual
)
SELECT Country, Currency_code, Mes, Posicion, Restaurant_name, MontoAumento
FROM Ranking
WHERE Posicion <= 2
ORDER BY Country, Mes, Posicion;
"""

SQL_Q20 = """
WITH IncrementoCiudad AS (
    SELECT PA.Country,
           PA.Currency_code,
           C.ISO_code,
           C.City,
           SUM(IM.Price - HP.Previous_price) AS IncrementoCiudad
    FROM Historial_Precio AS HP
    JOIN Item_Menu   AS IM ON IM.Menu_ID      = HP.Menu_ID
    JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Ciudad      AS C  ON C.City          = R.City
                          AND C.ISO_code      = R.ISO_code
    JOIN Pais        AS PA ON PA.ISO_code     = C.ISO_code
    WHERE IM.Price > HP.Previous_price
    GROUP BY PA.Country, PA.Currency_code, C.ISO_code, C.City
)
SELECT Country,
       Currency_code,
       City,
       CAST(IncrementoCiudad AS DECIMAL(14,2))             AS IncrementoCiudad,
       FORMAT(IncrementoCiudad * 1.0
              / SUM(IncrementoCiudad) OVER (PARTITION BY ISO_code),
              'P1', 'en-US')                               AS PctEnPais
FROM IncrementoCiudad
ORDER BY Country, IncrementoCiudad DESC;
"""

SQL_Q25_RESTAURANTES = """
SELECT R.Restaurant_ID,
       R.Restaurant_name,
       R.City,
       PA.Country,
       R.Average_rating,
       R.Review_count
FROM Restaurante AS R
JOIN Pais        AS PA ON PA.ISO_code = R.ISO_code;
"""

# Dias en que cada restaurante registro cambios de precio (equivale al EXISTS de la Q25)
SQL_Q25_CAMBIOS = """
SELECT IM.Restaurant_ID,
       CAST(HP.Timestamp AS DATE) AS Fecha,
       COUNT(*)                   AS NumCambios
FROM Item_Menu        AS IM
JOIN Historial_Precio AS HP ON HP.Menu_ID = IM.Menu_ID
GROUP BY IM.Restaurant_ID, CAST(HP.Timestamp AS DATE);
"""

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
            "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _mes_es(mes):
    """'2023-06' -> 'Jun 2023'"""
    try:
        anio, m = str(mes).split("-")
        return f"{MESES_ES[int(m) - 1]} {anio}"
    except Exception:
        return str(mes)


def _titulo(texto, subtitulo):
    return f"<b>{texto}</b><br><sup>{subtitulo}</sup>"


# ----------------------------------------------------------------------
# CARGA DE DATOS
# ----------------------------------------------------------------------
def cargar_datos():
    """Ejecuta las consultas y deja los DataFrames listos para graficar."""
    q4 = consulta(SQL_Q4)
    for c in ["Total_resenas", "Calificacion_promedio"]:
        q4[c] = pd.to_numeric(q4[c], errors="coerce")

    q17 = consulta(SQL_Q17)
    q17["MontoAumento"] = pd.to_numeric(q17["MontoAumento"], errors="coerce")

    q20 = consulta(SQL_Q20)
    q20["IncrementoCiudad"] = pd.to_numeric(q20["IncrementoCiudad"], errors="coerce")

    q25_rest = consulta(SQL_Q25_RESTAURANTES)
    for c in ["Average_rating", "Review_count"]:
        q25_rest[c] = pd.to_numeric(q25_rest[c], errors="coerce")
    q25_cambios = consulta(SQL_Q25_CAMBIOS)
    q25_cambios["Fecha"] = pd.to_datetime(q25_cambios["Fecha"])

    return {"q4": q4, "q17": q17, "q20": q20,
            "q25_rest": q25_rest, "q25_cambios": q25_cambios}


# ----------------------------------------------------------------------
# GRAFICO 1 - Q4: PODIO DE LOS 3 RESTAURANTES CON MAS RESEÑAS
# ----------------------------------------------------------------------
COLOR_POS = {1: "#F5B800", 2: "#B8C2CC", 3: "#CD7F32"}       # oro, plata, bronce
TEXTO_POS = {1: "#1b1b1b", 2: "#1b1b1b", 3: "#ffffff"}
MEDALLA = {1: "🥇", 2: "🥈", 3: "🥉"}
NOMBRE_LUGAR = {1: "1.er lugar", 2: "2.º lugar", 3: "3.er lugar"}
X_POS = {2: 0.0, 1: 1.0, 3: 2.0}     # podio clasico: 2º izquierda, 1º centro, 3º derecha


def fig_q4_top_resenas(q4):
    """Podio: la ALTURA de cada bloque es el numero de reseñas (eje desde 0);
    el circulo blanco muestra la calificacion promedio del restaurante."""
    d = q4.reset_index(drop=True).head(3).copy()
    d["Puesto"] = d.index + 1
    maximo = float(d["Total_resenas"].max())
    x = [X_POS[p] for p in d["Puesto"]]
    colores = [COLOR_POS[p] for p in d["Puesto"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x, y=d["Total_resenas"], width=0.78, marker_color=colores,
        text=[f"<b>{v:,.0f}</b><br>reseñas" for v in d["Total_resenas"]],
        textposition="inside", insidetextanchor="end",
        textfont=dict(size=16, color=[TEXTO_POS[p] for p in d["Puesto"]]),
        customdata=d[["Restaurant_name", "Calificacion_promedio", "Restaurant_ID"]].to_numpy(),
        hovertemplate=("<b>%{customdata[0]}</b><br>Reseñas acumuladas: %{y:,.0f}"
                       "<br>Calificación promedio: %{customdata[1]:.2f}"
                       "<br>ID del restaurante: %{customdata[2]}<extra></extra>"),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=(d["Total_resenas"] * 0.42), mode="markers+text",
        marker=dict(size=84, color="white", line=dict(width=6, color=colores)),
        text=[f"⭐<br><b>{c:.1f}</b>" for c in d["Calificacion_promedio"]],
        textposition="middle center", textfont=dict(size=15, color="#2d3436"),
        hovertemplate="Calificación promedio: %{text}<extra></extra>", showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=d["Total_resenas"], mode="text", textposition="top center",
        text=[f"{MEDALLA[p]} <b>" + "<br>".join(textwrap.wrap(str(n), 20)) + "</b>"
              for p, n in zip(d["Puesto"], d["Restaurant_name"])],
        textfont=dict(size=15, color="#2d3436"), hoverinfo="skip", showlegend=False,
    ))
    fig.update_layout(
        title=dict(text=_titulo("🏅 Los 3 restaurantes con más reseñas",
                                "Premiación de aliados estratégicos · la altura es el número de reseñas "
                                "· el círculo muestra la calificación promedio (⭐)"),
                   x=0.01, font=dict(size=21)),
        template="plotly_white", height=580, showlegend=False,
        margin=dict(t=110, l=70, r=30, b=60),
        xaxis=dict(tickmode="array", tickvals=[0, 1, 2],
                   ticktext=[f"{MEDALLA[2]} {NOMBRE_LUGAR[2]}", f"{MEDALLA[1]} {NOMBRE_LUGAR[1]}",
                             f"{MEDALLA[3]} {NOMBRE_LUGAR[3]}"],
                   tickfont=dict(size=15), range=[-0.65, 2.65], showgrid=False),
        yaxis=dict(title="Reseñas acumuladas", range=[0, maximo * 1.38],
                   tickformat=",", zeroline=False),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 2 - Q17: RANKING MENSUAL POR PAIS (los 2 que mas subieron precios)
# ----------------------------------------------------------------------
NOMBRE_PUESTO = {1: "🥇 1.er puesto", 2: "🥈 2.º puesto"}


def fig_q17_ranking_mensual(q17):
    d = q17.copy()
    d["Mes"] = d["Mes"].astype(str)
    # Si hay empate en un puesto (RANK), se unen los nombres en una sola barra
    agr = (d.groupby(["Country", "Currency_code", "Mes", "Posicion"], as_index=False)
             .agg(Restaurante=("Restaurant_name", lambda s: " / ".join(sorted(set(s.astype(str))))),
                  Monto=("MontoAumento", "max")))
    paises = sorted(agr["Country"].unique(), key=etiqueta_pais)

    fig = go.Figure()
    grupos, info = [], []
    for i, pais in enumerate(paises):
        sub = agr[agr["Country"] == pais]
        moneda = sub["Currency_code"].iloc[0]
        meses = sorted(sub["Mes"].unique())
        info.append(dict(meses=[_mes_es(m) for m in meses], moneda=moneda,
                         maximo=float(sub["Monto"].max())))
        for pos in (1, 2):
            s = sub[sub["Posicion"] == pos].sort_values("Mes")
            fig.add_trace(go.Bar(
                y=[_mes_es(m) for m in s["Mes"]], x=s["Monto"], orientation="h",
                name=NOMBRE_PUESTO[pos], marker_color=COLOR_POS[pos],
                text=[f"{corto(r, 30)} · {v:,.2f}" for r, v in zip(s["Restaurante"], s["Monto"])],
                textposition="outside", cliponaxis=False, textfont=dict(size=12),
                customdata=s[["Restaurante"]].to_numpy(),
                hovertemplate=("<b>%{customdata[0]}</b><br>%{y}: aumento total de precios "
                               "%{x:,.2f} " + str(moneda) + "<extra></extra>"),
                visible=(i == 0),
            ))
            grupos.append(i)

    def alto(i):
        return 240 + 78 * len(info[i]["meses"])

    titulos = [_titulo(f"📈 ¿Quién subió más los precios cada mes? — {etiqueta_pais(p)}",
                       "Los 2 restaurantes con mayor aumento total de precios en cada mes · "
                       f"montos en {etiqueta_moneda(info[i]['moneda'])}")
               for i, p in enumerate(paises)]
    botones = [
        dict(label=f"País: {etiqueta_pais(p)}", method="update",
             args=[{"visible": [g == i for g in grupos]},
                   {"title.text": titulos[i], "yaxis.categoryarray": info[i]["meses"],
                    "xaxis.range": [0, info[i]["maximo"] * 1.75], "height": alto(i)}])
        for i, p in enumerate(paises)
    ]
    margen_t, margen_b = 170, 60
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.985, yanchor="top", font=dict(size=21)),
        updatemenus=[dict(buttons=botones, direction="down", showactive=True, x=0.0,
                          xanchor="left", y=1 + 95 / (alto(0) - margen_t - margen_b),
                          yanchor="top")],
        template="plotly_white", barmode="group", height=alto(0), bargap=0.25,
        margin=dict(t=margen_t, l=90, r=30, b=margen_b),
        yaxis=dict(autorange="reversed", categoryorder="array",
                   categoryarray=info[0]["meses"], tickfont=dict(size=13)),
        xaxis=dict(title="Aumento total de precios en el mes (moneda local)",
                   range=[0, info[0]["maximo"] * 1.75]),
        legend=dict(orientation="h", y=-0.04, x=0),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 3 - Q20: ¿QUE % DEL ENCARECIMIENTO DEL PAIS PONE CADA CIUDAD?
# ----------------------------------------------------------------------
def fig_q20_ciudades_pais(q20, max_ciudades=8):
    d = q20.copy()
    paises = sorted(d["Country"].unique(), key=etiqueta_pais)

    fig = go.Figure()
    grupos, titulos, centros = [], [], []
    for i, pais in enumerate(paises):
        s = d[d["Country"] == pais].sort_values("IncrementoCiudad", ascending=False)
        total = float(s["IncrementoCiudad"].sum())
        moneda = s["Currency_code"].iloc[0]

        if len(s) > max_ciudades:                       # muchas ciudades: se agrupan las menores
            top, resto = s.head(max_ciudades - 1), s.iloc[max_ciudades - 1:]
            etiquetas = list(top["City"]) + [f"Otras {len(resto)} ciudades"]
            valores = list(top["IncrementoCiudad"]) + [float(resto["IncrementoCiudad"].sum())]
            colores = [PALETA[k % len(PALETA)] for k in range(len(top))] + ["#B2BEC3"]
        else:
            etiquetas, valores = list(s["City"]), list(s["IncrementoCiudad"])
            colores = [PALETA[k % len(PALETA)] for k in range(len(s))]

        fig.add_trace(go.Pie(
            labels=etiquetas, values=valores, sort=False, hole=0.55, direction="clockwise",
            marker=dict(colors=colores, line=dict(color="white", width=3)),
            pull=[0.07] + [0] * (len(valores) - 1),     # la ciudad que mas concentra, destacada
            texttemplate="%{label}<br><b>%{percent:.1%}</b>", textposition="outside",
            textfont=dict(size=13),
            hovertemplate=("<b>%{label}</b><br>Incremento: %{value:,.2f} " + str(moneda)
                           + "<br>%{percent:.1%} del total del país<extra></extra>"),
            visible=(i == 0), showlegend=False,
        ))
        grupos.append(i)

        pct_top = valores[0] / total * 100 if total else 0
        titulos.append(_titulo(
            f"🏙️ ¿Dónde se concentra el encarecimiento en {etiqueta_pais(pais)}?",
            f"👑 {etiquetas[0]} concentra el {pct_top:.1f} % del aumento de precios del país "
            f"· total: {total:,.0f} {etiqueta_moneda(moneda)}"))
        centros.append(f"<b>{total:,.0f}</b><br><span style='font-size:13px'>{moneda}<br>"
                       "incremento total</span>")

    alto, margen_t, margen_b = 640, 150, 50
    fig.add_annotation(text=centros[0], x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=22, color="#2d3436"))
    botones = [
        dict(label=f"País: {etiqueta_pais(p)}", method="update",
             args=[{"visible": [g == i for g in grupos]},
                   {"title.text": titulos[i], "annotations[0].text": centros[i]}])
        for i, p in enumerate(paises)
    ]
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.985, yanchor="top", font=dict(size=21)),
        updatemenus=[dict(buttons=botones, direction="down", showactive=True, x=0.0,
                          xanchor="left", y=1 + 80 / (alto - margen_t - margen_b),
                          yanchor="top")],
        template="plotly_white", height=alto,
        margin=dict(t=margen_t, l=40, r=40, b=margen_b),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 4 - Q25: EXPLORADOR DE RESTAURANTES
# ----------------------------------------------------------------------
def filtrar_restaurantes(restaurantes, cambios, ciudad=None, calif_min=None,
                         fecha_ini=None, fecha_fin=None):
    """Equivale al SQL dinamico de la Q25: solo aplica los filtros que se pidan.
    Con fechas, deja los restaurantes con al menos un cambio de precio en el rango
    y agrega la columna CambiosEnRango."""
    f = restaurantes
    if ciudad:
        f = f[f["City"] == ciudad]
    if calif_min is not None:
        f = f[f["Average_rating"] >= calif_min]
    if fecha_ini is not None and fecha_fin is not None:
        c = cambios[(cambios["Fecha"] >= pd.Timestamp(fecha_ini))
                    & (cambios["Fecha"] <= pd.Timestamp(fecha_fin))]
        n = c.groupby("Restaurant_ID")["NumCambios"].sum().rename("CambiosEnRango")
        f = f.merge(n, left_on="Restaurant_ID", right_index=True, how="inner")
    return f.sort_values(["Average_rating", "Restaurant_name"], ascending=[False, True])


def fig_q25_ranking(df_filtrado, top=10):
    """Barras con los restaurantes mejor calificados que cumplen los filtros."""
    d = (df_filtrado.dropna(subset=["Average_rating"])
         .sort_values(["Average_rating", "Review_count", "Restaurant_name"],
                      ascending=[False, False, True]).head(top).copy())
    fig = go.Figure()
    if d.empty:
        fig.add_annotation(text="Ningún restaurante cumple estos filtros. Prueba ampliarlos.",
                           showarrow=False, font=dict(size=16, color="#636e72"))
        fig.update_layout(template="plotly_white", height=300,
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    d["Etiqueta"] = [f"{i + 1}. {corto(n, 28)} · {corto(c, 16)}"
                     for i, (n, c) in enumerate(zip(d["Restaurant_name"], d["City"]))]
    d["PaisES"] = d["Country"].map(etiqueta_pais)
    if "CambiosEnRango" not in d.columns:
        d["CambiosEnRango"] = float("nan")
    for k, pais in enumerate(sorted(d["PaisES"].unique())):
        s = d[d["PaisES"] == pais]
        fig.add_trace(go.Bar(
            x=s["Average_rating"], y=s["Etiqueta"], orientation="h", name=pais,
            marker_color=PALETA[k % len(PALETA)],
            text=[f"⭐ {r:.1f} · {n:,.0f} reseñas" for r, n in zip(s["Average_rating"], s["Review_count"].fillna(0))],
            textposition="inside", insidetextanchor="end", textfont=dict(color="white", size=13),
            customdata=s[["Restaurant_name", "City", "PaisES", "Review_count",
                          "CambiosEnRango"]].to_numpy(),
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}, %{customdata[2]}"
                           "<br>Calificación: %{x:.2f}<br>Reseñas: %{customdata[3]:,.0f}"
                           "<br>Cambios de precio en el rango: %{customdata[4]}<extra></extra>"),
        ))
    fig.update_layout(
        title=dict(text=_titulo(f"🍴 Los {len(d)} restaurantes mejor calificados con estos filtros",
                                "El color indica el país"), x=0.01, font=dict(size=20)),
        barmode="overlay", template="plotly_white", height=130 + 52 * len(d),
        margin=dict(t=100, l=20, r=20, b=40),
        yaxis=dict(autorange="reversed", categoryorder="array",
                   categoryarray=list(d["Etiqueta"]), automargin=True),
        xaxis=dict(title="Calificación promedio (0 a 5)", range=[0, 5.2]),
        legend=dict(orientation="h", y=-0.12, x=0),
    )
    return fig


PLANTILLA_EXPLORADOR = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Explorador de restaurantes</title>
<style>
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f6fa;margin:0;padding:24px;color:#2d3436}
  h1{margin:0 0 4px} .sub{color:#636e72;margin:0 0 18px}
  .panel{background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.06);
         display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}
  label{font-size:13px;font-weight:600;display:block;margin-bottom:6px}
  select,input[type=date]{width:100%;padding:8px;border-radius:8px;border:1px solid #dfe6e9;box-sizing:border-box}
  input[type=range]{width:100%}
  .chk label{font-weight:400;display:flex;gap:8px;align-items:center;font-size:14px}
  .kpis{display:flex;gap:14px;margin:16px 0;flex-wrap:wrap}
  .kpi{background:#fff;border-radius:14px;padding:14px 22px;box-shadow:0 2px 10px rgba(0,0,0,.06);min-width:150px}
  .kpi b{display:block;font-size:28px} .kpi span{color:#636e72;font-size:13px}
  .card{background:#fff;border-radius:14px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:16px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;border-bottom:2px solid #dfe6e9;padding:8px}
  td{padding:8px;border-bottom:1px solid #f1f2f6}
  .estrellas{color:#F5B800;letter-spacing:1px}
  .nota{color:#636e72;font-size:12px;padding:6px 8px}
</style>
<script>__PLOTLY__</script>
</head>
<body>
<h1>🍴 Explorador de restaurantes</h1>
<p class="sub">Elige una ciudad, una calificación mínima y un rango de fechas con cambios de precio. Los resultados se actualizan al instante.</p>

<div class="panel">
  <div><label>Ciudad</label><select id="ciu"></select></div>
  <div><label>Calificación mínima: <span id="vCal"></span></label>
       <input type="range" id="sCal" min="0" max="5" step="0.1" value="0"></div>
  <div><label>Cambios de precio desde</label><input type="date" id="fIni"></div>
  <div><label>Cambios de precio hasta</label><input type="date" id="fFin"></div>
  <div class="chk"><label><input type="checkbox" id="chkFecha" checked>
       Solo restaurantes con cambios de precio en ese rango</label></div>
</div>

<div class="kpis" id="kpis"></div>
<div class="card">
  <div id="grafico"></div>
  <p id="vacio" style="display:none;padding:30px;text-align:center;color:#636e72;font-size:16px"></p>
</div>
<div class="card"><h3 style="margin:8px">Detalle de los restaurantes</h3><div id="tabla"></div>
  <p class="nota">⭐ Calificación promedio · 🔄 Cambios de precio registrados dentro del rango de fechas · s/d = sin dato</p></div>

<script>
const REST = __REST__;
const CAMBIOS = __CAMBIOS__;
const NOM_PAIS = __NOMPAIS__;
const PAL = __PALETA__;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const corto = (t, n) => { t = String(t); return t.length <= n ? t : t.slice(0, n - 1) + "…"; };
const pais = p => NOM_PAIS[p] || p;
const estrellas = r => r === null ? "s/d" : "★".repeat(Math.round(r)) + "☆".repeat(5 - Math.round(r));

const paises = [...new Set(REST.map(d => d.Country))].sort((a, b) => pais(a).localeCompare(pais(b), "es"));
const colorPais = {}; paises.forEach((p, i) => colorPais[p] = PAL[i % PAL.length]);
const ciudades = [...new Set(REST.map(d => d.City))].sort((a, b) => String(a).localeCompare(String(b), "es"));

// fechas con cambios de precio (dias desde 1970-01-01)
let minDia = Infinity, maxDia = -Infinity;
Object.values(CAMBIOS).forEach(a => { for (let i = 0; i < a.length; i += 2) {
  if (a[i] < minDia) minDia = a[i]; if (a[i] > maxDia) maxDia = a[i]; } });
if (!isFinite(minDia)) { minDia = 19358; maxDia = 19722; }      // 2023-01-01 a 2023-12-31
const iso = dia => new Date(dia * 86400000).toISOString().slice(0, 10);
const aDia = s => Math.floor(Date.parse(s + "T00:00:00Z") / 86400000);
$("fIni").value = iso(minDia); $("fFin").value = iso(maxDia);
$("fIni").min = $("fFin").min = iso(minDia); $("fIni").max = $("fFin").max = iso(maxDia);

$("ciu").innerHTML = '<option value="">Todas las ciudades</option>' +
  ciudades.map(c => '<option value="' + esc(c) + '">' + esc(c) + '</option>').join("");

function contar(id, d1, d2) {
  const a = CAMBIOS[id]; if (!a) return 0;
  let t = 0; for (let i = 0; i < a.length; i += 2) if (a[i] >= d1 && a[i] <= d2) t += a[i + 1];
  return t;
}

function mostrarVacio(msg) {
  $("grafico").style.display = "none"; $("vacio").style.display = "block"; $("vacio").textContent = msg;
  $("tabla").innerHTML = "";
}

function actualizar() {
  const ciudad = $("ciu").value, cmin = +$("sCal").value, usaFecha = $("chkFecha").checked;
  const d1 = aDia($("fIni").value), d2 = aDia($("fFin").value);
  $("vCal").textContent = cmin > 0 ? cmin.toFixed(1) + " ⭐ o más" : "sin mínimo";

  if (isNaN(d1) || isNaN(d2) || d1 > d2) {
    $("kpis").innerHTML = "";
    mostrarVacio("La fecha inicial debe ser anterior o igual a la fecha final.");
    return;
  }

  const lista = REST.map(d => Object.assign({}, d, {Cambios: contar(d.Restaurant_ID, d1, d2)})).filter(d =>
    (!ciudad || d.City === ciudad) &&
    (cmin === 0 || (d.Average_rating !== null && d.Average_rating >= cmin)) &&
    (!usaFecha || d.Cambios > 0)
  );

  const notas = lista.map(d => d.Average_rating).filter(x => x !== null);
  const sum = a => a.reduce((x, y) => x + y, 0);
  $("kpis").innerHTML =
    '<div class="kpi"><b>' + lista.length + '</b><span>restaurantes encontrados</span></div>' +
    '<div class="kpi"><b>' + (notas.length ? (sum(notas) / notas.length).toFixed(2) : "s/d") + '</b><span>calificación promedio</span></div>' +
    '<div class="kpi"><b>' + sum(lista.map(d => d.Review_count || 0)).toLocaleString("es") + '</b><span>reseñas en total</span></div>' +
    '<div class="kpi"><b>' + sum(lista.map(d => d.Cambios)).toLocaleString("es") + '</b><span>cambios de precio en el rango</span></div>';

  const orden = lista.slice().sort((a, b) =>
    ((b.Average_rating === null ? -1 : b.Average_rating) - (a.Average_rating === null ? -1 : a.Average_rating)) ||
    ((b.Review_count || 0) - (a.Review_count || 0)) ||
    String(a.Restaurant_name).localeCompare(String(b.Restaurant_name)));
  const top = orden.filter(d => d.Average_rating !== null).slice(0, 10);

  if (lista.length === 0 || top.length === 0) {
    mostrarVacio("Ningún restaurante cumple estos filtros. Prueba ampliarlos.");
    return;
  }
  $("vacio").style.display = "none"; $("grafico").style.display = "block";

  const etiquetas = top.map((d, i) => (i + 1) + ". " + corto(d.Restaurant_name, 28) + " · " + corto(d.City, 16));
  const trazas = paises.map(p => {
    const idx = top.map((d, i) => i).filter(i => top[i].Country === p);
    return {
      type: "bar", orientation: "h", name: pais(p),
      x: idx.map(i => top[i].Average_rating), y: idx.map(i => etiquetas[i]),
      marker: {color: colorPais[p]},
      text: idx.map(i => "⭐ " + top[i].Average_rating.toFixed(1) + " · " + (top[i].Review_count || 0).toLocaleString("es") + " reseñas"),
      textposition: "inside", insidetextanchor: "end", textfont: {color: "white", size: 13},
      hovertext: idx.map(i => "<b>" + esc(top[i].Restaurant_name) + "</b><br>" + esc(top[i].City) + ", " + esc(pais(top[i].Country)) +
                              "<br>Calificación: " + top[i].Average_rating.toFixed(2) +
                              "<br>Reseñas: " + (top[i].Review_count || 0).toLocaleString("es") +
                              "<br>Cambios de precio en el rango: " + top[i].Cambios),
      hoverinfo: "text"
    };
  });
  Plotly.react("grafico", trazas, {
    template: "plotly_white", barmode: "overlay", height: 130 + 52 * top.length,
    margin: {t: 20, l: 20, r: 20, b: 50},
    yaxis: {autorange: "reversed", categoryorder: "array", categoryarray: etiquetas, automargin: true},
    xaxis: {title: "Calificación promedio (0 a 5)", range: [0, 5.2]},
    legend: {orientation: "h", y: -0.12, x: 0}
  }, {responsive: true});

  $("tabla").innerHTML =
    '<table><tr><th>#</th><th>Restaurante</th><th>Ciudad</th><th>País</th><th>Calificación</th><th>Reseñas</th><th>🔄 Cambios</th></tr>' +
    orden.slice(0, 15).map((d, i) => '<tr><td>' + (i + 1) + '</td><td><b>' + esc(d.Restaurant_name) + '</b></td><td>' + esc(d.City) +
      '</td><td>' + esc(pais(d.Country)) + '</td><td><span class="estrellas">' + estrellas(d.Average_rating) + '</span> ' +
      (d.Average_rating === null ? "" : d.Average_rating.toFixed(1)) + '</td><td>' + (d.Review_count === null ? "s/d" : d.Review_count.toLocaleString("es")) +
      '</td><td>' + d.Cambios + '</td></tr>').join("") + '</table>';
}

["ciu", "sCal", "fIni", "fFin", "chkFecha"].forEach(id => $(id).addEventListener("input", actualizar));
actualizar();
</script>
</body>
</html>
"""


def html_explorador_restaurantes(restaurantes, cambios):
    """Devuelve el HTML completo del explorador (Plotly embebido, funciona sin internet)."""
    cam = cambios.copy()
    cam["Dia"] = (pd.to_datetime(cam["Fecha"]) - pd.Timestamp("1970-01-01")).dt.days
    mapa = {}
    for rid, g in cam.groupby("Restaurant_ID"):
        plano = []
        for dia, n in zip(g["Dia"], g["NumCambios"]):
            plano += [int(dia), int(n)]
        mapa[str(rid)] = plano

    rest_json = (restaurantes.to_json(orient="records", force_ascii=False)
                 .replace("</", "<\\/"))
    # Orden: primero los datos, ultimo la libreria (para no reescanear sus 3 MB)
    return (PLANTILLA_EXPLORADOR.replace("__REST__", rest_json)
            .replace("__CAMBIOS__", json.dumps(mapa))
            .replace("__NOMPAIS__", json.dumps(NOMBRE_PAIS, ensure_ascii=False))
            .replace("__PALETA__", json.dumps(PALETA))
            .replace("__PLOTLY__", get_plotlyjs()))


# ----------------------------------------------------------------------
# EJECUCION INDEPENDIENTE (F5 en Spyder)
# ----------------------------------------------------------------------
def generar_html(abrir=True):
    datos = cargar_datos()
    rutas = []

    figuras = {
        "1_1_podio_resenas": fig_q4_top_resenas(datos["q4"]),
        "1_2_ranking_mensual_pais": fig_q17_ranking_mensual(datos["q17"]),
        "1_3_ciudades_por_pais": fig_q20_ciudades_pais(datos["q20"]),
    }
    for nombre, fig in figuras.items():
        ruta = os.path.join(SALIDA, f"Reporte{nombre}.html")
        fig.write_html(ruta, include_plotlyjs=True)
        rutas.append(ruta)
        print("Guardado:", ruta)

    ruta = os.path.join(SALIDA, "Reporte1_4_explorador_restaurantes.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html_explorador_restaurantes(datos["q25_rest"], datos["q25_cambios"]))
    rutas.append(ruta)
    print("Guardado:", ruta)

    if abrir:
        for r in rutas:
            webbrowser.open("file:///" + r.replace("\\", "/"))


if __name__ == "__main__":
    generar_html()
