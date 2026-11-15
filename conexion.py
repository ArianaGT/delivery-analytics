# -*- coding: utf-8 -*-
"""
conexion.py - Conexion a SQL Server y utilidades compartidas por todos los reportes.

Todos los reportes hacen:   from conexion import consulta, SALIDA, ES_CAT
"""
import os

import pandas as pd
from sqlalchemy import create_engine

# --- Configuracion (cambia solo esto si cambia tu servidor o tu base) ---
SERVIDOR = "localhost"
BASE = "Bases-Trabajo"
DRIVER = "ODBC+Driver+18+for+SQL+Server"

# Carpeta donde se guardan los archivos generados (junto a estos .py)
CARPETA = os.path.dirname(os.path.abspath(__file__))
SALIDA = os.path.join(CARPETA, "salida")
os.makedirs(SALIDA, exist_ok=True)

_engine = None


def get_engine():
    """Crea la conexion la primera vez y la reutiliza despues."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"mssql+pyodbc://@{SERVIDOR}/{BASE}"
            f"?driver={DRIVER}"
            "&trusted_connection=yes&TrustServerCertificate=yes"
        )
    return _engine


def consulta(sql):
    """Ejecuta una consulta SQL y devuelve un DataFrame."""
    return pd.read_sql(sql, get_engine())


# --- Utilidades visuales compartidas ---
ES_CAT = {"Beverage": "Bebidas", "Dessert": "Postres",
          "Main": "Platos fuertes", "Starter": "Entradas"}

PALETA = ["#2E86DE", "#E84393", "#F39C12", "#27AE60", "#8E44AD",
          "#16A085", "#E74C3C", "#34495E", "#D35400", "#7F8C8D"]


# --- Nombres de monedas (codigo ISO -> nombre) para leyendas y selectores ---
NOMBRE_MONEDA = {
    "USD": "Dólar estadounidense", "EUR": "Euro", "GBP": "Libra esterlina",
    "PEN": "Sol peruano", "BRL": "Real brasileño", "MXN": "Peso mexicano",
    "COP": "Peso colombiano", "CLP": "Peso chileno", "ARS": "Peso argentino",
    "UYU": "Peso uruguayo", "BOB": "Boliviano", "PYG": "Guaraní paraguayo",
    "VES": "Bolívar venezolano", "VEF": "Bolívar venezolano", "CRC": "Colón costarricense",
    "GTQ": "Quetzal guatemalteco", "HNL": "Lempira hondureño", "NIO": "Córdoba nicaragüense",
    "PAB": "Balboa panameño", "DOP": "Peso dominicano", "CUP": "Peso cubano",
    "CAD": "Dólar canadiense", "AUD": "Dólar australiano", "NZD": "Dólar neozelandés",
    "CHF": "Franco suizo", "JPY": "Yen japonés", "CNY": "Yuan chino",
    "KRW": "Won surcoreano", "INR": "Rupia india", "IDR": "Rupia indonesia",
    "RUB": "Rublo ruso", "TRY": "Lira turca", "ZAR": "Rand sudafricano",
    "SEK": "Corona sueca", "NOK": "Corona noruega", "DKK": "Corona danesa",
    "PLN": "Esloti polaco", "CZK": "Corona checa", "HUF": "Forinto húngaro",
    "AED": "Dírham de los EAU", "SAR": "Riyal saudí", "ILS": "Nuevo séquel israelí",
    "THB": "Baht tailandés", "SGD": "Dólar de Singapur", "HKD": "Dólar de Hong Kong",
    "MYR": "Ringgit malayo", "PHP": "Peso filipino", "VND": "Dong vietnamita",
    "EGP": "Libra egipcia", "NGN": "Naira nigeriana", "KES": "Chelín keniano",
    "MAD": "Dírham marroquí",
}


def etiqueta_moneda(codigo):
    """'PEN' -> 'PEN · Sol peruano'. Si el codigo no esta en el diccionario, devuelve el codigo."""
    codigo = str(codigo).strip()
    nombre = NOMBRE_MONEDA.get(codigo.upper())
    return f"{codigo} · {nombre}" if nombre else codigo


# --- Nombres de regiones (ingles -> español) para leyendas ---
NOMBRE_REGION = {
    "Asia": "Asia", "Europe": "Europa", "Africa": "África", "Oceania": "Oceanía",
    "North America": "Norteamérica", "South America": "Sudamérica",
    "Central America": "Centroamérica", "Latin America": "Latinoamérica",
    "Caribbean": "Caribe", "Middle East": "Medio Oriente",
    "Asia Pacific": "Asia-Pacífico", "APAC": "Asia-Pacífico", "EMEA": "Europa, Medio Oriente y África",
    "LATAM": "Latinoamérica", "NA": "Norteamérica",
}


def etiqueta_region(region):
    """'Europe' -> 'Europa'. Si la region no esta en el diccionario, devuelve el original."""
    region = str(region).strip()
    return NOMBRE_REGION.get(region, region)


# --- Nombres de paises (ingles -> español) para leyendas y selectores ---
NOMBRE_PAIS = {
    "Peru": "Perú", "Brazil": "Brasil", "Mexico": "México", "Colombia": "Colombia",
    "Chile": "Chile", "Argentina": "Argentina", "Uruguay": "Uruguay", "Bolivia": "Bolivia",
    "Paraguay": "Paraguay", "Venezuela": "Venezuela", "Ecuador": "Ecuador",
    "Costa Rica": "Costa Rica", "Guatemala": "Guatemala", "Honduras": "Honduras",
    "Nicaragua": "Nicaragua", "Panama": "Panamá", "Dominican Republic": "República Dominicana",
    "Cuba": "Cuba", "El Salvador": "El Salvador",
    "United States": "Estados Unidos", "USA": "Estados Unidos", "United States of America": "Estados Unidos",
    "Canada": "Canadá", "United Kingdom": "Reino Unido", "UK": "Reino Unido",
    "Spain": "España", "France": "Francia", "Germany": "Alemania", "Italy": "Italia",
    "Portugal": "Portugal", "Netherlands": "Países Bajos", "Belgium": "Bélgica",
    "Switzerland": "Suiza", "Sweden": "Suecia", "Norway": "Noruega", "Denmark": "Dinamarca",
    "Finland": "Finlandia", "Ireland": "Irlanda", "Austria": "Austria", "Greece": "Grecia",
    "Poland": "Polonia", "Czech Republic": "República Checa", "Czechia": "Chequia",
    "Hungary": "Hungría", "Russia": "Rusia", "Turkey": "Turquía",
    "China": "China", "Japan": "Japón", "South Korea": "Corea del Sur", "India": "India",
    "Indonesia": "Indonesia", "Thailand": "Tailandia", "Vietnam": "Vietnam",
    "Philippines": "Filipinas", "Singapore": "Singapur", "Malaysia": "Malasia",
    "Australia": "Australia", "New Zealand": "Nueva Zelanda", "South Africa": "Sudáfrica",
    "Egypt": "Egipto", "Nigeria": "Nigeria", "Kenya": "Kenia", "Morocco": "Marruecos",
    "Saudi Arabia": "Arabia Saudita", "United Arab Emirates": "Emiratos Árabes Unidos",
    "Israel": "Israel",
}


def etiqueta_pais(pais):
    """'Peru' -> 'Perú'. Si el pais no esta en el diccionario, devuelve el original."""
    pais = str(pais).strip()
    return NOMBRE_PAIS.get(pais, pais)


def corto(texto, n=28):
    """Recorta un texto largo agregando '…'."""
    texto = str(texto)
    return texto if len(texto) <= n else texto[: n - 1] + "…"
