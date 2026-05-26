# ETHAN — Asistente de Logística Línea Directa

## ¿Qué es Ethan?
Ethan es el asistente inteligente de logística de Línea Directa.
Responde preguntas sobre la información de las carpetas del servidor,
usando inteligencia artificial que corre completamente en tu PC,
sin internet y sin que los datos salgan de la empresa.

---

## Estructura del proyecto

```
ethan/
├── app.py                    ← Interfaz Chainlit (el chat)
├── config.py                 ← Configuración central
├── INICIAR_ETHAN.bat         ← Doble clic para abrir
├── INSTALAR.bat              ← Ejecutar una sola vez
│
├── core/
│   ├── ethan_chat.py         ← Motor de conversación RAG
│   └── marcas.py             ← Normalizador de marcas
│
├── ingesta/
│   ├── pipeline_balanceo.py  ← Pipeline de ingesta
│   └── lector_balanceo.py    ← Lector de archivos Excel
│
└── db/
    └── gestor_db.py          ← Gestor SQLite
```

---

## Lo que sabe Ethan ahora

### Módulo 1 — Balanceos de Picking ✅
- Balanceos actuales de Carmel, Loguin, Pacifika
- Balanceos de Canal Digital y Ecuador
- Históricos 2024 y 2025
- Comparación entre campañas
- Análisis de tendencias y artículos

### Próximos módulos (en desarrollo)
- Módulo 2 — (siguiente carpeta)
- Módulo 3 — (siguiente carpeta)

---

## Preguntas que puede responder

### Navegación
- "¿Qué balanceos hay de Carmel?"
- "Muéstrame los balanceos actuales de Pacifika"
- "¿Tienes balanceos del 2024 de Loguin?"

### Resúmenes
- "¿Cómo quedó el último balanceo de Carmel?"
- "¿Cuántos PLU tiene el C-08 de Carmel?"
- "¿Cuántas estaciones tiene el último balanceo de Pacifika?"
- "¿Cuál es la tendencia total del C-06?"

### Comparaciones
- "Compara el C-07 y C-08 de Carmel"
- "¿El último balanceo de Pacifika tiene más PLU que el anterior?"
- "¿Cuál marca tiene mayor tendencia?"

### Análisis
- "¿Top 10 artículos por tendencia en Carmel C-08?"
- "¿Qué talla se vende más en Loguin?"
- "¿Hay diferencias entre balanceo SAP y Manhattan?"

---

## Tecnología

| Componente | Herramienta |
|---|---|
| LLM (cerebro) | Ollama + qwen2.5:7b |
| Embeddings | Ollama + nomic-embed-text |
| Búsqueda semántica | ChromaDB |
| Datos analíticos | SQLite |
| Orquestación | LangChain |
| Interfaz | Chainlit |

**Todo corre localmente en tu PC. Sin internet. Sin costo mensual.**
