# -*- coding: utf-8 -*-
"""
REPORTE 2A - PRODUCTOS Y PRECIOS   (Q16, Q21, Q26)
==================================================
Cada grafico es una funcion que RECIBE un DataFrame y DEVUELVE una figura de plotly,
para usarla igual en este script (F5) o en la app de Streamlit.

Graficos:
  1. Q16  Podio de platillos premium   -> circulos 🥇🥈🥉 con selector de moneda
  2. Q21  Mapa de calor de precios     -> region x categoria
  3. Q26  Explorador de platillos      -> filtros + ranking de los 10 mas caros

Codigos con leyenda: las monedas se muestran como "PEN · Sol peruano" y las
categorias en español (Bebidas, Postres, Platos fuertes, Entradas).
"""
import json
import math
import os
import webbrowser

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.offline import get_plotlyjs

from conexion import (consulta, SALIDA, ES_CAT, PALETA, NOMBRE_MONEDA,
                      etiqueta_moneda, etiqueta_region, corto)

# ----------------------------------------------------------------------
# CONSULTAS SQL (las tuyas; Q26 sin SQL dinamico: se filtra en Python/navegador)
# ----------------------------------------------------------------------
SQL_Q16 = """
WITH PlatillosRankeados AS (
    SELECT P.Currency_code,
           IM.Food_category,
           IM.Menu_ID,
           IM.Item_name,
           IM.Price,
           R.Restaurant_name,
           R.Average_rating,
           ROW_NUMBER() OVER (
               PARTITION BY P.Currency_code, IM.Food_category
               ORDER BY IM.Price DESC,
                        R.Average_rating DESC,
                        IM.Menu_ID ASC
           ) AS Posicion
    FROM Item_Menu   AS IM
    JOIN Restaurante AS R ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Pais        AS P ON P.ISO_code      = R.ISO_code
)
SELECT Currency_code, Food_category, Posicion, Item_name, Price,
       Restaurant_name, Average_rating
FROM PlatillosRankeados
WHERE Posicion <= 3
ORDER BY Currency_code, Food_category, Posicion;
"""

SQL_Q21 = """
SELECT Region,
       Currency_code,
       CAST(ISNULL([Beverage], 0) AS DECIMAL(10,2)) AS Beverage,
       CAST(ISNULL([Dessert],  0) AS DECIMAL(10,2)) AS Dessert,
       CAST(ISNULL([Main],     0) AS DECIMAL(10,2)) AS Main,
       CAST(ISNULL([Starter],  0) AS DECIMAL(10,2)) AS Starter
FROM (
    SELECT PA.Region, PA.Currency_code, IM.Food_category, IM.Price
    FROM Item_Menu   AS IM
    JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Pais        AS PA ON PA.ISO_code     = R.ISO_code
) AS Origen
PIVOT (
    AVG(Price)
    FOR Food_category IN ([Beverage], [Dessert], [Main], [Starter])
) AS P
ORDER BY Region, Currency_code;
"""

SQL_Q26 = """
SELECT IM.Menu_ID, IM.Item_name, IM.Food_category, IM.Price,
       PA.Currency_code, IM.Calories,
       IM.Vegetarian, IM.Vegan, IM.Gluten_free,
       R.Restaurant_name, R.City
FROM Item_Menu   AS IM
JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
JOIN Pais        AS PA ON PA.ISO_code     = R.ISO_code;
"""

COLOR_CATEGORIA = {"Bebidas": "#2E86DE", "Postres": "#E84393",
                   "Platos fuertes": "#F39C12", "Entradas": "#27AE60"}


# ----------------------------------------------------------------------
# CARGA DE DATOS
# ----------------------------------------------------------------------
def cargar_datos():
    """Ejecuta las 3 consultas y deja los DataFrames listos para graficar."""
    q16 = consulta(SQL_Q16)
    q21 = consulta(SQL_Q21)
    q26 = consulta(SQL_Q26)

    q16["Categoria"] = q16["Food_category"].map(lambda c: ES_CAT.get(c, c))
    for c in ["Price", "Average_rating"]:
        q16[c] = pd.to_numeric(q16[c], errors="coerce")

    q26["Categoria"] = q26["Food_category"].map(lambda c: ES_CAT.get(c, c))
    for c in ["Price", "Calories"]:
        q26[c] = pd.to_numeric(q26[c], errors="coerce")
    for c in ["Vegetarian", "Vegan", "Gluten_free"]:
        q26[c] = pd.to_numeric(q26[c], errors="coerce").fillna(0).astype(int)

    return {"q16": q16, "q21": q21, "q26": q26}


def _titulo(texto, subtitulo):
    return f"<b>{texto}</b><br><sup>{subtitulo}</sup>"


def _menu_monedas(monedas, grupos, titulos, y):
    """Menu desplegable que muestra solo las trazas de la moneda elegida."""
    botones = [
        dict(label=f"Moneda: {etiqueta_moneda(mon)}", method="update",
             args=[{"visible": [g == i for g in grupos]}, {"title.text": tit}])
        for i, (mon, tit) in enumerate(zip(monedas, titulos))
    ]
    return dict(buttons=botones, direction="down", showactive=True,
                x=0.0, xanchor="left", y=y, yanchor="top")


def _precio_txt(p):
    return f"{p:,.0f}" if p >= 1000 else f"{p:,.2f}"


# ----------------------------------------------------------------------
# GRAFICO 1 - Q16: PODIO DE PLATILLOS PREMIUM (circulos)
# ----------------------------------------------------------------------
COLOR_POS = {1: "#F5B800", 2: "#B8C2CC", 3: "#CD7F32"}       # oro, plata, bronce
TEXTO_POS = {1: "#1b1b1b", 2: "#1b1b1b", 3: "#ffffff"}
MEDALLA = {1: "🥇", 2: "🥈", 3: "🥉"}
# Disposicion de podio clasico: 2º a la izquierda, 1º al centro, 3º a la derecha
X_POS = {2: 0.0, 1: 1.0, 3: 2.0}
Y_POS = {1: 1.00, 2: 0.78, 3: 0.60}
TAM_POS = {1: 104, 2: 88, 3: 76}


def fig_q16_podio(q16):
    monedas = sorted(q16["Currency_code"].unique())
    cats = sorted(q16["Categoria"].unique())
    n_cols = 2
    n_filas = math.ceil(len(cats) / n_cols)
    alto, margen_t, margen_b = 380 * n_filas + 200, 175, 30

    fig = make_subplots(
        rows=n_filas, cols=n_cols,
        subplot_titles=[f"<b>{c}</b>" for c in cats],
        horizontal_spacing=0.05, vertical_spacing=0.10,
    )
    grupos = []

    for i, mon in enumerate(monedas):
        for j, cat in enumerate(cats):
            sub = (q16[(q16["Currency_code"] == mon) & (q16["Categoria"] == cat)]
                   .sort_values("Posicion").copy())
            sub["Posicion"] = sub["Posicion"].astype(int)
            sub["PrecioTxt"] = [f"{_precio_txt(p)} {mon}" for p in sub["Price"]]
            pos = sub["Posicion"].tolist()
            fila, col = j // n_cols + 1, j % n_cols + 1

            # Circulos: tamaño = puesto, numero dentro = precio
            fig.add_trace(go.Scatter(
                x=[X_POS[p] for p in pos], y=[Y_POS[p] for p in pos],
                mode="markers+text",
                marker=dict(size=[TAM_POS[p] for p in pos],
                            color=[COLOR_POS[p] for p in pos],
                            line=dict(width=4, color="white")),
                text=[_precio_txt(v) for v in sub["Price"]],
                textposition="middle center",
                textfont=dict(size=14, color=[TEXTO_POS[p] for p in pos]),
                customdata=sub[["Item_name", "Restaurant_name", "Average_rating",
                                "Posicion", "PrecioTxt"]].to_numpy(),
                hovertemplate=("<b>%{customdata[0]}</b>"
                               "<br>Restaurante: %{customdata[1]}"
                               "<br>Calificación del restaurante: %{customdata[2]:.1f}"
                               "<br>Precio: %{customdata[4]}"
                               "<br>Puesto: %{customdata[3]}º<extra></extra>"),
                visible=(i == 0), showlegend=False,
            ), row=fila, col=col)
            grupos.append(i)

            # Etiquetas debajo de cada circulo: platillo y restaurante
            fig.add_trace(go.Scatter(
                x=[X_POS[p] for p in pos], y=[Y_POS[p] - 0.34 for p in pos],
                mode="text",
                text=[f"{MEDALLA[p]} <b>{corto(n, 22)}</b><br>{corto(r, 26)}"
                      for p, n, r in zip(pos, sub["Item_name"], sub["Restaurant_name"])],
                textposition="middle center",
                textfont=dict(size=11, color="#2d3436"),
                hoverinfo="skip", visible=(i == 0), showlegend=False,
            ), row=fila, col=col)
            grupos.append(i)

    subtitulo = ("El número dentro del círculo es el precio · el tamaño indica el puesto "
                 "(🥇 el más grande) · pasa el cursor para ver la calificación del restaurante")
    titulos = [_titulo("🏆 Los 3 platillos más caros de cada categoría — "
                       + etiqueta_moneda(m), subtitulo) for m in monedas]

    plot_alto = alto - margen_t - margen_b
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.985, yanchor="top", font=dict(size=21)),
        updatemenus=[_menu_monedas(monedas, grupos, titulos, y=1 + 95 / plot_alto)],
        template="plotly_white", height=alto, showlegend=False,
        margin=dict(t=margen_t, l=20, r=20, b=margen_b),
    )
    fig.update_xaxes(visible=False, range=[-0.8, 2.8])
    fig.update_yaxes(visible=False, range=[0.05, 1.5])
    return fig


# ----------------------------------------------------------------------
# GRAFICO 2 - Q21: MAPA DE CALOR (region x categoria)
# ----------------------------------------------------------------------
def fig_q21_mapa_calor(q21):
    cols = [c for c in ["Beverage", "Dessert", "Main", "Starter"] if c in q21.columns]
    d = q21.copy()
    d["Fila"] = d["Region"].map(etiqueta_region) + "  —  " + d["Currency_code"].map(etiqueta_moneda)

    vals = (d.set_index("Fila")[cols].apply(pd.to_numeric, errors="coerce")
              .replace(0, np.nan))                       # 0 = sin datos
    # Cada fila tiene su moneda (no se pueden comparar PEN con USD): el COLOR compara
    # cada categoria contra el promedio de su propia fila; el NUMERO es el precio real.
    rel = vals.div(vals.mean(axis=1), axis=0)
    texto = vals.apply(lambda col: col.map(lambda v: "" if pd.isna(v) else f"{v:,.2f}"))
    nombres = [ES_CAT[c] for c in cols]

    # Escala de color HONESTA: como minimo cubre +-10 % alrededor del promedio de la fila.
    # Asi, si todas las categorias cuestan casi lo mismo, los colores se ven parecidos
    # en lugar de exagerar diferencias de 1 o 2 %.
    zmin = min(float(np.nanmin(rel.values)), 0.90)
    zmax = max(float(np.nanmax(rel.values)), 1.10)
    dif_pct = (rel - 1) * 100                        # % sobre / bajo el promedio de la fila
    fig = go.Figure(go.Heatmap(
        z=rel.values, x=nombres, y=list(vals.index), zmin=zmin, zmax=zmax,
        text=texto.values, texttemplate="%{text}", textfont=dict(size=14),
        customdata=dif_pct.values,
        colorscale="YlOrRd", xgap=4, ygap=4,
        colorbar=dict(title="Precio relativo", tickmode="array",
                      tickvals=[zmin, zmax], ticktext=["Más barato", "Más caro"],
                      len=0.8),
        hovertemplate=("%{y}<br>%{x}: <b>%{text}</b> (precio promedio)"
                       "<br>%{customdata:+.1f} % frente al promedio de su región<extra></extra>"),
    ))
    fig.update_layout(
        title=dict(text=_titulo("🔥 ¿Qué categoría pesa más en cada región?",
                                "Número = precio promedio real · Color = qué tan cara es la categoría frente al "
                                "promedio de su región (colores parecidos = precios parecidos) · "
                                "celda vacía = sin datos"),
                   x=0.01, font=dict(size=21)),
        template="plotly_white", height=170 + 75 * len(vals),
        margin=dict(t=110, l=20, r=20, b=40),
        xaxis=dict(side="top", showgrid=False),
        yaxis=dict(autorange="reversed", automargin=True, showgrid=False),
    )
    return fig


# ----------------------------------------------------------------------
# Q26 - FILTRO + RANKING (version Python, para Streamlit)
# ----------------------------------------------------------------------
def filtrar_platillos(df, categoria=None, moneda=None, precio_max=None,
                      calorias_max=None, vegetariano=False, vegano=False,
                      sin_gluten=False):
    """Equivale al SQL dinamico de la Q26: solo aplica los filtros que se pidan.
    'categoria' acepta el codigo (Main) o el nombre en español (Platos fuertes)."""
    f = df
    if categoria:
        f = f[(f["Food_category"] == categoria) | (f["Categoria"] == categoria)]
    if moneda:
        f = f[f["Currency_code"] == moneda]
    if precio_max is not None:
        f = f[f["Price"] <= precio_max]
    if calorias_max is not None:
        f = f[f["Calories"] <= calorias_max]       # sin dato de calorias = no cumple
    if vegetariano:
        f = f[f["Vegetarian"] == 1]
    if vegano:
        f = f[f["Vegan"] == 1]
    if sin_gluten:
        f = f[f["Gluten_free"] == 1]
    return f


def _dieta_txt(fila):
    partes = []
    if fila["Vegetarian"] == 1:
        partes.append("🥕 Vegetariano")
    if fila["Vegan"] == 1:
        partes.append("🌱 Vegano")
    if fila["Gluten_free"] == 1:
        partes.append("🌾 Sin gluten")
    return " · ".join(partes) if partes else "—"


def fig_q26_ranking(df_filtrado, moneda=None, top=10):
    """Ranking de barras con los platillos mas caros que cumplen los filtros."""
    d = (df_filtrado.sort_values(["Price", "Menu_ID"], ascending=[False, True])
         .head(top).copy())
    fig = go.Figure()
    if d.empty:
        fig.add_annotation(text="Ningún platillo cumple estos filtros. Prueba ampliarlos.",
                           showarrow=False, font=dict(size=16, color="#636e72"))
        fig.update_layout(template="plotly_white", height=300,
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        return fig

    mon = moneda or d["Currency_code"].iloc[0]
    d["Etiqueta"] = [f"{i + 1}. {corto(n, 30)} · {corto(r, 24)}"
                     for i, (n, r) in enumerate(zip(d["Item_name"], d["Restaurant_name"]))]
    d["Dieta"] = d.apply(_dieta_txt, axis=1)
    d["Cal"] = d["Calories"].map(lambda c: "s/d" if pd.isna(c) else f"{c:,.0f} kcal")

    for k, cat in enumerate(sorted(d["Categoria"].unique())):
        s = d[d["Categoria"] == cat]
        fig.add_trace(go.Bar(
            x=s["Price"], y=s["Etiqueta"], orientation="h", name=cat,
            marker_color=COLOR_CATEGORIA.get(cat, PALETA[k % len(PALETA)]),
            text=[f"{p:,.2f} {mon}" for p in s["Price"]],
            textposition="inside", insidetextanchor="end",
            textfont=dict(color="white", size=13),
            customdata=s[["Item_name", "Restaurant_name", "City", "Cal", "Dieta"]].to_numpy(),
            hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}"
                           "<br>Calorías: %{customdata[3]}<br>%{customdata[4]}"
                           "<br>Precio: %{x:,.2f}<extra></extra>"),
        ))
    fig.update_layout(
        title=dict(text=_titulo(f"🍽️ Los {len(d)} platillos más caros con estos filtros — "
                                + etiqueta_moneda(mon),
                                "El color indica la categoría del platillo"),
                   x=0.01, font=dict(size=20)),
        barmode="overlay", template="plotly_white",
        height=130 + 52 * len(d), margin=dict(t=100, l=20, r=20, b=40),
        yaxis=dict(autorange="reversed", categoryorder="array",
                   categoryarray=list(d["Etiqueta"]), automargin=True),
        xaxis=dict(title=f"Precio ({mon})", rangemode="tozero"),
        legend=dict(orientation="h", y=-0.12, x=0),
    )
    return fig


# ----------------------------------------------------------------------
# Q26 - EXPLORADOR HTML AUTONOMO (filtros en el navegador, sin Streamlit)
# ----------------------------------------------------------------------
PLANTILLA_EXPLORADOR = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Explorador de platillos</title>
<style>
  body{font-family:'Segoe UI',Arial,sans-serif;background:#f5f6fa;margin:0;padding:24px;color:#2d3436}
  h1{margin:0 0 4px} .sub{color:#636e72;margin:0 0 18px}
  .panel{background:#fff;border-radius:14px;padding:18px;box-shadow:0 2px 10px rgba(0,0,0,.06);
         display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}
  label{font-size:13px;font-weight:600;display:block;margin-bottom:6px}
  select{width:100%;padding:8px;border-radius:8px;border:1px solid #dfe6e9}
  input[type=range]{width:100%}
  .chk label{font-weight:400;display:flex;gap:8px;align-items:center;margin:5px 0;font-size:14px}
  .kpis{display:flex;gap:14px;margin:16px 0;flex-wrap:wrap}
  .kpi{background:#fff;border-radius:14px;padding:14px 22px;box-shadow:0 2px 10px rgba(0,0,0,.06);min-width:150px}
  .kpi b{display:block;font-size:28px} .kpi span{color:#636e72;font-size:13px}
  .card{background:#fff;border-radius:14px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.06);margin-bottom:16px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;border-bottom:2px solid #dfe6e9;padding:8px}
  td{padding:8px;border-bottom:1px solid #f1f2f6}
  .nota{color:#636e72;font-size:12px;padding:6px 8px}
</style>
<script>__PLOTLY__</script>
</head>
<body>
<h1>🍽️ Explorador de platillos</h1>
<p class="sub">Ajusta los filtros y el ranking se actualiza al instante. Los precios solo se comparan dentro de una misma moneda.</p>

<div class="panel">
  <div><label>Categoría</label><select id="cat"></select></div>
  <div><label>Moneda</label><select id="mon"></select></div>
  <div><label>Precio máximo: <span id="vPrecio"></span></label><input type="range" id="sPrecio" min="0" max="100" value="100"></div>
  <div><label>Calorías máximas: <span id="vCal"></span></label><input type="range" id="sCal" min="0" max="1000" step="10" value="1000"></div>
  <div class="chk">
    <label><input type="checkbox" id="veg"> 🥕 Vegetariano</label>
    <label><input type="checkbox" id="vegan"> 🌱 Vegano</label>
    <label><input type="checkbox" id="glu"> 🌾 Sin gluten</label>
  </div>
</div>

<div class="kpis" id="kpis"></div>
<div class="card">
  <div id="grafico"></div>
  <p id="vacio" style="display:none;padding:30px;text-align:center;color:#636e72;font-size:16px">
    Ningún platillo cumple estos filtros. Prueba ampliarlos.</p>
</div>
<div class="card"><h3 style="margin:8px">Detalle de los platillos del ranking</h3><div id="tabla"></div>
  <p class="nota">🥕 Vegetariano · 🌱 Vegano · 🌾 Sin gluten · s/d = sin dato</p></div>

<script>
const DATA = __DATA__;
const NOM_MON = __NOMMON__;
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const corto = (t, n) => { t = String(t); return t.length <= n ? t : t.slice(0, n - 1) + "…"; };
const etMon = c => NOM_MON[c] ? c + " · " + NOM_MON[c] : c;
const ES = {Beverage:"Bebidas", Dessert:"Postres", Main:"Platos fuertes", Starter:"Entradas"};
const nombreCat = c => ES[c] || c;
const COL = {"Bebidas":"#2E86DE", "Postres":"#E84393", "Platos fuertes":"#F39C12", "Entradas":"#27AE60"};
const paleta = ["#8E44AD","#16A085","#E74C3C","#34495E"];
const colorCat = (c, i) => COL[nombreCat(c)] || paleta[i % paleta.length];

const categorias = [...new Set(DATA.map(d => d.Food_category))].sort();
const monedas = [...new Set(DATA.map(d => d.Currency_code))].sort();

const conteo = {}; DATA.forEach(d => conteo[d.Currency_code] = (conteo[d.Currency_code] || 0) + 1);
const monedaIni = Object.keys(conteo).sort((a, b) => conteo[b] - conteo[a])[0];

$("cat").innerHTML = '<option value="">Todas</option>' +
  categorias.map(c => '<option value="' + c + '">' + nombreCat(c) + '</option>').join("");
$("mon").innerHTML = monedas.map(m => '<option value="' + m + '">' + esc(etMon(m)) + '</option>').join("");
$("mon").value = monedaIni;

const calVals = DATA.map(d => d.Calories).filter(x => x !== null);
const maxCal = calVals.length ? Math.ceil(Math.max(...calVals) / 50) * 50 : 1000;
$("sCal").max = maxCal; $("sCal").value = maxCal;

function ajustarPrecio() {
  const precios = DATA.filter(d => d.Currency_code === $("mon").value).map(d => d.Price);
  const max = Math.ceil(Math.max(...precios));
  $("sPrecio").max = max; $("sPrecio").step = max > 100 ? 1 : 0.5; $("sPrecio").value = max;
}

const dieta = d => [d.Vegetarian == 1 ? "🥕 Vegetariano" : "", d.Vegan == 1 ? "🌱 Vegano" : "",
                    d.Gluten_free == 1 ? "🌾 Sin gluten" : ""].filter(x => x).join(" · ") || "—";
const calTxt = d => d.Calories === null ? "s/d" : Math.round(d.Calories) + " kcal";

function actualizar() {
  const m = $("mon").value, c = $("cat").value;
  const pmax = +$("sPrecio").value, cmax = +$("sCal").value;
  const calActivo = cmax < maxCal;       // como en el SQL: sin filtro si no se toca el control
  $("vPrecio").textContent = pmax + " " + m;
  $("vCal").textContent = calActivo ? cmax + " kcal" : "sin límite";

  const f = DATA.filter(d =>
    d.Currency_code === m &&
    (!c || d.Food_category === c) &&
    d.Price <= pmax &&
    (!calActivo || (d.Calories !== null && d.Calories <= cmax)) &&
    (!$("veg").checked   || d.Vegetarian == 1) &&
    (!$("vegan").checked || d.Vegan == 1) &&
    (!$("glu").checked   || d.Gluten_free == 1)
  );

  const prom = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
  const cals = f.map(d => d.Calories).filter(x => x !== null);
  $("kpis").innerHTML =
    '<div class="kpi"><b>' + f.length + '</b><span>platillos encontrados</span></div>' +
    '<div class="kpi"><b>' + prom(f.map(d => d.Price)).toFixed(2) + '</b><span>precio promedio (' + m + ')</span></div>' +
    '<div class="kpi"><b>' + Math.round(prom(cals)) + '</b><span>calorías promedio</span></div>';

  const top = f.slice().sort((a, b) => (b.Price - a.Price) || String(a.Menu_ID).localeCompare(String(b.Menu_ID))).slice(0, 10);

  if (top.length === 0) {
    $("grafico").style.display = "none"; $("vacio").style.display = "block";
    $("tabla").innerHTML = "";
    return;
  }
  $("vacio").style.display = "none"; $("grafico").style.display = "block";

  const etiquetas = top.map((d, i) => (i + 1) + ". " + corto(d.Item_name, 30) + " · " + corto(d.Restaurant_name, 24));
  const trazas = categorias.map((cat, k) => {
    const idx = top.map((d, i) => i).filter(i => top[i].Food_category === cat);
    return {
      type: "bar", orientation: "h", name: nombreCat(cat),
      x: idx.map(i => top[i].Price), y: idx.map(i => etiquetas[i]),
      marker: {color: colorCat(cat, k)},
      text: idx.map(i => top[i].Price.toFixed(2) + " " + m),
      textposition: "inside", insidetextanchor: "end", textfont: {color: "white", size: 13},
      hovertext: idx.map(i => "<b>" + esc(top[i].Item_name) + "</b><br>" + esc(top[i].Restaurant_name) +
                              " · " + esc(top[i].City) + "<br>Calorías: " + calTxt(top[i]) +
                              "<br>" + dieta(top[i]) + "<br>Precio: " + top[i].Price.toFixed(2) + " " + m),
      hoverinfo: "text"
    };
  });
  Plotly.react("grafico", trazas, {
    template: "plotly_white", barmode: "overlay", height: 130 + 52 * top.length,
    margin: {t: 20, l: 20, r: 20, b: 50},
    yaxis: {autorange: "reversed", categoryorder: "array", categoryarray: etiquetas, automargin: true},
    xaxis: {title: "Precio (" + m + ")", rangemode: "tozero"},
    legend: {orientation: "h", y: -0.12, x: 0}
  }, {responsive: true});

  $("tabla").innerHTML =
    '<table><tr><th>#</th><th>Platillo</th><th>Categoría</th><th>Precio</th><th>Calorías</th><th>Dieta</th><th>Restaurante</th><th>Ciudad</th></tr>' +
    top.map((d, i) => '<tr><td>' + (i + 1) + '</td><td><b>' + esc(d.Item_name) + '</b></td><td>' + nombreCat(d.Food_category) +
      '</td><td>' + d.Price.toFixed(2) + ' ' + m + '</td><td>' + calTxt(d) + '</td><td>' + dieta(d) +
      '</td><td>' + esc(d.Restaurant_name) + '</td><td>' + esc(d.City) + '</td></tr>').join("") + '</table>';
}

["cat", "sPrecio", "sCal", "veg", "vegan", "glu"].forEach(id => $(id).addEventListener("input", actualizar));
$("mon").addEventListener("change", () => { ajustarPrecio(); actualizar(); });
ajustarPrecio(); actualizar();
</script>
</body>
</html>
"""


def html_explorador(q26):
    """Devuelve el HTML completo del explorador (Plotly embebido, funciona sin internet)."""
    datos = q26.drop(columns=["Categoria"], errors="ignore")
    datos_json = datos.to_json(orient="records", force_ascii=False).replace("</", "<\\/")
    nom_json = json.dumps(NOMBRE_MONEDA, ensure_ascii=False)
    # Orden: primero los datos, ultimo la libreria (para no reescanear sus 3 MB)
    return (PLANTILLA_EXPLORADOR.replace("__DATA__", datos_json)
            .replace("__NOMMON__", nom_json)
            .replace("__PLOTLY__", get_plotlyjs()))


# ----------------------------------------------------------------------
# EJECUCION INDEPENDIENTE (F5 en Spyder)
# ----------------------------------------------------------------------
def generar_html(abrir=True):
    datos = cargar_datos()
    rutas = []

    figuras = {
        "2A_1_podio_premium": fig_q16_podio(datos["q16"]),
        "2A_2_mapa_calor_precios": fig_q21_mapa_calor(datos["q21"]),
    }
    for nombre, fig in figuras.items():
        ruta = os.path.join(SALIDA, f"Reporte{nombre}.html")
        fig.write_html(ruta, include_plotlyjs=True)
        rutas.append(ruta)
        print("Guardado:", ruta)

    ruta = os.path.join(SALIDA, "Reporte2A_3_explorador_platillos.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html_explorador(datos["q26"]))
    rutas.append(ruta)
    print("Guardado:", ruta)

    if abrir:
        for r in rutas:
            webbrowser.open("file:///" + r.replace("\\", "/"))


if __name__ == "__main__":
    generar_html()
