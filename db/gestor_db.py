# ============================================================
#  ETHAN — Gestor de base de datos SQLite
#  Almacena resúmenes y detalles de balanceos
#  para consultas analíticas y comparativas
# ============================================================

import sqlite3
import pandas as pd
from pathlib import Path


def inicializar_db(ruta_db: str):
    """Crea las tablas si no existen."""
    Path(ruta_db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ruta_db)
    cur = conn.cursor()

    # Tabla de resúmenes (una fila por balanceo)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resumen_balanceos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            archivo          TEXT,
            ruta             TEXT UNIQUE,
            marca            TEXT,
            campaña          TEXT,
            numero_campaña   INTEGER,
            linea            TEXT,
            bin              TEXT,
            nivel            TEXT,
            fecha_mod        REAL,
            fecha_mod_str    TEXT,
            plu_total        INTEGER,
            estaciones_nec   INTEGER,
            estaciones_disp  INTEGER,
            ubicaciones      INTEGER,
            total_posiciones INTEGER,
            tendencia_total  INTEGER,
            indexado_en      TEXT
        )
    """)

    # Tabla de detalle (una fila por artículo por balanceo)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_balanceos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            marca           TEXT,
            campaña         TEXT,
            numero_campaña  INTEGER,
            linea           TEXT,
            bin             TEXT,
            nivel           TEXT,
            fecha_mod       REAL,
            material        TEXT,
            item_sap        TEXT,
            valor_matriz    TEXT,
            descripcion     TEXT,
            tendencia       INTEGER,
            estacion        INTEGER,
            color           TEXT,
            ubica           INTEGER,
            balanceo_sap    TEXT,
            categoria_ubic  TEXT,
            linea_manhattan TEXT,
            est_manhattan   TEXT,
            color_manhattan TEXT,
            ubica_manhattan TEXT,
            bal_manhattan   TEXT,
            plu_comunes     TEXT,
            max_uom         INTEGER,
            min_uom         INTEGER,
            is_replenish    TEXT
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Base de datos inicializada: {ruta_db}")


def guardar_resumen(ruta_db: str, metadatos: dict, analisis: dict, tendencia_total: int = 0):
    """Guarda o actualiza el resumen de un balanceo."""
    from datetime import datetime
    conn = sqlite3.connect(ruta_db)
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO resumen_balanceos (
            archivo, ruta, marca, campaña, numero_campaña,
            linea, bin, nivel, fecha_mod, fecha_mod_str,
            plu_total, estaciones_nec, estaciones_disp,
            ubicaciones, total_posiciones, tendencia_total, indexado_en
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        metadatos["archivo"],
        metadatos["ruta"],
        metadatos["marca"],
        metadatos["campaña"],
        metadatos["numero_campaña"],
        metadatos["linea"],
        metadatos["bin"],
        metadatos["nivel"],
        metadatos["fecha_mod"],
        metadatos["fecha_mod_str"],
        analisis.get("plu_total", 0),
        analisis.get("estaciones_nec", 0),
        analisis.get("estaciones_disp", 0),
        analisis.get("ubicaciones", 0),
        analisis.get("total_posiciones", 0),
        tendencia_total,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
    ))

    conn.commit()
    conn.close()


def guardar_detalle(ruta_db: str, df: pd.DataFrame, metadatos: dict):
    """Guarda el detalle de artículos del balanceo en SQLite."""
    if df.empty:
        return

    conn = sqlite3.connect(ruta_db)

    # ✅ CORRECCIÓN 2: Eliminar por archivo específico usando fecha_mod
    # Evita duplicados cuando hay varios archivos con misma campaña/linea/bin
    conn.execute("""
        DELETE FROM detalle_balanceos
        WHERE marca=? AND campaña=? AND linea=? AND bin=? AND fecha_mod=?
    """, (
        metadatos["marca"],
        metadatos["campaña"],
        metadatos["linea"],
        metadatos["bin"],
        metadatos["fecha_mod"],
    ))

    # ✅ CORRECCIÓN 1: Mapeo con y sin guión bajo para descripcion
    col_map = {
        "MATERIAL":              "material",
        "ITEM/SAP":              "item_sap",
        "VALOR_MATRIZ":          "valor_matriz",
        "DESCRIPCION_":          "descripcion",   # con guión bajo
        "DESCRIPCION":           "descripcion",   # sin guión bajo
        "TENDENCIA":             "tendencia",
        "ESTACION":              "estacion",
        "COLOR":                 "color",
        "UBICA":                 "ubica",
        "BALANCEO_SAP_/_OSIRIS": "balanceo_sap",
        "CATEGORIA_UBICACION":   "categoria_ubic",
        "LINEA_MANHATTAN":       "linea_manhattan",
        "ESTACION_MANHATTAN":    "est_manhattan",
        "COLOR_MANHATTAN":       "color_manhattan",
        "UBICA_MANHATTAN":       "ubica_manhattan",
        "BALANCEO_MANHATTAN":    "bal_manhattan",
        "PLU_COMUNES":           "plu_comunes",
        "MAXUOMQUANTITY":        "max_uom",
        "MINUOMQUANTITY":        "min_uom",
        "ISREPLENISHABLE":       "is_replenish",
    }

    # Renombrar columnas que existan
    df_renamed = df.rename(columns=col_map)

    # Agregar metadatos a cada fila
    df_renamed["marca"]          = metadatos["marca"]
    df_renamed["campaña"]        = metadatos["campaña"]
    df_renamed["numero_campaña"] = metadatos["numero_campaña"]
    df_renamed["linea"]          = metadatos["linea"]
    df_renamed["bin"]            = metadatos["bin"]
    df_renamed["nivel"]          = metadatos["nivel"]
    df_renamed["fecha_mod"]      = metadatos["fecha_mod"]

    # Guardar solo las columnas que existen en la tabla
    columnas_tabla = [
        "marca", "campaña", "numero_campaña", "linea", "bin", "nivel", "fecha_mod",
        "material", "item_sap", "valor_matriz", "descripcion", "tendencia",
        "estacion", "color", "ubica", "balanceo_sap", "categoria_ubic",
        "linea_manhattan", "est_manhattan", "color_manhattan", "ubica_manhattan",
        "bal_manhattan", "plu_comunes", "max_uom", "min_uom", "is_replenish"
    ]
    cols_disponibles = [c for c in columnas_tabla if c in df_renamed.columns]
    df_final = df_renamed[cols_disponibles]

    df_final.to_sql("detalle_balanceos", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


def consultar_balanceos(ruta_db: str, marca: str = None,
                        nivel: str = None, año: str = None) -> pd.DataFrame:
    """Consulta resúmenes de balanceos con filtros opcionales."""
    conn = sqlite3.connect(ruta_db)
    query = "SELECT * FROM resumen_balanceos WHERE 1=1"
    params = []

    if marca:
        query += " AND marca = ?"
        params.append(marca)
    if nivel:
        query += " AND nivel = ?"
        params.append(nivel)
    if año:
        query += " AND fecha_mod_str LIKE ?"
        params.append(f"{año}%")

    query += " ORDER BY fecha_mod DESC"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def comparar_campañas(ruta_db: str, marca: str,
                      campaña1: str, campaña2: str,
                      archivo1: str = None, archivo2: str = None) -> dict:
    """Compara dos campañas. Si se pasan archivos específicos,
    los usa para obtener los datos exactos."""
    conn = sqlite3.connect(ruta_db)

    def obtener_fila(campaña, archivo):
        if archivo:
            query = """
                SELECT campaña, plu_total, tendencia_total
                FROM resumen_balanceos
                WHERE marca = ? AND archivo = ?
                LIMIT 1
            """
            df = pd.read_sql_query(query, conn, params=[marca, archivo])
        else:
            query = """
                SELECT campaña, plu_total, tendencia_total
                FROM resumen_balanceos
                WHERE marca = ? AND campaña = ?
                ORDER BY fecha_mod DESC
                LIMIT 1
            """
            df = pd.read_sql_query(query, conn, params=[marca, campaña])
        return df.iloc[0] if not df.empty else None

    c1 = obtener_fila(campaña1, archivo1)
    c2 = obtener_fila(campaña2, archivo2)
    conn.close()

    if c1 is None or c2 is None:
        return {}

    return {
        "marca":             marca,
        "campaña_anterior":  c1["campaña"],
        "campaña_actual":    c2["campaña"],
        "plu_anterior":      int(c1["plu_total"]),
        "plu_actual":        int(c2["plu_total"]),
        "plu_diferencia":    int(c2["plu_total"]) - int(c1["plu_total"]),
        "tend_anterior":     int(c1["tendencia_total"]),
        "tend_actual":       int(c2["tendencia_total"]),
        "tend_diferencia":   int(c2["tendencia_total"]) - int(c1["tendencia_total"]),
        "tend_variacion_pct": round(
            (int(c2["tendencia_total"]) - int(c1["tendencia_total"])) /
            max(int(c1["tendencia_total"]), 1) * 100, 1
        ),
    }