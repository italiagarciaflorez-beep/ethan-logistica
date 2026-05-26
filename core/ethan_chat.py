# ============================================================
#  ETHAN — Motor de conversación v9+
#  Base: v9 intacta + flujo de análisis + _detectar_opcion robusto
# ============================================================

import os
import re
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import pandas as pd
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from config import (
    LLM_MODEL, EMBEDDING_MODEL, CHROMA_PATH, SQLITE_PATH,
    RUTAS_BALANCEOS, CARPETA_VIEJAS
)
from core.marcas import normalizar_marca, nombre_display
from db.gestor_db import consultar_balanceos, comparar_campañas
from datetime import datetime


# ── Estados (v9 originales + nuevos para análisis) ───────────
ESTADO_INICIO           = "inicio"
ESTADO_LISTA_ARCHIVOS   = "lista_archivos"
ESTADO_SIGUIENTE_ACCION = "siguiente_accion"
ESTADO_COMPARANDO       = "comparando"
ESTADO_TIPO_HISTORICO   = "tipo_historico"

# Nuevos estados para el flujo de análisis
ESTADO_ANALISIS_TIPO    = "analisis_tipo"
ESTADO_ANALISIS_MARCA   = "analisis_marca"
ESTADO_ANALISIS_PERIODO = "analisis_periodo"
ESTADO_ANALISIS_ARCHIVO = "analisis_archivo"

SYSTEM_PROMPT = """
Eres Ethan, el asistente experto en logística de Línea Directa S.A.S.
Tu especialidad actual es el análisis de balanceos de picking.

REGLAS ESTRICTAS:
1. Responde SOLO con información del contexto proporcionado.
2. Si no tienes la información di: "No tengo esa información disponible."
3. Siempre cita el archivo fuente y la campaña.
4. Muestra las tablas de forma clara y ordenada.
5. Habla siempre en español.
6. NUNCA inventes datos ni análisis.
7. Muestra la tabla por estación UNA SOLA VEZ — no la repitas.

Formato de respuesta:
RESUMEN DEL BALANCEO
- Total PLU: X
- Estaciones necesarias: X
- Estaciones disponibles: X
- Ubicaciones por estación: X
- Tendencia total: X

TABLA POR ESTACIÓN:
[tabla completa — solo una vez]

Fuente: [nombre del archivo]
Campaña: [campaña]

CONTEXTO:
{context}
"""

PROMPT_RAG = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{pregunta}"),
])


class EthanChat:

    def __init__(self):
        print("🤖 Iniciando Ethan...")
        self.llm = ChatOllama(model=LLM_MODEL, temperature=0.1)
        self.embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
        self.vectorstore = Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=self.embeddings,
            collection_name="balanceos"
        )
        # ── Estado v9 original ──
        self._estado          = ESTADO_INICIO
        self._marca_activa    = None
        self._archivo_activo  = None
        self._lista_archivos  = []
        self._lista_campanas  = []
        self._tipo_consulta   = None

        # ── Estado nuevo para análisis ──
        self._tipo_analisis    = None   # 1-5
        self._periodo_analisis = None   # "actual", "2025", "2024"

        print("✅ Ethan listo para responder\n")

    # ════════════════════════════════════════════════════════════
    # ROUTER PRINCIPAL (v9 intacto + nuevos estados)
    # ════════════════════════════════════════════════════════════

    def responder(self, pregunta: str) -> str:
        texto = pregunta.strip()

        if self._estado == ESTADO_LISTA_ARCHIVOS:
            return self._manejar_seleccion_archivo(texto)

        if self._estado == ESTADO_SIGUIENTE_ACCION:
            return self._manejar_siguiente_accion(texto)

        if self._estado == ESTADO_COMPARANDO:
            return self._manejar_seleccion_campana(texto)

        if self._estado == ESTADO_TIPO_HISTORICO:
            return self._manejar_tipo_historico(texto)

        # Nuevos estados de análisis
        if self._estado == ESTADO_ANALISIS_TIPO:
            return self._manejar_analisis_tipo(texto)

        if self._estado == ESTADO_ANALISIS_MARCA:
            return self._manejar_analisis_marca(texto)

        if self._estado == ESTADO_ANALISIS_PERIODO:
            return self._manejar_analisis_periodo(texto)

        if self._estado == ESTADO_ANALISIS_ARCHIVO:
            return self._manejar_analisis_archivo(texto)

        return self._manejar_inicio(texto)

    # ════════════════════════════════════════════════════════════
    # INICIO (v9 intacto)
    # ════════════════════════════════════════════════════════════

    def _manejar_inicio(self, texto: str) -> str:
        texto_lower = texto.lower()

        # Detectar intención de análisis ANTES de buscar marca
        PALABRAS_ANALISIS = ["analiz", "analís", "análisis", "análisis"]
        if any(p in texto_lower for p in PALABRAS_ANALISIS):
            return self._mostrar_menu_analisis()

        marca = self._detectar_marca(texto_lower)
        if marca:
            self._tipo_consulta = self._detectar_tipo_consulta(texto_lower)
            self._marca_activa  = marca
            return self._mostrar_lista(marca, texto_lower)

        return ("No entendí qué marca buscas. ¿De cuál te gustaría ver balanceos?\n\n"
                "• Carmel\n• Loguin\n• Pacifika\n• Canal Digital\n• Ecuador\n\n"
                "O escribe **analizar** para hacer un análisis de tendencias.")

    # ════════════════════════════════════════════════════════════
    # LISTA Y SELECCIÓN DE ARCHIVOS (v9 intacto)
    # ════════════════════════════════════════════════════════════

    def _mostrar_lista(self, marca: str, pregunta: str = "") -> str:
        pide_2024 = "2024" in pregunta
        pide_2025 = "2025" in pregunta
        pide_historicos = any(p in pregunta for p in
                              ["2024", "2025", "histórico", "historico", "viejo", "viejas"])

        ruta_marca = RUTAS_BALANCEOS.get(marca)
        if not ruta_marca or not os.path.exists(ruta_marca):
            return f"No tengo acceso a la carpeta de {nombre_display(marca)}."

        nombre_viejas = CARPETA_VIEJAS.get(marca, "BALANCEOS CAMPAÑAS VIEJAS")
        ruta_viejas   = os.path.join(ruta_marca, nombre_viejas)

        if pide_2024 and os.path.exists(os.path.join(ruta_viejas, "BALANCEOS 2024")):
            archivos = self._leer_excels(os.path.join(ruta_viejas, "BALANCEOS 2024"))
            titulo   = f"Balanceos históricos 2024 — {nombre_display(marca)}"
        elif pide_2025 and os.path.exists(os.path.join(ruta_viejas, "BALANCEOS 2025")):
            archivos = self._leer_excels(os.path.join(ruta_viejas, "BALANCEOS 2025"))
            titulo   = f"Balanceos históricos 2025 — {nombre_display(marca)}"
        elif pide_historicos:
            return (f"¿Qué año de históricos de {nombre_display(marca)} necesitas?\n\n"
                    f"• 2025\n• 2024")
        else:
            actuales_raiz   = self._leer_excels(ruta_marca)
            actuales_viejas = self._leer_excels(ruta_viejas) if os.path.exists(ruta_viejas) else []
            archivos = actuales_raiz + actuales_viejas
            titulo   = f"Balanceos actuales 2026 — {nombre_display(marca)}"

        if not archivos:
            return f"No encontré archivos de balanceo para {nombre_display(marca)}."

        archivos.sort(key=lambda x: x["fecha_mod"], reverse=True)
        self._lista_archivos = archivos
        self._estado         = ESTADO_LISTA_ARCHIVOS

        respuesta = f"📂 **{titulo}**\n\n"
        for i, a in enumerate(archivos, 1):
            respuesta += f"{i}. {a['nombre']}  ({a['fecha_str']})\n"
        respuesta += "\n¿Cuál quieres ver? Escribe el número."
        return respuesta

    def _manejar_seleccion_archivo(self, texto: str) -> str:
        match = re.search(r'\d+', texto)
        if not match:
            return "Escribe el número del balanceo que quieres ver."

        indice = int(match.group()) - 1
        if indice < 0 or indice >= len(self._lista_archivos):
            return f"Elige un número entre 1 y {len(self._lista_archivos)}."

        archivo = self._lista_archivos[indice]
        self._archivo_activo = archivo

        respuesta = self._obtener_info_archivo(archivo)
        respuesta += self._menu_siguiente_accion()
        self._estado = ESTADO_SIGUIENTE_ACCION
        return respuesta

    def _obtener_info_archivo(self, archivo: dict) -> str:
        nombre = archivo['nombre']

        # DESPUÉS — normaliza espacios dobles
        nombre_normalizado = " ".join(nombre.split())
        retriever = self.vectorstore.as_retriever(
            search_kwargs={
                "k": 2,
                "filter": {"archivo": nombre_normalizado} if nombre_normalizado else None
            }
        )
        docs = retriever.invoke(f"resumen tabla estacion {nombre}")

        if not docs:
            filtros = {"marca": self._marca_activa} if self._marca_activa else {}
            retriever = self.vectorstore.as_retriever(
                search_kwargs={"k": 3, "filter": filtros if filtros else None}
            )
            docs = retriever.invoke(f"resumen tabla estacion {nombre}")

        contexto = "\n\n---\n\n".join([d.page_content for d in docs])

        if not contexto.strip():
            return f"No encontré información indexada para **{nombre}**.\n\n"

        prompt = PROMPT_RAG.format_messages(
            context=contexto,
            pregunta=f"Muestra el resumen completo y la tabla por estación del balanceo {nombre}. NO repitas la tabla dos veces."
        )
        respuesta = self.llm.invoke(prompt)
        return respuesta.content + "\n\n"

    # ════════════════════════════════════════════════════════════
    # MENÚ SIGUIENTE ACCIÓN (v9 + opción 3 analizar + opción 4 y 5)
    # ════════════════════════════════════════════════════════════

    def _menu_siguiente_accion(self) -> str:
        marca = nombre_display(self._marca_activa) if self._marca_activa else "esta marca"
        return (f"---\n"
                f"**¿Qué quieres hacer ahora?**\n\n"
                f"1. Ver otro balanceo de {marca}\n"
                f"2. Comparar con otra campaña\n"
                f"3. Hacer análisis\n"
                f"4. Ver balanceos de otra marca\n"
                f"5. Nueva consulta")

    def _manejar_siguiente_accion(self, texto: str) -> str:
        texto_lower = texto.lower()
        opcion = self._detectar_opcion(texto_lower)

        if opcion == 1 or "otro balanceo" in texto_lower:
            self._estado = ESTADO_LISTA_ARCHIVOS
            return self._mostrar_lista(self._marca_activa)

        elif opcion == 2 or "comparar" in texto_lower:
            return self._iniciar_comparacion()

        elif opcion == 3 or "análisis" in texto_lower or "analisis" in texto_lower or "analiz" in texto_lower:
            return self._mostrar_menu_analisis()

        elif opcion == 4 or "otra marca" in texto_lower:
            self._estado = ESTADO_INICIO
            self._marca_activa = None
            return ("¿De qué marca quieres ver los balanceos?\n\n"
                    "• Carmel\n• Loguin\n• Pacifika\n"
                    "• Canal Digital\n• Ecuador")

        elif opcion == 5 or "nueva consulta" in texto_lower:
            self._estado = ESTADO_INICIO
            return ("¿En qué te puedo ayudar?\n\n"
                    "• Ver balanceos → escribe el nombre de la marca\n"
                    "• Hacer análisis → escribe **analizar**")

        else:
            self._estado = ESTADO_INICIO
            return self._manejar_inicio(texto)

    # ════════════════════════════════════════════════════════════
    # COMPARACIÓN (v9 intacto)
    # ════════════════════════════════════════════════════════════

    def _iniciar_comparacion(self) -> str:
        if not self._marca_activa:
            self._estado = ESTADO_INICIO
            return "¿De qué marca quieres comparar campañas?"

        self._estado = ESTADO_TIPO_HISTORICO
        campana_actual = self._extraer_campana_archivo(
            self._archivo_activo['nombre'] if self._archivo_activo else "")

        return (f"El balanceo actual es **{campana_actual}**.\n\n"
                f"¿Con qué quieres comparar?\n\n"
                f"1. Con otro balanceo actual de {nombre_display(self._marca_activa)}\n"
                f"2. Con un balanceo histórico (2025 o 2024)")

    def _manejar_tipo_historico(self, texto: str) -> str:
        opcion = self._detectar_opcion(texto.lower())

        if opcion == 1 or "actual" in texto.lower():
            return self._listar_campanas_para_comparar(historico=False)
        elif opcion == 2 or "histórico" in texto.lower() or "historico" in texto.lower():
            return self._listar_campanas_para_comparar(historico=True)
        else:
            return ("¿Con qué quieres comparar?\n\n"
                    "1. Con otro balanceo actual\n"
                    "2. Con un balanceo histórico")

    def _listar_campanas_para_comparar(self, historico: bool = False) -> str:
        # v9: filtra por archivo != activo (más preciso que por campaña)
        nombre_archivo_activo = self._archivo_activo['nombre'] if self._archivo_activo else ""
        nivel_busqueda = 'historico' if historico else 'actual'

        conn = sqlite3.connect(SQLITE_PATH)
        query = """
            SELECT DISTINCT archivo, campaña, fecha_mod_str 
            FROM resumen_balanceos 
            WHERE marca = ? AND nivel = ? AND archivo != ?
            ORDER BY fecha_mod DESC 
            LIMIT 10
        """
        df = pd.read_sql_query(query, conn, params=[self._marca_activa, nivel_busqueda, nombre_archivo_activo])
        conn.close()

        if df.empty:
            self._estado = ESTADO_SIGUIENTE_ACCION
            return f"No encontré otros archivos en {nivel_busqueda} para comparar.\n\n" + self._menu_siguiente_accion()

        self._lista_campanas = df.to_dict('records')
        self._estado = ESTADO_COMPARANDO

        tipo_str = "HISTÓRICOS" if historico else "ACTUALES"
        respuesta = f"📂 **Comparando con {tipo_str} ({nombre_display(self._marca_activa)})**\n"
        respuesta += f"Archivo base: `{nombre_archivo_activo}`\n\n"

        for i, row in enumerate(self._lista_campanas, 1):
            respuesta += f"{i}. {row['campaña']} - {row['archivo']} ({row['fecha_mod_str']})\n"

        respuesta += "\n¿Con cuál quieres compararlo? Escribe el número."
        return respuesta

    def _manejar_seleccion_campana(self, texto: str) -> str:
        match = re.search(r'\d+', texto)
        if not match:
            return "Escribe el número de la opción que quieres elegir."

        indice = int(match.group()) - 1
        if indice < 0 or indice >= len(self._lista_campanas):
            return f"Elige un número entre 1 y {len(self._lista_campanas)}."

        archivo_a = self._archivo_activo['nombre']
        campana_a = self._extraer_campana_archivo(archivo_a)

        archivo_b = self._lista_campanas[indice]['archivo']
        campana_b = self._lista_campanas[indice]['campaña']

        resultado = comparar_campañas(
            SQLITE_PATH, self._marca_activa,
            campana_b, campana_a,
            archivo_b, archivo_a  # ← archivos específicos
)

        if not resultado:
            respuesta = f"No pude cruzar los datos entre {campana_a} y {campana_b}."
        else:
            respuesta = f"📊 **Comparativa: {campana_b} vs {campana_a}**\n\n"
            respuesta += f"| Métrica | {campana_b} | {campana_a} | Dif. |\n"
            respuesta += f"| :--- | :--- | :--- | :--- |\n"
            respuesta += f"| **PLU Total** | {resultado['plu_anterior']:,} | {resultado['plu_actual']:,} | {resultado['plu_diferencia']:+,} |\n"
            respuesta += f"| **Tendencia** | {resultado['tend_anterior']:,} | {resultado['tend_actual']:,} | {resultado['tend_diferencia']:+,} |\n"
            respuesta += f"\n**Variación:** {resultado['tend_variacion_pct']:+.2f}%"

        respuesta += "\n\n" + self._menu_siguiente_accion()
        self._estado = ESTADO_SIGUIENTE_ACCION
        return respuesta

    # ════════════════════════════════════════════════════════════
    # FLUJO DE ANÁLISIS (nuevo, integrado sobre v9)
    # ════════════════════════════════════════════════════════════

    def _mostrar_menu_analisis(self) -> str:
        self._estado = ESTADO_ANALISIS_TIPO
        return ("📊 **¿Qué análisis quieres hacer?**\n\n"
                "1. Top N artículos por tendencia\n"
                "2. Distribución por estación\n"
                "3. Comparación entre campañas\n"
                "4. Artículos por color\n"
                "5. Artículos por línea")

    def _manejar_analisis_tipo(self, texto: str) -> str:
        opcion = self._detectar_opcion(texto.lower())

        if opcion and 1 <= opcion <= 5:
            self._tipo_analisis = opcion

            # Opción 3 = comparación, redirigir al flujo ya existente en v9
            if opcion == 3:
                return self._iniciar_comparacion()

            # Si ya tenemos marca activa, saltamos ese paso
            if self._marca_activa:
                self._estado = ESTADO_ANALISIS_PERIODO
                return (f"¿Qué periodo de {nombre_display(self._marca_activa)}?\n\n"
                        "1. Actuales 2026\n"
                        "2. Históricos 2025\n"
                        "3. Históricos 2024")

            self._estado = ESTADO_ANALISIS_MARCA
            return ("¿De qué marca?\n\n"
                    "• Carmel\n• Loguin\n• Pacifika\n"
                    "• Canal Digital\n• Ecuador")

        return ("Elige un número del 1 al 5:\n\n"
                "1. Top N artículos por tendencia\n"
                "2. Distribución por estación\n"
                "3. Comparación entre campañas\n"
                "4. Artículos por color\n"
                "5. Artículos por línea")

    def _manejar_analisis_marca(self, texto: str) -> str:
        marca = self._detectar_marca(texto.lower())
        if not marca:
            return ("No reconocí la marca. Elige una:\n\n"
                    "• Carmel\n• Loguin\n• Pacifika\n"
                    "• Canal Digital\n• Ecuador")

        self._marca_activa = marca
        self._estado = ESTADO_ANALISIS_PERIODO
        return (f"¿Qué periodo de {nombre_display(marca)}?\n\n"
                "1. Actuales 2026\n"
                "2. Históricos 2025\n"
                "3. Históricos 2024")

    def _manejar_analisis_periodo(self, texto: str) -> str:
        opcion = self._detectar_opcion(texto.lower())
        texto_lower = texto.lower()

        if opcion == 1 or "actual" in texto_lower or "2026" in texto_lower:
            self._periodo_analisis = "actual"
        elif opcion == 2 or "2025" in texto_lower:
            self._periodo_analisis = "2025"
        elif opcion == 3 or "2024" in texto_lower:
            self._periodo_analisis = "2024"
        else:
            return ("Elige el periodo:\n\n"
                    "1. Actuales 2026\n"
                    "2. Históricos 2025\n"
                    "3. Históricos 2024")

        return self._mostrar_lista_analisis()

    def _mostrar_lista_analisis(self) -> str:
        marca   = self._marca_activa
        periodo = self._periodo_analisis

        ruta_marca = RUTAS_BALANCEOS.get(marca)
        if not ruta_marca or not os.path.exists(ruta_marca):
            return f"No tengo acceso a la carpeta de {nombre_display(marca)}."

        nombre_viejas = CARPETA_VIEJAS.get(marca, "BALANCEOS CAMPAÑAS VIEJAS")
        ruta_viejas   = os.path.join(ruta_marca, nombre_viejas)

        if periodo == "2024":
            archivos = self._leer_excels(os.path.join(ruta_viejas, "BALANCEOS 2024"))
            titulo   = f"Históricos 2024 — {nombre_display(marca)}"
        elif periodo == "2025":
            archivos = self._leer_excels(os.path.join(ruta_viejas, "BALANCEOS 2025"))
            titulo   = f"Históricos 2025 — {nombre_display(marca)}"
        else:
            actuales_raiz   = self._leer_excels(ruta_marca)
            actuales_viejas = self._leer_excels(ruta_viejas) if os.path.exists(ruta_viejas) else []
            archivos = actuales_raiz + actuales_viejas
            titulo   = f"Actuales 2026 — {nombre_display(marca)}"

        if not archivos:
            return f"No encontré archivos para {nombre_display(marca)} en ese periodo."

        archivos.sort(key=lambda x: x["fecha_mod"], reverse=True)
        self._lista_archivos = archivos
        self._estado = ESTADO_ANALISIS_ARCHIVO

        respuesta = f"📂 **{titulo}**\n\n"
        for i, a in enumerate(archivos, 1):
            respuesta += f"{i}. {a['nombre']}  ({a['fecha_str']})\n"
        respuesta += "\n¿Cuál quieres analizar? Escribe el número."
        return respuesta

    def _manejar_analisis_archivo(self, texto: str) -> str:
        match = re.search(r'\d+', texto)
        if not match:
            return "Escribe el número del balanceo que quieres analizar."

        indice = int(match.group()) - 1
        if indice < 0 or indice >= len(self._lista_archivos):
            return f"Elige un número entre 1 y {len(self._lista_archivos)}."

        archivo = self._lista_archivos[indice]
        self._archivo_activo = archivo

        resultado = self._ejecutar_analisis(archivo)
        resultado += "\n\n" + self._menu_siguiente_accion()
        self._estado = ESTADO_SIGUIENTE_ACCION
        return resultado

    def _ejecutar_analisis(self, archivo: dict) -> str:
        nombre  = archivo['nombre']
        campaña = self._extraer_campana_archivo(nombre) or "desconocida"
        marca   = self._marca_activa
        tipo    = self._tipo_analisis

        conn = sqlite3.connect(SQLITE_PATH)
        try:
            if tipo == 1:
                return self._analisis_top_tendencia(conn, marca, campaña, nombre)
            elif tipo == 2:
                return self._analisis_distribucion_estacion(conn, marca, campaña, nombre)
            elif tipo == 4:
                return self._analisis_por_color(conn, marca, campaña, nombre)
            elif tipo == 5:
                return self._analisis_por_linea(conn, marca, campaña, nombre)
            else:
                return "Tipo de análisis no reconocido."
        finally:
            conn.close()

    def _analisis_top_tendencia(self, conn, marca, campaña, nombre_archivo) -> str:
        query = """
            SELECT descripcion, item_sap, tendencia, estacion
            FROM detalle_balanceos
            WHERE marca = ? AND campaña = ?
            AND tendencia > 0
            ORDER BY tendencia DESC
            LIMIT 15
        """
        df = pd.read_sql_query(query, conn, params=[marca, campaña])

        if df.empty:
            return f"No encontré datos de detalle para {nombre_display(marca)} {campaña}."
            # ← AGREGA ESTA LÍNEA AQUÍ
        df = df.dropna(subset=['estacion', 'tendencia'])

        respuesta = f"🏆 **Top 15 artículos por tendencia — {nombre_display(marca)} {campaña}**\n\n"
        respuesta += f"{'#':<4} {'Descripción':<35} {'SAP':<12} {'Estación':<10} {'Tendencia':>10}\n"
        respuesta += "─" * 75 + "\n"
        for i, row in df.iterrows():
            desc = str(row.get('descripcion', 'N/A'))[:34]
            sap  = str(row.get('item_sap',    'N/A'))[:11]
            est  = str(row.get('estacion',    'N/A'))
            tend = f"{int(row.get('tendencia', 0)):,}"
            respuesta += f"{i+1:<4} {desc:<35} {sap:<12} {est:<10} {tend:>10}\n"

        respuesta += f"\nFuente: {nombre_archivo}"
        return respuesta

    def _analisis_distribucion_estacion(self, conn, marca, campaña, nombre_archivo) -> str:
        query = """
            SELECT estacion,
                   COUNT(item_sap) as referencias,
                   SUM(tendencia) as tendencia_total
            FROM detalle_balanceos
            WHERE marca = ? AND campaña = ?
            GROUP BY estacion
            ORDER BY estacion
        """
        df = pd.read_sql_query(query, conn, params=[marca, campaña])

        if df.empty:
            return f"No encontré datos para {nombre_display(marca)} {campaña}."

        total_ref  = df['referencias'].sum()
        total_tend = df['tendencia_total'].sum()

        respuesta = f"📊 **Distribución por estación — {nombre_display(marca)} {campaña}**\n\n"
        respuesta += f"{'Estación':<12} {'Referencias':>12} {'Tendencia':>12} {'% Tend':>8}\n"
        respuesta += "─" * 48 + "\n"
        for _, row in df.iterrows():
            if pd.isna(row['estacion']):
                continue
            pct   = round(row['tendencia_total'] / total_tend * 100, 1) if total_tend > 0 else 0
            est   = int(row['estacion'])
            refs  = int(row['referencias'])  if not pd.isna(row['referencias'])  else 0
            tend  = int(row['tendencia_total']) if not pd.isna(row['tendencia_total']) else 0
            respuesta += f"{est:<12} {refs:>12,} {tend:>12,} {pct:>7.1f}%\n"

        respuesta += "─" * 48 + "\n"
        respuesta += f"{'TOTAL':<12} {int(total_ref):>12,} {int(total_tend):>12,} {'100.0%':>8}\n"
        respuesta += f"\nFuente: {nombre_archivo}"
        return respuesta

    def _analisis_por_color(self, conn, marca, campaña, nombre_archivo) -> str:
        query = """
            SELECT color,
                   COUNT(item_sap) as referencias,
                   SUM(tendencia) as tendencia_total
            FROM detalle_balanceos
            WHERE marca = ? AND campaña = ?
            AND color IS NOT NULL AND color != ''
            GROUP BY color
            ORDER BY tendencia_total DESC
            LIMIT 20
        """
        df = pd.read_sql_query(query, conn, params=[marca, campaña])

        if df.empty:
            return f"No encontré datos de color para {nombre_display(marca)} {campaña}."

        respuesta = f"🎨 **Artículos por color — {nombre_display(marca)} {campaña}**\n\n"
        respuesta += f"{'Color':<20} {'Referencias':>12} {'Tendencia':>12}\n"
        respuesta += "─" * 48 + "\n"
        for _, row in df.iterrows():
            respuesta += f"{str(row['color']):<20} {int(row['referencias']):>12,} {int(row['tendencia_total']):>12,}\n"

        respuesta += f"\nFuente: {nombre_archivo}"
        return respuesta

    def _analisis_por_linea(self, conn, marca, campaña, nombre_archivo) -> str:
        query = """
            SELECT linea_manhattan,
                   COUNT(item_sap) as referencias,
                   SUM(tendencia) as tendencia_total
            FROM detalle_balanceos
            WHERE marca = ? AND campaña = ?
            AND linea_manhattan IS NOT NULL
            GROUP BY linea_manhattan
            ORDER BY tendencia_total DESC
        """
        df = pd.read_sql_query(query, conn, params=[marca, campaña])

        if df.empty:
            return f"No encontré datos de línea para {nombre_display(marca)} {campaña}."

        respuesta = f"📋 **Artículos por línea — {nombre_display(marca)} {campaña}**\n\n"
        respuesta += f"{'Línea':<20} {'Referencias':>12} {'Tendencia':>12}\n"
        respuesta += "─" * 48 + "\n"
        for _, row in df.iterrows():
            respuesta += f"{str(row['linea_manhattan']):<20} {int(row['referencias']):>12,} {int(row['tendencia_total']):>12,}\n"

        respuesta += f"\nFuente: {nombre_archivo}"
        return respuesta

    # ════════════════════════════════════════════════════════════
    # COMPARACIÓN (v9 intacto)
    # ════════════════════════════════════════════════════════════

    def _extraer_campana_archivo(self, nombre: str) -> str | None:
        match = re.search(r'C[-_\s]?(\d+)', nombre.upper())
        if match:
            return f"C-{int(match.group(1)):02d}"
        return None

    # ════════════════════════════════════════════════════════════
    # UTILIDADES (v9 + _detectar_opcion mejorado)
    # ════════════════════════════════════════════════════════════

    def _detectar_opcion(self, texto: str) -> int | None:
        """
        Detecta qué número eligió el usuario sin importar cómo lo escribió.
        Ejemplos válidos: "1", "2.", "opción 3", "opcion 3", "la 4", "número 5",
                          "el 2", "quiero el 1", "tercera", "primera", etc.
        """
        texto = texto.strip().lower()

        # Palabras ordinales → número
        ordinales = {
            "primer": 1, "primera": 1,
            "segund": 2, "segunda": 2,
            "tercer": 3, "tercera": 3,
            "cuart":  4, "cuarta":  4,
            "quint":  5, "quinta":  5,
        }
        for palabra, num in ordinales.items():
            if palabra in texto:
                return num

        # Buscar dígito en cualquier posición
        match = re.search(r'\b(\d+)\b', texto)
        if match:
            return int(match.group(1))

        return None

    def _detectar_marca(self, texto: str) -> str | None:
        MARCAS_PRIORIDAD = [
            ("pcfk",    ["pcfk", "pacifika", "pacifica", "pacifia", "paficika", "packfika", "pacifka"]),
            ("carmel",  ["carmel", "crml", "carml", "carmle"]),
            ("loguin",  ["loguin", "login", "logiun", "lgin"]),
            ("digital", ["digital", "canal digital"]),
            ("ecuador", ["ecuador", "expo ecuador"]),
        ]

        palabras = texto.lower().split()

        for marca, sinonimos in MARCAS_PRIORIDAD:
            for palabra in palabras:
                if palabra in sinonimos:
                    return marca

        for i in range(len(palabras) - 1):
            frase = f"{palabras[i]} {palabras[i+1]}"
            for marca, sinonimos in MARCAS_PRIORIDAD:
                if frase in sinonimos:
                    return marca

        for marca, sinonimos in MARCAS_PRIORIDAD:
            for sinonimo in sinonimos:
                for palabra in palabras:
                    if len(palabra) >= 4 and len(sinonimo) >= 4:
                        if sinonimo in palabra or palabra in sinonimo:
                            return marca
        return None

    def _detectar_tipo_consulta(self, texto: str) -> str:
        if any(p in texto for p in ["comparar", "compara", "vs", "diferencia"]):
            return "comparar"
        if any(p in texto for p in ["top", "artículo", "tendencia"]):
            return "analisis"
        return "resumen"

    def _leer_excels(self, ruta: str) -> list:
        if not os.path.exists(ruta):
            return []
        archivos = []
        for f in os.listdir(ruta):
            ruta_f = os.path.join(ruta, f)
            if f.endswith(".xlsx") and os.path.isfile(ruta_f) and not f.startswith("~$"):
                fecha_mod = os.path.getmtime(ruta_f)
                archivos.append({
                    "nombre":    f,
                    "ruta":      ruta_f,
                    "fecha_mod": fecha_mod,
                    "fecha_str": datetime.fromtimestamp(fecha_mod).strftime("%d/%m/%Y"),
                })
        return archivos


if __name__ == "__main__":
    ethan = EthanChat()
    print("💬 Escribe tu pregunta (o 'salir' para terminar)\n")
    while True:
        pregunta = input("Tú: ").strip()
        if pregunta.lower() in ["salir", "exit", "quit"]:
            break
        if not pregunta:
            continue
        respuesta = ethan.responder(pregunta)
        print(f"\nEthan: {respuesta}\n")