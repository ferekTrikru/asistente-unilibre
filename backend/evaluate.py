"""
Banco de pruebas del asistente: corre las preguntas de tests/preguntas_evaluacion.json
contra el backend encendido y dice cuántas responde bien.

Uso (con el backend corriendo en otra terminal):
    python evaluate.py                 # todas las preguntas
    python evaluate.py --solo-fallas   # muestra solo las que fallan

Correrlo después de cambiar el documento, el prompt o la búsqueda: si el puntaje baja,
el cambio rompió algo que antes funcionaba.
"""
import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.request

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
CASES_PATH = os.path.join(os.path.dirname(__file__), "tests", "preguntas_evaluacion.json")
NOT_FOUND = "no encuentro esa informacion"


def norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def ask(question: str, history: list) -> dict:
    req = urllib.request.Request(
        f"{BACKEND}/ask",
        data=json.dumps({"question": question, "history": history}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def evaluate(case: dict, result: dict) -> list[str]:
    answer = norm(result.get("answer", ""))
    problems = []
    if case.get("sin_respuesta"):
        # Vale decir que no está en los documentos o negar directamente ("no tenemos...").
        if NOT_FOUND not in answer and not answer.lstrip().startswith(("no ", "lo siento")):
            problems.append("debía decir que no está en los documentos")
        return problems
    if NOT_FOUND in answer and case.get("debe"):
        problems.append("dijo que no encuentra la información")
    for expected in case.get("debe", []):
        if not any(norm(option) in answer for option in expected.split("|")):
            problems.append(f"falta «{expected}»")
    for forbidden in case.get("no_debe", []):
        if norm(forbidden) in answer:
            problems.append(f"no debía decir «{forbidden}»")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solo-fallas", action="store_true")
    args = parser.parse_args()

    with open(CASES_PATH, encoding="utf-8") as f:
        cases = json.load(f)["casos"]

    passed, started = 0, time.time()
    for i, case in enumerate(cases, 1):
        try:
            result = ask(case["pregunta"], case.get("historial", []))
        except Exception as exc:
            print(f"[{i:02d}] ERROR  {case['pregunta']}\n       no se pudo consultar el backend: {exc}")
            continue
        problems = evaluate(case, result)
        ok = not problems
        passed += ok
        if ok and args.solo_fallas:
            continue
        print(f"[{i:02d}] {'OK   ' if ok else 'FALLA'} {case['pregunta']}")
        if not ok:
            print(f"       {'; '.join(problems)}")
            print(f"       respuesta: {result.get('answer', '')[:300]}")

    total = len(cases)
    print(f"\nResultado: {passed}/{total} correctas ({passed / total:.0%}) en {time.time() - started:.0f} s")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
