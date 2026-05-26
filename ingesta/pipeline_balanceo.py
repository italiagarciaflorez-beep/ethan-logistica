# ============================================================
#  ETHAN — Pipeline de ingesta de balanceos
#  Escanea las carpetas, lee los archivos y los indexa
#  en ChromaDB y SQLite
# ============================================================

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from config import RUTAS_BALANCEOS, CARPETA_VIEJAS, CHROMA_PATH, SQLITE_PATH
from ingesta.lector_balanceo import (
    extraer_metadatos_nombre,
    leer_hoja_analisis,
    leer_hoja_oficial,
    construir_texto_indexable,
)
from db.gestor_db import inicializar_db, guardar_resumen, guardar_detalle


def escanear_balanceos_marca(marca: str) -> list[dict]:
    """
    Escanea todos los archivos de balanceo de una marca.
    Retorna lista de dicts con ruta y nivel (actual/historico).

    Lógica de niveles:
    - NIVEL 1A: archivos .xlsx directamente en la carpeta raíz de la marca
    - NIVEL 1B: archivos .xlsx directamente en la carpeta VIEJAS (sueltos)
    - NIVEL 2:  archivos .xlsx dentro de BALANCEOS 2024 o BALANCEOS 2025
    """
    ruta_marca = RUTAS_BALANCEOS.get(marca)
    if not ruta_marca or not os.path.exists(ruta_marca):
        print(f"⚠️  Ruta no encontrada para marca '{marca}': {ruta_marca}")
        return []

    archivos = []
    nombre_carpeta_viejas = CARPETA_VIEJAS.get(marca, "VIEJAS")
    ruta_viejas = os.path.join(ruta_marca, nombre_carpeta_viejas)

    # ── NIVEL 1A — Archivos sueltos en la raíz de la marca ──
    for f in os.listdir(ruta_marca):
        ruta_f = os.path.join(ruta_marca, f)
        if f.endswith(".xlsx") and os.path.isfile(ruta_f):
            archivos.append({"ruta": ruta_f, "nivel": "actual"})

    # ── NIVEL 1B — Archivos sueltos en la carpeta VIEJAS ──
    if os.path.exists(ruta_viejas):
        for f in os.listdir(ruta_viejas):
            ruta_f = os.path.join(ruta_viejas, f)
            if f.endswith(".xlsx") and os.path.isfile(ruta_f):
                archivos.append({"ruta": ruta_f, "nivel": "actual"})

        # ── NIVEL 2 — Históricos 2024 y 2025 ──
        for año in ["BALANCEOS 2024", "BALANCEOS 2025"]:
            ruta_año = os.path.join(ruta_viejas, año)
            if os.path.exists(ruta_año):
                for f in os.listdir(ruta_año):
                    ruta_f = os.path.join(ruta_año, f)
                    if f.endswith(".xlsx") and os.path.isfile(ruta_f):
                        archivos.append({"ruta": ruta_f, "nivel": "historico"})

    # Ignorar archivos .tmp y temporales
    archivos = [a for a in archivos
                if not Path(a["ruta"]).stem.startswith("~$")
                and not a["ruta"].endswith(".tmp")]

    print(f"📂 {marca.upper()}: {len(archivos)} archivos encontrados")
    return archivos


def indexar_balanceo(ruta_archivo: str, vectorstore, ruta_db: str):
    """
    VERSION MEJORADA: Guarda resumen Y productos en ChromaDB.
    """
    nombre_archivo = Path(ruta_archivo).name
    print(f"  📄 Indexando a fondo: {nombre_archivo}")

    metadatos = extraer_metadatos_nombre(ruta_archivo)
    analisis = leer_hoja_analisis(ruta_archivo)
    df_oficial = leer_hoja_oficial(ruta_archivo)

    # 1. Guardar en SQLite (Mantenemos tu lógica)
    import pandas as pd
    tendencia_total = 0
    if not df_oficial.empty and "TENDENCIA" in df_oficial.columns:
        # Esto convierte a número y si hay texto lo vuelve "vacío" para no dar error
        serie_numerica = pd.to_numeric(df_oficial["TENDENCIA"], errors='coerce')
        tendencia_total = int(serie_numerica.sum())

    # 2. Guardar en SQLite (Tus funciones originales se quedan IGUAL)
    guardar_resumen(ruta_db, metadatos, analisis, tendencia_total)
    guardar_detalle(ruta_db, df_oficial, metadatos)

    # 2. GUARDAR RESUMEN EN CHROMADB
    texto_resumen = construir_texto_indexable(metadatos, analisis)
    # ID único usando el nombre del archivo para evitar que se borren
    id_resumen = f"resumen_{nombre_archivo}" 
    vectorstore.add_texts(texts=[texto_resumen], metadatas=[metadatos], ids=[id_resumen])

    # 3. GUARDAR PRODUCTOS EN CHROMADB (Aquí es donde se vuelve inteligente)
    if not df_oficial.empty:
        # Convertimos los productos a texto (agrupamos de a 20 para no marear a la IA)
        productos = df_oficial.to_dict('records')
        for i in range(0, len(productos), 20):
            bloque = productos[i:i+20]
            texto_productos = f"DETALLE DE PRODUCTOS - {metadatos['marca']} {metadatos['campaña']}\n"
            for p in bloque:
                # Ajusta los nombres de columnas (ITEM_SAP, ESTACION) según tu Excel
                sap = p.get('ITEM/SAP', p.get('ITEM_SAP', p.get('SAP', p.get('ITEM/_SAP', 'N/A'))))
                est = p.get('ESTACION', p.get('ESTACIÓN', p.get('EST', 'N/A')))
                cant = p.get('TENDENCIA', p.get('CANTIDAD', 0))
                texto_productos += f"- SAP: {sap} | Estación: {est} | Cantidad: {cant}\n"
            
            id_bloque = f"prod_{nombre_archivo}_{i}"
            vectorstore.add_texts(texts=[texto_productos], metadatas=[metadatos], ids=[id_bloque])

    print(f"  ✅ {metadatos['marca'].upper()} | {metadatos['campaña']} | Procesado completo")


def ejecutar_ingesta_completa():
    """
    Corre la ingesta completa de todos los balanceos
    de todas las marcas.
    """
    from langchain_ollama import OllamaEmbeddings
    from langchain_community.vectorstores import Chroma
    from config import EMBEDDING_MODEL

    print("\n" + "="*60)
    print("  ETHAN — Iniciando ingesta de balanceos")
    print("="*60 + "\n")

    # Inicializar SQLite
    inicializar_db(SQLITE_PATH)

    # Inicializar ChromaDB
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="balanceos"
    )

    marcas = ["carmel", "loguin", "pcfk", "digital", "ecuador"]
    total_indexados = 0

    for marca in marcas:
        archivos = escanear_balanceos_marca(marca)
        for archivo in archivos:
            try:
                indexar_balanceo(archivo["ruta"], vectorstore, SQLITE_PATH)
                total_indexados += 1
            except Exception as e:
                print(f"  ❌ Error en {archivo['ruta']}: {e}")

    print(f"\n{'='*60}")
    print(f"  ✅ Ingesta completada: {total_indexados} balanceos indexados")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    ejecutar_ingesta_completa()
