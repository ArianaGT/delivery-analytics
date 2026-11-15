# -*- coding: utf-8 -*-
"""
REPORTE 3 - TRAZABILIDAD DE PRECIOS   (Q18, Q19, Q22)
=====================================================
Cada grafico es una funcion que RECIBE un DataFrame y DEVUELVE una figura de plotly.
Asi sirve igual para:
  - ejecutarlo solo (F5 en Spyder)  -> genera HTML interactivos en la carpeta "salida"
  - la app de Streamlit             -> st.plotly_chart(fig_q18(datos["q18"]))

Graficos:
  1. Q18  Tendencia del aumento % por categoria (lineas + mapa de calor acelera/frena)
  2. Q19a Ritmo semanal y acumulado por moneda   (barras + linea, selector de moneda)
  3. Q19b Comparativo de todas las monedas       (% del aumento anual acumulado)
  4. Q22  Crecimiento acumulado mensual por region (areas apiladas, selector de moneda)
"""
import os
import webbrowser

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from conexion import consulta, SALIDA, ES_CAT, PALETA, etiqueta_moneda, etiqueta_region

# ----------------------------------------------------------------------
# CONSULTAS SQL (las tuyas, sin cambios de logica; comentarios quitados)
# ----------------------------------------------------------------------
SQL_Q18 = """
WITH AumentoCategoria AS (
    SELECT IM.Food_category,
           FORMAT(CAST(HP.Timestamp AS DATETIME2), 'yyyy-MM') AS Mes,
           AVG((IM.Price - HP.Previous_price) * 100.0
               / NULLIF(HP.Previous_price, 0))                 AS AumentoPromedioPct
    FROM Historial_Precio AS HP
    JOIN Item_Menu AS IM ON IM.Menu_ID = HP.Menu_ID
    WHERE IM.Price > HP.Previous_price
    GROUP BY IM.Food_category,
             FORMAT(CAST(HP.Timestamp AS DATETIME2), 'yyyy-MM')
),
ConMesAnterior AS (
    SELECT Food_category,
           Mes,
           AumentoPromedioPct,
           LAG(AumentoPromedioPct, 1, NULL)
               OVER (PARTITION BY Food_category ORDER BY Mes)   AS AumentoPctMesAnt
    FROM AumentoCategoria
)
SELECT Food_category,
       Mes,
       CAST(AumentoPromedioPct                    AS DECIMAL(10,2)) AS AumentoPctActual,
       CAST(AumentoPctMesAnt                      AS DECIMAL(10,2)) AS AumentoPctMesAnt,
       CAST(AumentoPromedioPct - AumentoPctMesAnt AS DECIMAL(10,2)) AS VariacionPuntos,
       CASE
           WHEN AumentoPctMesAnt IS NULL                  THEN 'Sin mes anterior'
           WHEN AumentoPromedioPct > AumentoPctMesAnt     THEN 'Se acelera'
           WHEN AumentoPromedioPct < AumentoPctMesAnt     THEN 'Se frena'
           ELSE 'Estable'
       END                                                          AS Tendencia
FROM ConMesAnterior
ORDER BY Food_category, Mes;
"""

SQL_Q19 = """
WITH Base AS (
    SELECT P.Currency_code,
           IM.Price - HP.Previous_price AS Incremento,
           CAST(HP.Timestamp AS DATE)   AS Fecha
    FROM Historial_Precio AS HP
    JOIN Item_Menu   AS IM ON IM.Menu_ID      = HP.Menu_ID
    JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Pais        AS P  ON P.ISO_code      = R.ISO_code
    WHERE YEAR(CAST(HP.Timestamp AS DATETIME2)) = 2023
      AND IM.Price > HP.Previous_price
),
IncrementoSemanal AS (
    SELECT Currency_code,
           DATEADD(DAY, -(DATEDIFF(DAY, '19000101', Fecha) % 7), Fecha) AS InicioSemana,
           SUM(Incremento)                                              AS IncrementoSemana
    FROM Base
    GROUP BY Currency_code,
             DATEADD(DAY, -(DATEDIFF(DAY, '19000101', Fecha) % 7), Fecha)
)
SELECT Currency_code,
       ROW_NUMBER() OVER (PARTITION BY Currency_code
                          ORDER BY InicioSemana)                        AS NroSemana,
       InicioSemana,
       CAST(IncrementoSemana AS DECIMAL(14,2))                          AS IncrementoSemana,
       CAST(SUM(IncrementoSemana) OVER (
                PARTITION BY Currency_code
                ORDER BY InicioSemana
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            AS DECIMAL(14,2))                                           AS IncrementoAcumulado
FROM IncrementoSemanal
ORDER BY Currency_code, InicioSemana;
"""

SQL_Q22 = """
WITH Base AS (
    SELECT PA.Region,
           PA.Currency_code,
           MONTH(CAST(HP.Timestamp AS DATETIME2)) AS MesNum,
           IM.Price - HP.Previous_price           AS Incremento
    FROM Historial_Precio AS HP
    JOIN Item_Menu   AS IM ON IM.Menu_ID      = HP.Menu_ID
    JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
    JOIN Pais        AS PA ON PA.ISO_code     = R.ISO_code
    WHERE YEAR(CAST(HP.Timestamp AS DATETIME2)) = 2023
      AND IM.Price > HP.Previous_price
)
SELECT Region,
       Currency_code,
       CAST(SUM(CASE WHEN MesNum <= 1  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Ene,
       CAST(SUM(CASE WHEN MesNum <= 2  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Feb,
       CAST(SUM(CASE WHEN MesNum <= 3  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Mar,
       CAST(SUM(CASE WHEN MesNum <= 4  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Abr,
       CAST(SUM(CASE WHEN MesNum <= 5  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_May,
       CAST(SUM(CASE WHEN MesNum <= 6  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Jun,
       CAST(SUM(CASE WHEN MesNum <= 7  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Jul,
       CAST(SUM(CASE WHEN MesNum <= 8  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Ago,
       CAST(SUM(CASE WHEN MesNum <= 9  THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Sep,
       CAST(SUM(CASE WHEN MesNum <= 10 THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Oct,
       CAST(SUM(CASE WHEN MesNum <= 11 THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Nov,
       CAST(SUM(CASE WHEN MesNum <= 12 THEN Incremento ELSE 0 END) AS DECIMAL(14,2)) AS Acum_Dic
FROM Base
GROUP BY Region, Currency_code
ORDER BY Region, Currency_code;
"""

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

COLOR_TENDENCIA = {"Se acelera": "#E74C3C", "Se frena": "#2ECC71",
                   "Estable": "#95A5A6", "Sin mes anterior": "#D0D3D4"}


# ----------------------------------------------------------------------
# CARGA DE DATOS
# ----------------------------------------------------------------------
def cargar_datos():
    """Ejecuta las 3 consultas y deja los DataFrames listos para graficar."""
    q18 = consulta(SQL_Q18)
    q19 = consulta(SQL_Q19)
    q22 = consulta(SQL_Q22)

    q18["Categoria"] = q18["Food_category"].map(lambda c: ES_CAT.get(c, c))
    for c in ["AumentoPctActual", "AumentoPctMesAnt", "VariacionPuntos"]:
        q18[c] = pd.to_numeric(q18[c], errors="coerce")

    q19["InicioSemana"] = pd.to_datetime(q19["InicioSemana"])
    for c in ["IncrementoSemana", "IncrementoAcumulado"]:
        q19[c] = pd.to_numeric(q19[c], errors="coerce")

    for c in [c for c in q22.columns if c.startswith("Acum_")]:
        q22[c] = pd.to_numeric(q22[c], errors="coerce")

    return {"q18": q18, "q19": q19, "q22": q22}


def _menu_monedas(monedas, grupos, titulos):
    """Menu desplegable que muestra solo las trazas de la moneda elegida."""
    botones = [
        dict(label=f"Moneda: {etiqueta_moneda(mon)}", method="update",
             args=[{"visible": [g == i for g in grupos]}, {"title.text": tit}])
        for i, (mon, tit) in enumerate(zip(monedas, titulos))
    ]
    return dict(buttons=botones, direction="down", showactive=True,
                x=0.0, xanchor="left", y=1.15, yanchor="top")


# ----------------------------------------------------------------------
# GRAFICO 1 - Q18: ¿se acelera o se frena el encarecimiento?
# ----------------------------------------------------------------------
def fig_q18(q18):
    cats = sorted(q18["Categoria"].unique())
    meses = sorted(q18["Mes"].unique())

    fig = make_subplots(
        rows=2, cols=1, row_heights=[0.62, 0.38], shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=("Aumento % promedio de precio por categoría",
                        "¿Se acelera o se frena? Cambio frente al mes anterior (puntos porcentuales)"),
    )

    # Fila 1: una linea por categoria; el relleno de cada punto muestra la tendencia
    for i, cat in enumerate(cats):
        d = q18[q18["Categoria"] == cat].sort_values("Mes")
        color_cat = PALETA[i % len(PALETA)]
        fig.add_trace(go.Scatter(
            x=d["Mes"], y=d["AumentoPctActual"], mode="lines+markers", name=cat,
            line=dict(color=color_cat, width=3),
            marker=dict(size=12,
                        color=[COLOR_TENDENCIA.get(t, "#95A5A6") for t in d["Tendencia"]],
                        line=dict(width=2.5, color=color_cat)),
            customdata=np.stack([d["AumentoPctMesAnt"], d["VariacionPuntos"],
                                 d["Tendencia"]], axis=-1),
            hovertemplate=("<b>" + cat + "</b> · %{x}"
                           "<br>Aumento promedio: %{y:.2f}%"
                           "<br>Mes anterior: %{customdata[0]:.2f}%"
                           "<br>Variación: %{customdata[1]:+.2f} pp"
                           "<br>Tendencia: %{customdata[2]}<extra></extra>"),
        ), row=1, col=1)

    # Leyenda explicativa de los colores de los puntos
    for t in ["Se acelera", "Se frena", "Estable"]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name="Punto: " + t,
            marker=dict(size=12, color=COLOR_TENDENCIA[t]),
        ), row=1, col=1)

    # Fila 2: mapa de calor divergente (rojo = acelera, verde = frena)
    piv = (q18.pivot(index="Categoria", columns="Mes", values="VariacionPuntos")
              .reindex(index=cats, columns=meses))
    fig.add_trace(go.Heatmap(
        z=piv.values, x=meses, y=cats, colorscale="RdYlGn_r", zmid=0,
        xgap=3, ygap=3, texttemplate="%{z:+.1f}", textfont=dict(size=12),
        colorbar=dict(title="pp", len=0.34, y=0.17),
        hovertemplate="%{y} · %{x}<br>Variación: %{z:+.2f} pp<extra></extra>",
    ), row=2, col=1)

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=meses)
    fig.update_yaxes(title_text="Aumento promedio (%)", ticksuffix="%", row=1, col=1)
    fig.update_layout(
        title=dict(text="📈 ¿Se acelera o se frena el encarecimiento por categoría?",
                   x=0.01, font=dict(size=22)),
        template="plotly_white", height=780,
        legend=dict(orientation="h", y=-0.08, x=0),
        margin=dict(t=100, l=60, r=30, b=60),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 2 - Q19a: ritmo semanal y acumulado, por moneda
# ----------------------------------------------------------------------
def fig_q19_semanal(q19):
    monedas = sorted(q19["Currency_code"].unique())
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    grupos = []

    for i, mon in enumerate(monedas):
        d = q19[q19["Currency_code"] == mon].sort_values("InicioSemana")
        fig.add_trace(go.Bar(
            x=d["InicioSemana"], y=d["IncrementoSemana"],
            name="Incremento de la semana", marker_color="#9CC5E8", opacity=0.9,
            visible=(i == 0),
            hovertemplate="Semana del %{x|%d %b %Y}<br>Incremento: %{y:,.2f}<extra></extra>",
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=d["InicioSemana"], y=d["IncrementoAcumulado"], mode="lines",
            name="Acumulado del año", line=dict(color="#E84393", width=4),
            fill="tozeroy", fillcolor="rgba(232,67,147,0.10)",
            visible=(i == 0),
            hovertemplate="Semana del %{x|%d %b %Y}<br>Acumulado: %{y:,.2f}<extra></extra>",
        ), secondary_y=True)
        grupos += [i, i]

    titulos = [f"💰 Ritmo de ajuste de precios en 2023 ({etiqueta_moneda(m)})" for m in monedas]
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.96, font=dict(size=22)),
        updatemenus=[_menu_monedas(monedas, grupos, titulos)],
        template="plotly_white", height=560, bargap=0.25,
        legend=dict(orientation="h", y=-0.28, x=0),
        margin=dict(t=130, l=60, r=60, b=40),
    )
    fig.update_yaxes(title_text="Incremento de cada semana", secondary_y=False,
                     title_font=dict(color="#4A90C2"))
    fig.update_yaxes(title_text="Acumulado del año", secondary_y=True,
                     title_font=dict(color="#E84393"), showgrid=False)
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.07))
    return fig


# ----------------------------------------------------------------------
# GRAFICO 3 - Q19b: todas las monedas comparadas en una escala comun
# ----------------------------------------------------------------------
def fig_q19_comparado(q19):
    fig = go.Figure()
    d_orden = q19.sort_values("InicioSemana")

    for i, (mon, d) in enumerate(d_orden.groupby("Currency_code")):
        total = d["IncrementoAcumulado"].max()
        pct = d["IncrementoAcumulado"] / total * 100 if total and total > 0 \
            else d["IncrementoAcumulado"] * 0
        fig.add_trace(go.Scatter(
            x=d["InicioSemana"], y=pct, mode="lines", name=etiqueta_moneda(mon),
            line=dict(width=2.8, color=PALETA[i % len(PALETA)]),
            customdata=d["IncrementoAcumulado"],
            hovertemplate=("<b>" + etiqueta_moneda(mon) + "</b><br>Semana del %{x|%d %b %Y}"
                           "<br>%{y:.1f}% del aumento anual"
                           "<br>Acumulado: %{customdata:,.2f}<extra></extra>"),
        ))

    fig.add_hline(y=50, line_dash="dot", line_color="#95A5A6",
                  annotation_text="mitad del aumento anual", annotation_position="top left")
    fig.update_layout(
        title=dict(text="⏱️ ¿Cuándo se concentró el aumento? Todas las monedas en una misma escala",
                   x=0.01, font=dict(size=20)),
        template="plotly_white", height=520, hovermode="closest",
        yaxis=dict(title="% del aumento total de 2023 ya aplicado", ticksuffix="%", range=[0, 102]),
        xaxis=dict(title="Semana (inicio en lunes)"),
        legend=dict(title="Moneda (clic = ocultar · doble clic = aislar)"),
        margin=dict(t=80, l=60, r=30, b=50),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 4 - Q22: crecimiento acumulado mensual por region
# ----------------------------------------------------------------------
def fig_q22(q22):
    cols = [c for c in q22.columns if c.startswith("Acum_")]
    monedas = sorted(q22["Currency_code"].unique())
    regiones = sorted(q22["Region"].unique())
    color_region = {r: PALETA[i % len(PALETA)] for i, r in enumerate(regiones)}

    fig = go.Figure()
    grupos = []
    for i, mon in enumerate(monedas):
        sub = q22[q22["Currency_code"] == mon]
        for _, fila in sub.iterrows():
            fig.add_trace(go.Scatter(
                x=MESES, y=[float(fila[c]) for c in cols], mode="lines",
                name=etiqueta_region(fila["Region"]), stackgroup=f"moneda_{i}",
                line=dict(width=1, color=color_region[fila["Region"]]),
                hovertemplate=("<b>" + etiqueta_region(fila["Region"]) + "</b><br>%{x}: %{y:,.2f}"
                               "<extra></extra>"),
                visible=(i == 0),
            ))
            grupos.append(i)

    titulos = [f"🌎 Aumento acumulado de precios por región, 2023 ({etiqueta_moneda(m)})" for m in monedas]
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.96, font=dict(size=22)),
        updatemenus=[_menu_monedas(monedas, grupos, titulos)],
        template="plotly_white", height=540, hovermode="x unified",
        yaxis=dict(title="Aumento acumulado (moneda local)"),
        xaxis=dict(title="Mes"),
        legend=dict(title="Región", orientation="h", y=-0.2, x=0),
        margin=dict(t=130, l=60, r=30, b=60),
    )
    return fig


# ----------------------------------------------------------------------
# EJECUCION INDEPENDIENTE (F5 en Spyder): genera los HTML interactivos
# ----------------------------------------------------------------------
def generar_html(abrir=True):
    datos = cargar_datos()
    figuras = {
        "3_1_tendencia_categorias": fig_q18(datos["q18"]),
        "3_2_ritmo_semanal": fig_q19_semanal(datos["q19"]),
        "3_3_comparativo_monedas": fig_q19_comparado(datos["q19"]),
        "3_4_acumulado_regiones": fig_q22(datos["q22"]),
    }
    for nombre, fig in figuras.items():
        ruta = os.path.join(SALIDA, f"Reporte{nombre}.html")
        fig.write_html(ruta, include_plotlyjs=True)
        print("Guardado:", ruta)
        if abrir:
            webbrowser.open("file:///" + ruta.replace("\\", "/"))


if __name__ == "__main__":
    generar_html()
