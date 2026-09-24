# Asistente Combarranquilla — Agente inteligente de admisiones

Chat con IA para **Combarranquilla** (Caja de Compensación Familiar). El asistente:

- **Responde preguntas** sobre afiliación, categorías, subsidios, programas de formación, crédito,
  recreación y trámites, usando **solo** la guía oficial
  [`backend/data/Guia_Combarranquilla_RAG.docx`](backend/data/Guia_Combarranquilla_RAG.docx).
  Si un dato no está en la guía, lo dice y ofrece agendar una cita; no inventa.
- **Agenda citas** con un asesor (tipo de atención → virtual o presencial → horario → correo).
- **Envía un correo de confirmación** de la cita.
- **Arma un resumen para el asesor** con el contexto de la conversación ("Vista del asesor").

Todo corre **en tu computador**: la IA (Ollama), la búsqueda en la guía y la página.

---

## ⚠️ Importante: a quién le llega el correo de confirmación

El envío de correos usa una cuenta de **[Resend](https://resend.com)** en **modo de prueba**.
En ese modo Resend **solo entrega correos a la dirección con la que se creó la cuenta**.

| Cómo configures `backend/.env` | Qué pasa al agendar una cita |
|---|---|
| **Sin clave de correo** (`RESEND_API_KEY` vacío) | La cita se guarda y el chat dice *"Modo demo"*. **No se envía ningún correo.** Todo lo demás funciona. |
| **Con la clave de Resend del proyecto** (pídela por privado a quien administra el proyecto) | El correo se envía, pero **solo llega a `ferekromero9a@gmail.com`**, el correo con el que se creó la cuenta de Resend. Si escribes otro correo en el chat, Resend lo rechaza y el chat dice que no pudo enviarlo. |
| **Con tu propia cuenta de Resend** (gratis, ver abajo) | El correo llega **a tu propio correo** (el que usaste para crear la cuenta de Resend). |

> Para ver el flujo con correo usando la clave del proyecto, escribe
> **`ferekromero9a@gmail.com`** cuando el chat te pida el correo.

La clave **no está en este repositorio** a propósito: el archivo `backend/.env` está excluido
de Git para que nadie pueda usar la cuenta de correo sin permiso.

### Usar tu propia cuenta de Resend (para que el correo te llegue a ti)
1. Crea una cuenta gratis en https://resend.com con tu correo.
2. En el panel, ve a **API Keys → Create API Key** y copia la clave (empieza por `re_`).
3. Pégala en `backend/.env`: `RESEND_API_KEY=re_...`
4. Reinicia el backend. Al agendar una cita, escribe **el correo con el que creaste la cuenta**.

(Otra opción es usar tu Gmail con una "contraseña de aplicación": llena `SMTP_USER` y
`SMTP_APP_PASSWORD` en `backend/.env`. Así el correo puede llegar a cualquier dirección.)

---

## Requisitos

| Programa | Versión | Para qué |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.11 (recomendado) | Backend |
| [Ollama](https://ollama.com/download) | cualquiera reciente | La IA que redacta las respuestas |
| [Git](https://git-scm.com/downloads) | cualquiera | Descargar el proyecto |

- **Espacio en disco:** unos 6 GB (el modelo `llama3.1:8b` pesa ~4,7 GB y el modelo de búsqueda ~0,5 GB).
- **Memoria:** 8 GB de RAM como mínimo; con 16 GB va más fluido.
- Se necesita internet solo la primera vez, para descargar los modelos.

---

## Instalación (una sola vez)

Los comandos son para **Windows** (PowerShell o CMD). En Mac/Linux, cambia
`venv\Scripts\python.exe` por `venv/bin/python` y `copy` por `cp`.

### 1. Descargar el proyecto
```bash
git clone <URL-de-este-repositorio>
cd <nombre-de-la-carpeta>
```

### 2. Descargar el modelo de IA
Abre la app de **Ollama** y luego:
```bash
ollama pull llama3.1:8b
```

### 3. Preparar el backend
```bash
cd backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```
Si quieres correos, edita `backend/.env` según la sección
[a quién le llega el correo](#️-importante-a-quién-le-llega-el-correo-de-confirmación).
Si no, déjalo así y funcionará en modo demo.

### 4. Cargar la guía de Combarranquilla en la base de búsqueda
Todavía dentro de `backend`:
```bash
venv\Scripts\python.exe ingest.py --reset
```
Debe terminar con `1 documento(s) -> 73 fragmento(s)` y `Listo.`
(La primera vez descarga el modelo de búsqueda; tarda unos minutos.)

---

## Cómo encenderlo (cada vez que lo uses)

Necesitas **3 cosas abiertas**:

1. **Ollama**: abre la app (queda en la bandeja del sistema).
2. **Backend**: en una terminal, dentro de `backend`:
   ```bash
   venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
   ```
   Déjala abierta. Comprueba en el navegador: http://localhost:8000/health → `{"status":"ok"}`
3. **Página**: en **otra** terminal, en la carpeta principal del proyecto:
   ```bash
   python -m http.server 5000
   ```
   Abre **http://localhost:5000**

> Usa el puerto **5000**: el backend solo acepta peticiones de `localhost:5000` y `localhost:8080`
> (configurable en `CORS_ORIGINS` dentro de `backend/.env`).

### Prueba rápida
1. Pregunta: *"¿Qué requisitos pide el subsidio de vivienda?"*. Responde con los requisitos
   de la guía y muestra la fuente abajo.
2. Escribe: *"Quiero hablar con un asesor sobre el subsidio de vivienda"*.
3. Elige **Afiliación y subsidios → Virtual →** un horario.
4. Escribe el correo (ver la [tabla de correo](#️-importante-a-quién-le-llega-el-correo-de-confirmación)).
5. Revisa **Mis citas** y **Vista del asesor** en el menú.

La primera respuesta puede tardar 20–30 s mientras Ollama carga el modelo; las siguientes, unos 5–15 s.

---

## Actualizar la información que responde

1. Edita la guía de Word [`backend/data/Guia_Combarranquilla_RAG.docx`](backend/data/Guia_Combarranquilla_RAG.docx)
   (o agrega más `.docx`, `.pdf`, `.md` o `.txt` en `backend/data/`).
   Usa los estilos **Título 1, 2 y 3**: el asistente divide la guía por títulos.
2. **Detén el backend** (Ctrl + C). La base no se puede recargar mientras está abierto.
3. En `backend`: `venv\Scripts\python.exe ingest.py --reset`
4. Vuelve a encender el backend.

> El catálogo de la pantalla **Programas de formación** está escrito en el código
> (`index.html` y `screens/programas/index.html`, variable `KB_PROGRAMS`). Si cambian los
> programas, sedes o precios en la guía, hay que actualizarlo también ahí.

---

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| El chat siempre ofrece agendar cita y nunca responde con la guía | El backend o Ollama están apagados. Revisa http://localhost:8000/health y que Ollama esté abierto. |
| `No se pudo conectar con Ollama` en la terminal del backend | Abre la app de Ollama (o ejecuta `ollama serve`). |
| `El modelo 'llama3.1:8b' no está descargado` | `ollama pull llama3.1:8b` |
| "Todavía no hay documentos cargados" | Ejecuta el paso 4 (`ingest.py --reset`). |
| "No pude enviarte el correo de confirmación" | Estás usando la clave de Resend del proyecto con un correo distinto a `ferekromero9a@gmail.com`. Revisa la [tabla de correo](#️-importante-a-quién-le-llega-el-correo-de-confirmación). |
| El chat no conecta con el backend (error de CORS en la consola) | Abre la página en `http://localhost:5000`, no abriendo el archivo `index.html` directamente. |
| `ingest.py` falla con un error de conexión a Hugging Face | Vuelve a intentarlo con internet estable; si el modelo ya se descargó antes, puedes forzar modo sin conexión: `set HF_HUB_OFFLINE=1` (Windows) antes del comando. |

---

## Estructura del proyecto

```
index.html                  Chat principal
screens/
  programas/                Catálogo de programas de formación
  citas/                    Mis citas
  proceso/                  Mi proceso (etapas del aspirante)
  asesor/                   Vista del asesor (resumen de la conversación)
icons/                      Logo e íconos de Combarranquilla
backend/
  app/                      API (FastAPI): preguntas, citas, correo, llamadas
  data/                     Guía de Combarranquilla (fuente de las respuestas)
  config/domain_knowledge.json   Glosario (SMMLV, PQRS…) y contexto general
  ingest.py                 Carga los documentos en la base de búsqueda
  .env.example              Plantilla de configuración (copiar a .env)
```

Tecnologías: HTML/CSS/JS sin frameworks · FastAPI · Qdrant (local) · LangChain ·
`paraphrase-multilingual-MiniLM-L12-v2` para la búsqueda · Llama 3.1 8B vía Ollama ·
Resend o Gmail (SMTP) para correos.

Más detalles técnicos del backend en [`backend/README.md`](backend/README.md).
