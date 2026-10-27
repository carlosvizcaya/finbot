"""RAG mínimo sobre las políticas de posventa (ficticias) de la tienda del caso.

Ingesta fuera de línea (scripts/indexar.py): cada política en app/politicas/ se divide por sección
y se guarda con su versión, fecha y estado en app/indice.json, junto al embedding de cada fragmento.
Consulta: embedding de la pregunta → los 4 fragmentos vigentes más parecidos → el LLM redacta solo
con esos fragmentos, citándolos, y se abstiene si no encuentra respaldo.
"""

import json
import math
import os
import re
from pathlib import Path

DIR = Path(__file__).parent
POLITICAS = DIR / "politicas"
INDICE = DIR / "indice.json"
MODELO_EMBEDDINGS = "text-embedding-3-small"
TOP_K = 4

SISTEMA = (
    "Eres un asistente interno de posventa para agentes de una tienda de retail en Chile. "
    "Responde en español, en un máximo de cinco frases, usando SOLO los fragmentos de política "
    "entregados. Cita cada afirmación con el id del fragmento entre corchetes, por ejemplo "
    "[garantia-legal/plazo]. Si los fragmentos no responden la pregunta, responde exactamente "
    "SIN_RESPALDO y nada más; no inventes plazos ni condiciones."
)

SIN_RESPALDO = "No encontré una política que responda esto. Escala el caso a un supervisor."


def _slug(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def leer_politica(ruta: Path) -> dict:
    """Separa el encabezado (titulo, version, vigente_desde, estado) del cuerpo."""
    texto = ruta.read_text(encoding="utf-8")
    _, cabecera, cuerpo = texto.split("---", 2)
    meta = dict(linea.split(": ", 1) for linea in cabecera.strip().splitlines())
    meta["doc"] = re.sub(r"-v\d+$", "", ruta.stem)
    meta["version"] = int(meta["version"])
    meta["cuerpo"] = re.sub(r"<!--.*?-->", "", cuerpo, flags=re.S).strip()
    return meta


def fragmentar(politica: dict) -> list[dict]:
    """Un fragmento por sección «## …», con el título de la política como contexto."""
    fragmentos = []
    for bloque in re.split(r"^## ", politica["cuerpo"], flags=re.M):
        if not bloque.strip():
            continue
        seccion, _, texto = bloque.partition("\n")
        fragmentos.append({
            "id": f"{politica['doc']}/{_slug(seccion)}",
            "doc": politica["doc"],
            "titulo": politica["titulo"],
            "version": politica["version"],
            "vigente_desde": politica["vigente_desde"],
            "estado": politica["estado"],
            "texto": f"{politica['titulo']} · {seccion.strip()}: {' '.join(texto.split())}",
        })
    return fragmentos


def cargar_fragmentos() -> list[dict]:
    return [f for ruta in sorted(POLITICAS.glob("*.md")) for f in fragmentar(leer_politica(ruta))]


def coseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    return num / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)


def buscar(vector: list[float], indice: list[dict], k: int = TOP_K) -> list[dict]:
    """Top-k por similitud, solo entre fragmentos de políticas vigentes."""
    vigentes = [f for f in indice if f["estado"] == "vigente"]
    return sorted(vigentes, key=lambda f: coseno(vector, f["vector"]), reverse=True)[:k]


def contexto(fragmentos: list[dict]) -> str:
    return "\n".join(f"[{f['id']}] (v{f['version']}, desde {f['vigente_desde']}) {f['texto']}" for f in fragmentos)


def citas_validas(respuesta: str, fragmentos: list[dict]) -> list[str]:
    """Ids citados en la respuesta que sí estaban entre los fragmentos recuperados."""
    ids = {f["id"] for f in fragmentos}
    return [c for c in dict.fromkeys(re.findall(r"\[([a-z0-9\-]+/[a-z0-9\-]+)\]", respuesta)) if c in ids]


def respaldo(respuesta: str, fragmentos: list[dict]) -> list[str]:
    """Verificador mínimo: citas válidas, o ninguna si el modelo declaró que no hay respaldo."""
    if "SIN_RESPALDO" in respuesta:
        return []
    return citas_validas(respuesta, fragmentos)


_indice: list[dict] | None = None


def indice() -> list[dict]:
    global _indice
    if _indice is None:
        _indice = json.loads(INDICE.read_text(encoding="utf-8"))["fragmentos"] if INDICE.exists() else []
    return _indice


def _cliente():
    from openai import OpenAI

    return OpenAI(timeout=20)


def embeber(textos: list[str]) -> list[list[float]]:
    r = _cliente().embeddings.create(model=MODELO_EMBEDDINGS, input=textos)
    return [d.embedding for d in r.data]


def redactar(pregunta: str, fragmentos: list[dict], modelo: str) -> str:
    r = _cliente().chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": f"Fragmentos:\n{contexto(fragmentos)}\n\nPregunta del agente: {pregunta}"},
        ],
    )
    return (r.choices[0].message.content or "").strip()


def responder(pregunta: str, modelo: str, embed=embeber, llm=redactar) -> dict:
    """Recupera, redacta y verifica que la respuesta cite fragmentos recuperados."""
    recuperados = buscar(embed([pregunta])[0], indice())
    if not recuperados:
        return {"respuesta": SIN_RESPALDO, "fuente": "ayuda", "citas": [], "recuperados": []}
    texto = llm(pregunta, recuperados, modelo)
    citas = respaldo(texto, recuperados)
    if not citas:
        # Sin citas válidas no hay respaldo verificable: se abstiene en vez de responder.
        return {"respuesta": SIN_RESPALDO, "fuente": "ayuda", "citas": [], "recuperados": [f["id"] for f in recuperados]}
    return {"respuesta": texto, "fuente": "rag", "citas": citas, "recuperados": [f["id"] for f in recuperados]}


def disponible() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and bool(indice())
