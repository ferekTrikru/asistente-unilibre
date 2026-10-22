# Asistente Unilibre — Agente inteligente de admisiones

Asistente de admisiones de la **Universidad Libre, seccional Barranquilla**. El asistente:

- **Responde preguntas** sobre carreras, valores de matrícula, jornadas, inscripciones,
  calendario, descuentos, becas y financiación, usando **solo** los documentos de la Universidad
  que están en `backend/data/`. Si un dato no está, lo dice y ofrece agendar una cita; no inventa.
  Entiende preguntas de seguimiento ("¿y de noche?") y sabe qué plazos ya pasaron.
- **Agenda citas reales** con un asesor: ofrece las franjas libres de la agenda
  (`backend/config/advisors.json`), evita choques y envía correo de confirmación.
- **Llamada de voz**: se le puede hablar al asistente y responde en voz alta (Chrome o Edge).
- **Mis citas**: el aspirante cancela o reprograma su cita sin crear cuenta.
- **Panel del asesor** (con clave): todas las citas con la conversación del chat, cambio de
  estado (asistió, admitido…) y la lista de **preguntas que el agente no supo responder**.

Todo corre **en tu computador**: la IA (Ollama), la búsqueda en los documentos y la página.

---

## Requisitos

| Programa | Versión | Para qué |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.11 (recomendado) | Backend |
| [Ollama](https://ollama.com/download) | cualquiera reciente | La IA que redacta las respuestas |
| [Git](https://git-scm.com/downloads) | cualquiera | Descargar el proyecto |
| Google Chrome o Microsoft Edge | reciente | Llamada de voz y dictado (Brave los bloquea) |

- **Espacio en disco:** unos 6 GB (el modelo `llama3.1:8b` pesa ~4,7 GB y el de búsqueda ~0,5 GB).
- **Memoria:** 16 GB de RAM recomendados. Con una tarjeta gráfica (NVIDIA, 6 GB o más) las
  respuestas tardan 6–13 s; solo con procesador, bastante más.
- Se necesita internet la primera vez (descarga de modelos) y para el reconocimiento de voz.

---

## Instalación (una sola vez)

Los comandos son para **Windows**. En Mac/Linux, cambia `venv\Scripts\python.exe` por
`venv/bin/python` y `copy` por `cp`.

### 1. Descargar el proyecto y el modelo de IA
```bash
git clone <URL-de-este-repositorio>
cd <nombre-de-la-carpeta>
ollama pull llama3.1:8b
```

### 2. Preparar el backend
```bash
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```
Abre `backend/.env` y completa al menos **`ADMIN_API_KEY`** (la clave del panel del asesor).
Genera una con:
```bash
venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(18))"
```
El correo y las llamadas de Vapi son opcionales: sin sus claves funcionan en **modo demo**
(ver [correo](#correo-de-confirmación)).

### 3. Cargar los documentos de la Universidad
Copia los PDF de la Universidad Libre en `backend/data/` (no vienen en el repositorio) y, dentro
de `backend`:
```bash
venv\Scripts\python.exe ingest.py --reset
```
Debe terminar con `N documento(s) -> M fragmento(s)` y `Listo.`

---

## Cómo encenderlo (cada vez que lo uses)

1. **Ollama**: abre la app (queda en la bandeja del sistema).
2. **Backend** — en una terminal, dentro de `backend`:
   ```bash
   venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Espera el mensaje `Precarga lista` (carga el modelo para que la primera pregunta sea rápida).
3. **Página** — en **otra** terminal, en la carpeta principal:
   ```bash
   python -m http.server 5000
   ```
   Abre **http://localhost:5000** (en Chrome o Edge si vas a usar la voz).

### Prueba rápida
1. Pregunta *"¿Cuánto cuesta la matrícula de Derecho?"* y luego *"¿Y tiene jornada nocturna?"*.
2. Escribe *"Quiero agendar una cita"* → **Admisiones → Virtual →** un horario → tu correo.
3. Abre **Mis citas** (menú) y reprograma la cita.
4. Abre **Panel del asesor** (menú), entra con tu `ADMIN_API_KEY` y marca la cita como **Admitido**.
5. Abre **Mi proceso**: debe estar en la etapa **Admisión**.
6. Toca el teléfono del encabezado para **llamar al asistente** por voz.

---

## Actualizar la información que responde

1. Cambia o agrega documentos en `backend/data/` (`.pdf`, `.docx`, `.md` o `.txt`). En los PDF,
   los títulos tipo *"13. Oferta de pregrado…"* y *"Derecho — Barranquilla"* se usan para que
   cada fragmento sepa a qué sección pertenece.
2. Si cambia la oferta de programas (valores, jornadas, fechas), actualiza también:
   - `backend/config/domain_knowledge.json` → `official_facts` (la ficha que el agente usa siempre)
   - `js/programas-unilibre.js` (lo que muestra la pantalla **Programas** y el chat)
3. **Detén el backend** (Ctrl + C): la base no se puede recargar mientras está abierto.
4. En `backend`: `venv\Scripts\python.exe ingest.py --reset`
5. Enciende el backend y corre el banco de pruebas (abajo).

> El **Panel del asesor → Sin respuesta** muestra lo que los aspirantes preguntaron y el agente no
> encontró: es la lista de lo que falta agregar a los documentos.

---

## Banco de pruebas

`backend/tests/preguntas_evaluacion.json` tiene 34 preguntas con lo que la respuesta debe (y no
debe) decir. Con el backend encendido, dentro de `backend`:
```bash
venv\Scripts\python.exe evaluate.py --solo-fallas
```
Córrelo después de cambiar documentos, el prompt o la búsqueda: si el puntaje baja, el cambio
rompió algo. Estado actual: **34/34**.

---

## Correo de confirmación

El correo se envía con Gmail (SMTP) o con [Resend](https://resend.com), según `backend/.env`:

| Configuración | Resultado |
|---|---|
| Sin claves | La cita se guarda y el chat dice *"Modo demo"*. No se envía correo. |
| `SMTP_USER` + `SMTP_APP_PASSWORD` (Gmail con *contraseña de aplicación*) | Llega a cualquier dirección. |
| `RESEND_API_KEY` (cuenta gratuita) | En modo de prueba, Resend **solo entrega al correo con que se creó la cuenta**; a cualquier otro lo rechaza y el chat avisa que no pudo enviarlo. |

Se envía correo al confirmar, reprogramar y cancelar una cita.

---

## Seguridad

- `backend/.env` (claves) y `backend/data/*.db` (datos de aspirantes) **nunca** se suben a Git ni a
  Firebase (`firebase.json` excluye todo `backend/`).
- El panel del asesor y sus rutas (`/admin/*`) exigen `ADMIN_API_KEY`.
- Las rutas públicas tienen un límite de peticiones por minuto (`RATE_LIMIT_PER_MINUTE`).
- Cancelar, reprogramar o pedir la llamada de una cita exige el código que recibe quien la agendó.
- El webhook de Vapi exige `VAPI_WEBHOOK_SECRET`.

---

## Publicar en internet (pendiente de decisión)

La página es estática y se publica con Firebase Hosting (`firebase deploy`). El backend necesita
un servidor con **Ollama y GPU**, o cambiar la IA a un modelo por API. Al desplegarlo:
1. Pon su URL pública en `js/config.js` (`PRODUCTION_BACKEND_URL`).
2. Agrega el dominio de la página a `CORS_ORIGINS` en `backend/.env`.

---

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| El chat siempre ofrece agendar cita y nunca responde con los documentos | El backend u Ollama están apagados. Revisa http://127.0.0.1:8000/health y que Ollama esté abierto. |
| `No se pudo conectar con Ollama` | Abre la app de Ollama (o `ollama serve`). |
| `El modelo 'llama3.1:8b' no está descargado` | `ollama pull llama3.1:8b` |
| `ingest.py` dice *"Storage folder ./qdrant_data is already accessed"* | Detén el backend antes de recargar los documentos. |
| En el log del backend: *"Ollama pudo recortar las instrucciones"* | El prompt no cabe: baja `MAX_CONTEXT_CHARS` en `backend/app/rag_engine.py`. |
| El panel del asesor dice *"Panel deshabilitado"* | Falta `ADMIN_API_KEY` en `backend/.env`; reinicia el backend. |
| La llamada de voz o el dictado no funcionan | Usa Chrome o Edge y permite el micrófono. Brave bloquea el reconocimiento de voz. |
| *"Demasiadas solicitudes seguidas"* | Límite por minuto; espera o sube `RATE_LIMIT_PER_MINUTE`. |
| Error de CORS en la consola | Abre la página en `http://localhost:5000`, no el archivo directamente. |

---

## Estructura del proyecto

```
index.html                    Chat, llamada de voz y agendamiento
screens/
  programas/                  Oferta de pregrado de la seccional
  citas/                      Mis citas (cancelar, reprogramar)
  proceso/                    Mi proceso (etapas del aspirante)
  asesor/                     Panel del asesor (con clave)
js/config.js                  Dirección del backend (local / publicado)
js/programas-unilibre.js      Datos de los 11 programas (pantalla Programas y chat)
styles/unilibre.css           Identidad visual de la Universidad Libre
backend/
  app/                        API (FastAPI): preguntas, agenda, citas, correo, llamadas, panel
  config/advisors.json        Asesores, tipos de atención y horario de la agenda
  config/domain_knowledge.json Ficha oficial de la oferta, glosario y aclaraciones fijas
  data/                       Documentos de la Universidad + base de citas (no se suben)
  tests/                      Banco de pruebas
  evaluate.py                 Corre el banco de pruebas
  ingest.py                   Carga los documentos en la base de búsqueda
```

Tecnologías: HTML/CSS/JS sin frameworks · FastAPI · SQLite · Qdrant (local) · LangChain ·
`paraphrase-multilingual-MiniLM-L12-v2` (búsqueda híbrida) · Llama 3.1 8B vía Ollama ·
Web Speech API (voz) · Resend o Gmail (correo) · Vapi (llamada telefónica, opcional).

Más detalles técnicos del backend en [`backend/README.md`](backend/README.md).
