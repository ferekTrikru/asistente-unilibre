import httpx
import ollama

from . import config

_client = None

# Temperatura baja: respuestas factuales y estables entre ejecuciones.
# num_ctx 4096: el prompt (instrucciones + fragmentos) ronda los 3.000 tokens; una ventana
# mayor no cabe en la GPU de 6 GB y pasa parte del modelo a la CPU, que es mucho más lenta.
# num_predict: tope de longitud. Las respuestas buenas usan 40-150 tokens; sin tope, el
# modelo puede entrar en bucle y escribir miles de tokens (visto en pruebas).
_OPTIONS = {"temperature": 0.1, "num_ctx": 4096, "num_predict": 220}
# Mantiene el modelo cargado en memoria entre preguntas (cargarlo tarda 20-30 s).
_KEEP_ALIVE = "60m"


def get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=config.OLLAMA_URL)
    return _client


def _friendly_error(exc: Exception) -> RuntimeError:
    if isinstance(exc, ollama.ResponseError):
        if exc.status_code == 404:
            return RuntimeError(
                f"El modelo '{config.OLLAMA_MODEL}' no está descargado. "
                f"Corre: ollama pull {config.OLLAMA_MODEL}"
            )
        return RuntimeError(f"Error de Ollama: {exc.error}")
    return RuntimeError(
        f"No se pudo conectar con Ollama en {config.OLLAMA_URL}. "
        "Abre la app de Ollama (o corre 'ollama serve') e inténtalo de nuevo."
    )


def generate(prompt: str) -> str:
    try:
        response = get_client().generate(
            model=config.OLLAMA_MODEL, prompt=prompt, options=_OPTIONS, keep_alive=_KEEP_ALIVE
        )
    except (httpx.ConnectError, ConnectionError, ollama.ResponseError) as exc:
        raise _friendly_error(exc) from exc
    return (response.response or "").strip()


def generate_stream(prompt: str):
    """Igual que generate(), pero entrega el texto a medida que el modelo lo escribe."""
    try:
        for part in get_client().generate(
            model=config.OLLAMA_MODEL, prompt=prompt, options=_OPTIONS,
            keep_alive=_KEEP_ALIVE, stream=True,
        ):
            if part.response:
                yield part.response
    except (httpx.ConnectError, ConnectionError, ollama.ResponseError) as exc:
        raise _friendly_error(exc) from exc


def warm_up() -> None:
    """Carga el modelo en memoria para que la primera pregunta no espere la carga."""
    get_client().generate(
        model=config.OLLAMA_MODEL, prompt="ok", options={**_OPTIONS, "num_predict": 1},
        keep_alive=_KEEP_ALIVE,
    )
