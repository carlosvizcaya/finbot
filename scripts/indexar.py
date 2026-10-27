"""Construye app/indice.json: fragmenta las políticas y calcula sus embeddings (requiere OPENAI_API_KEY).

Uso: python scripts/indexar.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import rag  # noqa: E402

fragmentos = rag.cargar_fragmentos()
vectores = rag.embeber([f["texto"] for f in fragmentos])
for f, v in zip(fragmentos, vectores):
    f["vector"] = [round(x, 6) for x in v]
rag.INDICE.write_text(json.dumps({"modelo": rag.MODELO_EMBEDDINGS, "fragmentos": fragmentos}, ensure_ascii=False), encoding="utf-8")
vigentes = sum(f["estado"] == "vigente" for f in fragmentos)
print(f"{len(fragmentos)} fragmentos ({vigentes} vigentes) · {len(vectores[0])} dimensiones → {rag.INDICE}")
