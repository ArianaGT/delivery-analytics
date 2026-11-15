# -*- coding: utf-8 -*-
"""
REPORTE 2B - CONDICIONES DEL SERVICIO   (Q23, Q24)
==================================================
Cada grafico es una funcion que RECIBE un DataFrame y DEVUELVE una figura de plotly,
para usarla igual en este script (F5) o en la app de Streamlit.

Graficos:
  1. Q23  Aumentos de precio del 1 al 15 de diciembre por modalidad  (circulos + selector de moneda)
  2. Q24  Riesgo operativo del delivery                              (anillo tipo semaforo)

Codigos con leyenda: monedas como "PEN · Sol peruano"; modalidades con icono y nombre
completo; niveles de riesgo con su regla (por ejemplo "Alto · cancelación de 7 % o más").
"""
import os
import webbrowser

import pandas as pd
import plotly.graph_objects as go

from conexion import consulta, SALIDA, etiqueta_moneda

# ----------------------------------------------------------------------
# CONSULTAS SQL (las tuyas, sin cambios de logica)
# ----------------------------------------------------------------------
# SET NOCOUNT ON es necesario para que pandas reciba el resultado
# cuando la consulta empieza con DECLARE.
SQL_Q23 = """
SET NOCOUNT ON;
DECLARE @Ref       DATE = '2023-12-15';
DECLARE @InicioMTD DATE = DATEFROMPARTS(YEAR(@Ref), MONTH(@Ref), 1);

WITH Modalidades AS (
    SELECT Restaurant_ID, Modalidad
    FROM (
        SELECT Restaurant_ID,
               CAST(Delivery_available AS INT) AS Delivery,
               CAST(Takeaway           AS INT) AS Para_llevar,
               CAST(Dine_in            AS INT) AS En_local,
               CAST(Reservations       AS INT) AS Reservaciones
        FROM Restaurante
    ) AS Origen
    UNPIVOT (Activo FOR Modalidad
             IN (Delivery, Para_llevar, En_local, Reservaciones)) AS U
    WHERE Activo = 1
)
SELECT M.Modalidad,
       PA.Currency_code,
       CAST(SUM(CASE WHEN CAST(HP.Timestamp AS DATE) BETWEEN @InicioMTD AND @Ref
                     THEN IM.Price - HP.Previous_price
                     ELSE 0 END) AS DECIMAL(14,2)) AS AumentoMTD
FROM Historial_Precio AS HP
JOIN Item_Menu   AS IM ON IM.Menu_ID      = HP.Menu_ID
JOIN Restaurante AS R  ON R.Restaurant_ID = IM.Restaurant_ID
JOIN Pais        AS PA ON PA.ISO_code     = R.ISO_code
JOIN Modalidades AS M  ON M.Restaurant_ID = R.Restaurant_ID
WHERE IM.Price > HP.Previous_price
GROUP BY M.Modalidad, PA.Currency_code
ORDER BY M.Modalidad, PA.Currency_code;
"""

SQL_Q24 = """
SELECT NivelRiesgo,
       COUNT(*) AS NumRestaurantes
FROM (
    SELECT CASE
               WHEN RD.Cancellation_rate >= 0.07 THEN 'Alto'
               WHEN RD.Cancellation_rate >= 0.03 THEN 'Medio'
               ELSE 'Bajo'
           END AS NivelRiesgo
    FROM Restaurante          AS R
    JOIN Restaurante_Delivery AS RD ON RD.Restaurant_ID = R.Restaurant_ID
    WHERE R.Delivery_available = 1
) AS T
GROUP BY NivelRiesgo
ORDER BY NumRestaurantes DESC;
"""

# Modalidades: codigo de la base -> nombre con icono
ORDEN_MOD = ["Delivery", "Para_llevar", "En_local", "Reservaciones"]
MAP_MOD = {"Delivery": "🛵 Delivery", "Para_llevar": "🥡 Para llevar",
           "En_local": "🍽️ En el local", "Reservaciones": "📅 Reservaciones"}
COLOR_MOD = {"Delivery": "#FF6B6B", "Para_llevar": "#FFB400",
             "En_local": "#4ECDC4", "Reservaciones": "#6C5CE7"}

# Riesgo: nivel -> leyenda con su regla, y color de semaforo
ORDEN_RIESGO = ["Bajo", "Medio", "Alto"]
LEYENDA_RIESGO = {"Bajo": "Bajo · cancelación menor a 3 %",
                  "Medio": "Medio · cancelación de 3 % a menos de 7 %",
                  "Alto": "Alto · cancelación de 7 % o más"}
COLOR_RIESGO = {"Bajo": "#2ECC71", "Medio": "#F1C40F", "Alto": "#E74C3C"}


# ----------------------------------------------------------------------
# CARGA DE DATOS
# ----------------------------------------------------------------------
def cargar_datos():
    """Ejecuta las 2 consultas y deja los DataFrames listos para graficar."""
    q23 = consulta(SQL_Q23)
    q24 = consulta(SQL_Q24)
    q23["AumentoMTD"] = pd.to_numeric(q23["AumentoMTD"], errors="coerce").fillna(0)
    return {"q23": q23, "q24": q24}


def _titulo(texto, subtitulo):
    return f"<b>{texto}</b><br><sup>{subtitulo}</sup>"


# ----------------------------------------------------------------------
# GRAFICO 1 - Q23: AUMENTOS DE PRECIO MTD POR MODALIDAD (circulos)
# ----------------------------------------------------------------------
def fig_q23_modalidades(q23):
    monedas = sorted(q23["Currency_code"].unique())
    etiquetas = [MAP_MOD[m] for m in ORDEN_MOD]
    colores = [COLOR_MOD[m] for m in ORDEN_MOD]

    fig = go.Figure()
    grupos, rangos = [], []

    for i, mon in enumerate(monedas):
        serie = (q23[q23["Currency_code"] == mon].set_index("Modalidad")
                 .reindex(ORDEN_MOD)["AumentoMTD"].fillna(0))
        vals = serie.values
        fmt = (lambda v: f"{v:,.0f}") if vals.max() >= 100 else (lambda v: f"{v:,.2f}")

        # Tallo fino que va de 0 hasta el valor ...
        fig.add_trace(go.Bar(
            x=vals, y=etiquetas, orientation="h", width=0.12,
            marker_color=colores, hoverinfo="skip",
            visible=(i == 0), showlegend=False,
        ))
        # ... y un circulo al final con el valor al lado
        fig.add_trace(go.Scatter(
            x=vals, y=etiquetas, mode="markers+text",
            marker=dict(size=48, color=colores, line=dict(width=4, color="white")),
            text=[f"<b>{fmt(v)}</b> {mon}" for v in vals],
            textposition="middle right", textfont=dict(size=15, color="#2d3436"),
            hovertemplate=("<b>%{y}</b><br>Aumento acumulado: %{x:,.2f} " + mon
                           + "<extra></extra>"),
            visible=(i == 0), showlegend=False,
        ))
        grupos += [i, i]
        rangos.append([0, max(float(vals.max()) * 1.4, 1.0)])

    subtitulo = ("Aumento acumulado del 1 al 15 de diciembre de 2023 · un restaurante puede ofrecer "
                 "varias modalidades, por eso los círculos no se suman entre sí")
    titulos = [_titulo("🛵 ¿En qué modalidad subieron más los precios? — "
                       + etiqueta_moneda(m), subtitulo) for m in monedas]

    botones = [
        dict(label=f"Moneda: {etiqueta_moneda(mon)}", method="update",
             args=[{"visible": [g == i for g in grupos]},
                   {"title.text": titulos[i], "xaxis.range": rangos[i]}])
        for i, mon in enumerate(monedas)
    ]
    fig.update_layout(
        title=dict(text=titulos[0], x=0.01, y=0.975, yanchor="top", font=dict(size=21)),
        updatemenus=[dict(buttons=botones, direction="down", showactive=True,
                          x=0.0, xanchor="left", y=1.19, yanchor="top")],
        template="plotly_white", height=540, showlegend=False,
        margin=dict(t=170, l=20, r=30, b=60),
        yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=etiquetas,
                   automargin=True, tickfont=dict(size=15)),
        xaxis=dict(title="Aumento acumulado (moneda local)", range=rangos[0], zeroline=False),
    )
    return fig


# ----------------------------------------------------------------------
# GRAFICO 2 - Q24: RIESGO OPERATIVO DEL DELIVERY (semaforo)
# ----------------------------------------------------------------------
def fig_q24_riesgo(q24):
    serie = (q24.set_index("NivelRiesgo").reindex(ORDEN_RIESGO)["NumRestaurantes"]
             .fillna(0).astype(int))
    total = int(serie.sum())

    fig = go.Figure(go.Pie(
        labels=[LEYENDA_RIESGO[n] for n in ORDEN_RIESGO],
        values=serie.values, sort=False, direction="clockwise", hole=0.6,
        marker=dict(colors=[COLOR_RIESGO[n] for n in ORDEN_RIESGO],
                    line=dict(color="white", width=5)),
        pull=[0, 0, 0.05],
        texttemplate="<b>%{value}</b><br>%{percent}", textposition="inside",
        textfont=dict(size=18, color="#1b1b1b"),
        hovertemplate="%{label}<br><b>%{value}</b> restaurantes (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{total}</b><br><span style='font-size:15px'>restaurantes<br>con delivery</span>",
                       x=0.5, y=0.5, showarrow=False, font=dict(size=44, color="#2d3436"),
                       xref="paper", yref="paper")
    fig.update_layout(
        title=dict(text=_titulo("🚦 ¿Qué tan confiable es el delivery?",
                                "Restaurantes con delivery clasificados según su porcentaje "
                                "de cancelación de pedidos"),
                   x=0.01, font=dict(size=21)),
        template="plotly_white", height=560,
        legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center", font=dict(size=13)),
        margin=dict(t=110, l=20, r=20, b=70),
    )
    return fig


# ----------------------------------------------------------------------
# EJECUCION INDEPENDIENTE (F5 en Spyder)
# ----------------------------------------------------------------------
def generar_html(abrir=True):
    datos = cargar_datos()
    figuras = {
        "2B_1_aumentos_por_modalidad": fig_q23_modalidades(datos["q23"]),
        "2B_2_riesgo_delivery": fig_q24_riesgo(datos["q24"]),
    }
    for nombre, fig in figuras.items():
        ruta = os.path.join(SALIDA, f"Reporte{nombre}.html")
        fig.write_html(ruta, include_plotlyjs=True)
        print("Guardado:", ruta)
        if abrir:
            webbrowser.open("file:///" + ruta.replace("\\", "/"))


if __name__ == "__main__":
    generar_html()
