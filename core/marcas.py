# ============================================================
#  ETHAN — Normalizador de marcas
#  Convierte cualquier forma de escribir la marca
#  al nombre canónico interno
# ============================================================

from config import SINONIMOS_MARCAS
import difflib

def normalizar_marca(texto: str) -> str | None:
    """
    Recibe cualquier texto y retorna la marca canónica.
    Ejemplos:
        "pacifika"  → "pcfk"
        "carmle"    → "carmel"
        "login"     → "loguin"
        "digital"   → "digital"
    Retorna None si no reconoce la marca.
    """
    texto = texto.lower().strip()

    # Búsqueda exacta primero
    for marca, sinonimos in SINONIMOS_MARCAS.items():
        if texto in sinonimos:
            return marca

    # Búsqueda por contenido parcial
    for marca, sinonimos in SINONIMOS_MARCAS.items():
        for sinonimo in sinonimos:
            if sinonimo in texto or texto in sinonimo:
                return marca

    # Búsqueda difusa (tolerancia a errores de escritura)
    todos = []
    for marca, sinonimos in SINONIMOS_MARCAS.items():
        for sinonimo in sinonimos:
            todos.append((sinonimo, marca))

    coincidencias = difflib.get_close_matches(
        texto,
        [s for s, _ in todos],
        n=1,
        cutoff=0.75
    )

    if coincidencias:
        for sinonimo, marca in todos:
            if sinonimo == coincidencias[0]:
                return marca

    return None


def nombre_display(marca: str) -> str:
    """Retorna el nombre bonito para mostrar al usuario."""
    nombres = {
        "carmel":  "Carmel",
        "loguin":  "Loguin",
        "pcfk":    "Pacifika",
        "digital": "Canal Digital",
        "ecuador": "Ecuador",
        "comunes": "PLU Comunes",
    }
    return nombres.get(marca, marca.upper())


# ── Test rápido ──────────────────────────────────────────────
if __name__ == "__main__":
    pruebas = [
        "pacifika", "carmle", "login", "CRML",
        "carmel", "pcfk", "digital", "ecuador",
        "pacifica", "logiun", "paficika"
    ]
    for p in pruebas:
        resultado = normalizar_marca(p)
        print(f"  '{p}' → {resultado} ({nombre_display(resultado) if resultado else 'NO RECONOCIDA'})")
