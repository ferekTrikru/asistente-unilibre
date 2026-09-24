import httpx
import ollama

from . import config

_client = None


def get_client() -> ollama.Client:
    global _client
    if _client is None:
        _client = ollama.Client(host=config.OLLAMA_URL)
    return _client


def generate(prompt: str) -> str:
    client = get_client()
    try:
        response = client.generate(model=config.OLLAMA_MODEL, prompt=prompt)
    except (httpx.ConnectError, ConnectionError) as exc:
        raise RuntimeError(
            f"No se pudo conectar con Ollama en {config.OLLAMA_URL}. "
            "Abre la app de Ollama (o corre 'ollama serve') e inténtalo de nuevo."
        ) from exc
    except ollama.ResponseError as exc:
        if exc.status_code == 404:
            raise RuntimeError(
                f"El modelo '{config.OLLAMA_MODEL}' no está descargado. "
                f"Corre: ollama pull {config.OLLAMA_MODEL}"
            ) from exc
        raise RuntimeError(f"Error de Ollama: {exc.error}") from exc

    return (response.response or "").strip()
