# ============================================================
#  ETHAN — Configuración central
# ============================================================

import os

# Detecta la carpeta donde vive este archivo config.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define las rutas de las bases de datos de forma absoluta
CHROMA_PATH = os.path.join(BASE_DIR, "db", "chroma")
SQLITE_PATH = os.path.join(BASE_DIR, "db", "ethan.db")

# Ajusta también la RUTA_BASE_CAD si quieres que sea absoluta dentro del proyecto
# O déjala como /mnt/copernico si el montaje es fijo.


#RUTA_BASE_CAD = "/mnt/copernico/CAD"
# En config.py, cambia esto:
RUTA_BASE_CAD = "/mnt/copernico"  # Eliminamos el /CAD del final

# 2. Ahora usamos esa variable para construir las demás (Fíjate en la 'f' al inicio)
RUTAS_BALANCEOS = {
    "base":    f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS",
    "carmel":  f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/BALANCEOS CARMEL",
    "loguin":  f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/BALANCEOS LOGUIN",
    "pcfk":    f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/BALANCEOS PCFK",
    "digital": f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/BALANCEO CANAL DIGITAL",
    "ecuador": f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/BALANCEO EXPO-ECUADOR",
    "comunes": f"{RUTA_BASE_CAD}/2026 BALANCEOS PICKING/2026 PROXIMAS CAMPAÑAS/Balanceo Plu comunes",
}

CARPETA_VIEJAS = {
    "carmel": "BALANCEOS CAMPAÑAS VIEJAS CRML",
    "loguin": "BALANCEOS CAMPAÑAS VIEJAS LGIN",
    "pcfk":   "BALANCEOS CAMPAÑAS VIEJAS PCFK",
}

SINONIMOS_MARCAS = {
    "carmel":  ["carmel", "crml", "carml", "carmle", "camel"],
    "loguin":  ["loguin", "login", "logiun", "logín", "logi", "lgin"],
    "pcfk":    ["pcfk", "pacifika", "pacifia", "pacifica", "paficika",
                "pcfck", "pcfj", "pacifka", "packfika"],
    "digital": ["digital", "canal digital", "canaldigital", "likeme"],
    "ecuador": ["ecuador", "expo ecuador", "exportacion", "exportaciones"],
    "comunes": ["comunes", "plu comunes", "plurcomunes"],
}

LLM_MODEL       = "llama3.2:3b"
EMBEDDING_MODEL = "nomic-embed-text"



CHUNK_SIZE    = 500
CHUNK_OVERLAP = 80
TOP_K         = 5