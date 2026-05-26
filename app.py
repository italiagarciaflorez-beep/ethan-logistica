# ============================================================
#  ETHAN — Interfaz Chainlit
#  Abre el chat en el navegador automáticamente
#  Ejecutar: chainlit run app.py
# ============================================================

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import chainlit as cl
from core.ethan_chat import EthanChat

# Instancia global de Ethan
ethan: EthanChat = None


@cl.on_chat_start
async def inicio():
    """Se ejecuta cuando el usuario abre el chat."""
    global ethan

    await cl.Message(
        content=(
            "👋 **Hola, soy Ethan**, el asistente de logística de Línea Directa.\n\n"
            "Por ahora soy experto en **balanceos de picking**. Puedo ayudarte con:\n\n"
            "• Ver los balanceos actuales de Carmel, Loguin o Pacifika\n"
            "• Consultar resúmenes de campañas específicas\n"
            "• Comparar campañas entre sí\n"
            "• Analizar tendencias y artículos\n\n"
            "¿En qué te puedo ayudar?"
        )
    ).send()

    # Inicializar Ethan (carga modelos)
    msg = cl.Message(content="⏳ Cargando modelos...")
    await msg.send()

    ethan = EthanChat()

    msg.content = "✅ Listo. ¿Cuál es tu primera pregunta?"
    await msg.update()


@cl.on_message
async def mensaje(message: cl.Message):
    """Se ejecuta con cada mensaje del usuario."""
    global ethan

    if ethan is None:
        await cl.Message(content="⏳ Todavía cargando, espera un momento...").send()
        return

    # Mostrar indicador de escritura
    async with cl.Step(name="Consultando...") as step:
        respuesta = ethan.responder(message.content)
        step.output = "Listo"

    await cl.Message(content=respuesta).send()


@cl.on_chat_end
async def fin():
    """Se ejecuta cuando el usuario cierra el chat."""
    pass
