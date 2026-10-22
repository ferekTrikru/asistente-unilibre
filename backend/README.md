# Backend RAG — Asistente Unilibre

API del asistente de admisiones de la Universidad Libre (seccional Barranquilla): responde
preguntas a partir de los documentos institucionales (PDF, Word, Markdown o texto) con
búsqueda híbrida en Qdrant y generación con un LLM local vía Ollama; además maneja la agenda
de asesores, el ciclo de vida de las citas y el panel del asesor.

## Rutas de la API

| Ruta | Acceso | Para qué |
|---|---|---|
| `GET /health` | público | Comprobar que el backend está encendido |
| `POST /ask`, `POST /ask/stream` | público, con límite por minuto | Responder una pregunta (`question` + `history` opcional). `/ask/stream` envía la respuesta a medida que se escribe (una línea JSON por evento) |
| `GET /availability?tipo=` | público | Próximas franjas libres de la agenda para ese tipo de atención |
| `POST /appointments` | público | Reservar una cita (valida que la franja siga libre; devuelve `id` y `token`) |
| `POST /appointments/{id}/status`, `/cancel`, `/reschedule`, `/call` | con el `token` de la cita | Consultar, cancelar, reprogramar o pedir la llamada de confirmación (una vez) |
| `GET /admin/appointments`, `PATCH /admin/appointments/{id}`, `GET /admin/unanswered` | encabezado `X-Admin-Key` | Panel del asesor: citas, cambio de estado, preguntas sin respuesta |
| `POST /webhooks/vapi` | encabezado `x-vapi-secret` | Resultado de las llamadas de Vapi |

## Cómo se arma cada respuesta

1. **Búsqueda híbrida** (`app/search.py`): 24 candidatos por parecido semántico, reordenados
   sumando coincidencia de palabras clave y un bono si aparecen en el título de la sección del
   fragmento. Cada fragmento lleva su ruta de títulos (`ingest.py`).
2. **Pregunta de seguimiento**: si la pregunta es corta, se busca junto con la anterior del
   aspirante (`history`).
3. **Contexto** (`app/rag_engine.py`): la ficha oficial de la oferta (`official_facts`) va
   siempre primero, luego aclaraciones fijas (`relations`) y los fragmentos (hasta
   `MAX_CONTEXT_CHARS`). Si el log avisa que Ollama recortó el prompt, bajar ese valor.
4. **Generación** (`app/llm.py`): Llama 3.1 8B, temperatura 0.1, ventana de 4096 tokens y tope
   de 220 tokens por respuesta. Las respuestas sin historial quedan en caché.
5. **Sin respuesta**: si el agente no encuentra el dato, la pregunta se registra para el panel.

## 0. Instalar Ollama

Descarga e instala Ollama desde https://ollama.com, y descarga un modelo:

```bash
ollama pull llama3.1:8b
```

Deja la app de Ollama abierta (o corre `ollama serve`) — expone su API en
`http://localhost:11434`, que es lo que usa este backend. Puedes usar cualquier otro
modelo que tengas descargado (`ollama list`) cambiando `OLLAMA_MODEL` en `.env`.

## 1. Instalar el backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
```

`OLLAMA_URL` y `OLLAMA_MODEL` en `.env` ya vienen con valores por defecto que funcionan
si Ollama corre localmente con `llama3.1:8b` descargado.

Sin `QDRANT_URL`, se usa una base Qdrant local embebida en `./qdrant_data` — sirve para
probar en tu máquina. Para producción, crea una instancia gratuita en
https://cloud.qdrant.io y pon su URL + API key en `.env`.

## 2. Cargar documentos

Copia tus PDFs institucionales (reglamentos, folletos de programas, etc.) a `backend/data/`
y corre:

```bash
python ingest.py
```

Usa `python ingest.py --reset` para reconstruir la colección desde cero.

## 3. Levantar la API

```bash
uvicorn app.main:app --reload --port 8000
```

Prueba con:

```bash
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"¿Cuándo abren inscripciones?\"}"
```

## 4. Conectar con el frontend

La dirección de esta API se configura en [`../js/config.js`](../js/config.js): en local usa
`http://127.0.0.1:8000`; al desplegar el backend, pon su URL pública en `PRODUCTION_BACKEND_URL`.

## 5. Desplegar (Cloud Run)

```bash
gcloud run deploy asistente-unilibre-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OLLAMA_URL=...,OLLAMA_MODEL=...,QDRANT_URL=...,QDRANT_API_KEY=...
```

Agrega el dominio de Firebase Hosting a `CORS_ORIGINS` antes de desplegar. Nota: Ollama
corriendo localmente no es accesible desde Cloud Run — para producción necesitas un
Ollama expuesto en una URL alcanzable (una VM propia, o un servicio como Ollama Cloud).

## 6. Confirmación de citas por correo

Cuando el chat agenda una cita (`../index.html`), hace `POST /appointments` a esta API,
que guarda la cita en SQLite (`data/appointments.db`) y envía un correo de confirmación
vía [Resend](https://resend.com).

Sin `RESEND_API_KEY` configurada en `.env`, el envío se **simula**: la API responde
igual y guarda la cita, pero en vez de enviar el correo deja un registro en la consola
del servidor (`[email simulado] ...`). Esto permite probar el flujo completo de
agendamiento sin crear ninguna cuenta.

Para enviar correos reales hay dos opciones — el sistema prueba SMTP primero, y si no
está configurado, cae a Resend:

**Opción A — con tu propia cuenta de Gmail (sin crear cuenta en nada más):**

1. Activa la verificación en dos pasos en https://myaccount.google.com/security
2. Genera una "contraseña de aplicación" en https://myaccount.google.com/apppasswords
   (elige "Correo" / "Otra (nombre personalizado)"). Google te da un código de 16
   caracteres — esa es la clave a usar, **no** tu contraseña normal de Gmail.
3. En `.env`, pon `SMTP_USER=tu-correo@gmail.com` y `SMTP_APP_PASSWORD=` (el código de
   16 caracteres, sin espacios).

**Opción B — con Resend:**

1. Crea una cuenta gratis en https://resend.com (3,000 correos/mes gratis).
2. Genera una API key y ponla en `.env` como `RESEND_API_KEY`.
3. Para pruebas puedes dejar `RESEND_FROM_EMAIL=onboarding@resend.dev` (no requiere
   verificar dominio). Para producción, verifica tu propio dominio en Resend y úsalo
   como remitente.

Prueba el endpoint directamente:

```bash
curl -X POST http://localhost:8000/appointments -H "Content-Type: application/json" -d "{\"tipo\":\"Admisiones\",\"modalidad\":\"Virtual\",\"slot_label\":\"lunes 22 de septiembre a las 10:00 a. m.\",\"slot_iso\":\"2026-09-22T10:00:00.000Z\",\"asesor\":\"Laura Méndez\",\"email\":\"tu-correo@ejemplo.com\"}"
```

## 7. Llamada de confirmación con un agente de voz (Vapi)

Después de agendar, si el aspirante dejó un teléfono, el chat le ofrece una llamada de
confirmación. Al aceptar, hace `POST /appointments/{id}/call`, que dispara una llamada
saliente vía [Vapi](https://vapi.ai) — una plataforma de agentes de voz con IA (LLM + voz
+ telefonía en uno, sin construir tu propio pipeline de STT/TTS).

Sin `VAPI_API_KEY`/`VAPI_ASSISTANT_ID`/`VAPI_PHONE_NUMBER_ID` en `.env`, la llamada se
**simula** igual que el correo: la API responde igual y guarda el estado, pero registra
`[llamada simulada] ...` en la consola del servidor en vez de llamar de verdad.

Para llamadas reales:

1. Crea una cuenta gratis en https://vapi.ai (trae créditos de prueba — no alcanza para
   uso productivo continuo, solo para probar el flujo).
2. Crea un **Assistant** en el dashboard: modelo (LLM), voz, y sobre todo su prompt —
   debe seguir las mismas reglas que el chat: puede confirmar, reprogramar o cancelar la
   cita, y responder preguntas básicas ya cubiertas por la base de conocimiento
   (`config/domain_knowledge.json` / `KB_PROGRAMS` en `../index.html`); si no sabe algo,
   debe decirlo y ofrecer transferir a un asesor humano — nunca inventar información.
   Copia su `Assistant ID`.
3. Compra o importa un número en **Phone Numbers**. Copia su `Phone Number ID`.
4. En la configuración del asistente, define su **Server URL** (webhook) apuntando a
   `<URL_PÚBLICA_DE_ESTE_BACKEND>/webhooks/vapi` — así el backend recibe la transcripción
   y el resumen cuando termina la llamada (`POST /webhooks/vapi`, ver `app/main.py`). En
   local, expón el puerto con algo como `ngrok http 8000` para que Vapi pueda alcanzarlo.
5. Pon las tres variables en `.env`.

6. En el dashboard de Vapi define un **Server URL Secret** y ponlo en `.env` como
   `VAPI_WEBHOOK_SECRET`: sin él, el webhook rechaza todas las peticiones.

El resultado de la llamada (estado, transcripción, resumen) queda en la tabla
`appointments` de `data/appointments.db` y el resumen se muestra en el panel del asesor
(`screens/asesor/`).

**Nota:** la forma exacta del payload que envía Vapi al webhook puede cambiar entre
versiones de su API — revisa su documentación actual antes de depender de campos
específicos; el handler en `app/main.py` está escrito de forma defensiva para no romperse
si algún campo falta.

## Personalizar el conocimiento de dominio

`config/domain_knowledge.json` tiene cuatro secciones:
- `official_facts`: ficha compacta y oficial de la oferta de pregrado y el calendario. Va en
  **todas** las respuestas; evita que el modelo mezcle datos entre programas. Si cambia la
  oferta, actualizarla aquí y en `../js/programas-unilibre.js`.
- `general_context`: párrafo que se agrega cuando hay pocos resultados de búsqueda.
- `glossary`: siglas institucionales a expandir automáticamente (ej. `"SNIES": "Sistema..."`).
- `relations`: aclaraciones que se inyectan cuando la pregunta menciona un término
  (ej. `"descuento"` → los descuentos no son acumulables).

`config/advisors.json` define los asesores, qué tipos de atención cubre cada uno y el horario
de la agenda (días hábiles, franjas, anticipación mínima).

## Banco de pruebas

`python evaluate.py` (con el backend encendido) corre las preguntas de
`tests/preguntas_evaluacion.json` y muestra el puntaje. Agrega un caso cada vez que el agente
responda mal algo importante, para que no vuelva a pasar.

## Contexto del proyecto (conceptualización y valor)

### Conceptualización problémica y/o oportunidad

**Identificación de necesidades:** un aspirante que se acerca por primera vez a
la Universidad Libre trae preguntas heterogéneas — qué programas existen, en qué sede se
dictan, cuánto cuestan, qué requisitos piden, cómo es la inscripción, si hay financiación,
o directamente "no sé qué estudiar". Hoy esto se resuelve por dos vías insuficientes: un
canal humano (línea de admisiones, WhatsApp) que no está disponible 24/7, o información
estática en la web institucional que no se adapta a la situación particular del aspirante
ni sabe reaccionar cuando este quiere dar el siguiente paso (agendar cita, hablar con
alguien). El síntoma concreto: preguntas simples consumen tiempo de un asesor humano, y
las preguntas que sí ameritan una persona no llegan con contexto — el asesor empieza cada
conversación desde cero.

**Análisis de viabilidad:** el proyecto es viable técnicamente porque no depende de
infraestructura costosa — el backend RAG (FastAPI + Qdrant + LLM) corre completamente en
local con Ollama, sin costo de API por consulta ni dependencia de conectividad externa una
vez desplegado. La base de conocimiento se nutre de documentos institucionales ya
existentes (PDFs de reglamentos y guías), evitando construir una base de datos desde cero.
Es viable operativamente porque no reemplaza al asesor humano, sino que filtra y prepara
el contexto que este recibe, reduciendo carga sin eliminar el criterio humano en
decisiones sensibles (matrícula, casos particulares).

**Definición de alcance:** el alcance actual (MVP) cubre conversación con motor de
intención, orientación vocacional básica, agendamiento autónomo de citas, transferencia de
contexto a un asesor, y consulta de documentos institucionales vía RAG cuando el motor de
reglas no reconoce la intención. Queda fuera de alcance (V2/V3): reprogramación real de
citas contra un sistema institucional, integración con preinscripción y matrícula oficial,
analítica predictiva de conversión, y recomendación de programas basada en historial.

### Valor obtenido

Un agente conversacional que no solo genera texto, sino que **ejecuta acciones**:
identifica la intención real del aspirante, responde con información confiable extraída
de documentos oficiales (nunca inventada), agenda una cita con el tipo de asesor adecuado,
y transfiere el contexto completo de la conversación para que el aspirante no tenga que
repetir nada. El valor no es "un chatbot más rápido" sino la reducción de fricción en todo
el recorrido del aspirante, desde la primera pregunta hasta la cita confirmada.

### Gestión de valor

La arquitectura combina dos capas complementarias: un **motor de reglas en JavaScript**
(`handleUserMessage`, en `../index.html`) que detecta programa, sede, tema (financiación,
requisitos, calendario, modalidad) y la necesidad de escalar a un humano, resolviendo la
mayoría de las preguntas frecuentes de forma instantánea y sin costo de inferencia; y este
**backend RAG**, que entra en juego solo cuando el motor de reglas no reconoce la
intención, buscando semánticamente en los documentos institucionales indexados en Qdrant y
generando la respuesta con un LLM local vía Ollama. Si el backend no está disponible o no
encuentra información suficiente, el sistema cae de vuelta al flujo de agendar cita —
nunca deja al aspirante sin respuesta ni inventa datos que no puede sustentar.

### Caracterización del usuario/cliente

El usuario es el aspirante a un programa de la Universidad Libre, en una de cuatro etapas
del embudo de admisión: **exploración** (quiere saber qué programas, sedes y costos
existen, sin intención de decisión inmediata), **decisión** (ya tiene un programa en mente
y necesita requisitos, modalidad o financiación concretos), **indeciso** (no sabe qué
estudiar y necesita orientación vocacional guiada por área de interés), y **listo para
actuar** (quiere agendar una cita, virtual o presencial, con un asesor). El perfil típico
consulta desde el celular (de ahí el diseño PWA instalable del frontend), espera respuesta
inmediata y no siempre formula la pregunta de forma clara, lo que exige que el sistema
infiera intención en vez de depender de comandos exactos.

### Fundamentación teórica

El sistema se apoya en **Retrieval-Augmented Generation (RAG)**: en vez de que el modelo
de lenguaje responda solo desde su conocimiento paramétrico (con riesgo de alucinación),
se recupera primero el contexto relevante de una base vectorial y se condiciona la
generación a ese contexto. La recuperación usa **embeddings locales**
(`sentence-transformers/all-MiniLM-L6-v2`, 384 dimensiones) para representar
semánticamente cada fragmento de documento, indexados en **Qdrant** como base de datos
vectorial con similitud coseno. Los documentos se dividen en fragmentos de 2000 caracteres
con solape de 300 (`RecursiveCharacterTextSplitter`) para preservar contexto entre
fragmentos contiguos. La generación de la respuesta final corre en un **LLM local vía
Ollama** (por defecto `llama3.1:8b`), eliminando la dependencia de una API externa de pago
y manteniendo los datos institucionales dentro de la infraestructura propia. Sobre esta
base técnica se apoya el motor de reglas de detección de intención como capa previa,
siguiendo el principio de usar el enfoque más simple y confiable disponible antes de
recurrir a generación libre.

### Gestión del impacto

El impacto esperado se mide en cuatro dimensiones: **disponibilidad** (respuesta 24/7 a
preguntas frecuentes, sin tiempos de espera); **carga operativa** (menos consultas
repetitivas llegan a los asesores humanos, que pueden enfocarse en casos que sí requieren
criterio humano); **conversión** (el seguimiento explícito del embudo Exploración →
Interés → Orientación → Cita → Admisión, visible en `screens/proceso/`, permite
identificar en qué etapa se pierden aspirantes); y **calidad de la transferencia** (el
asesor humano recibe un resumen de contexto — programa, sede, necesidad, etapa, cita — en
`screens/asesor/`, en vez de partir de cero, lo que reduce el tiempo de la primera
interacción humana y mejora la experiencia del aspirante).
