"""Evalúa el RAG de posventa con preguntas de respuesta conocida (eval/preguntas_rag.json).

Mide la recuperación (recall@1 y recall@4 por política), el tamaño real del contexto en tokens
y, de punta a punta, si la respuesta cita la política correcta o se abstiene cuando no hay respaldo.
Requiere OPENAI_API_KEY. Uso: python scripts/evaluar_rag.py
"""

import json
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import bot, rag  # noqa: E402

casos = json.loads((RAIZ / "eval" / "preguntas_rag.json").read_text(encoding="utf-8"))
vectores = rag.embeber([c["pregunta"] for c in casos])
cliente = rag._cliente()

r1 = r4 = n = 0
tokens_in, tokens_out, aciertos, abstenciones, vencidas = [], [], 0, 0, 0
for caso, vector in zip(casos, vectores):
    recuperados = rag.buscar(vector, rag.indice())
    docs = [f["doc"] for f in recuperados]
    vencidas += sum(f["estado"] != "vigente" for f in recuperados)
    if caso["doc"]:
        n += 1
        r1 += docs[0] == caso["doc"]
        r4 += caso["doc"] in docs
    r = cliente.chat.completions.create(
        model=bot.modelo_llm(),
        messages=[{"role": "system", "content": rag.SISTEMA},
                  {"role": "user", "content": f"Fragmentos:\n{rag.contexto(recuperados)}\n\nPregunta del agente: {caso['pregunta']}"}],
    )
    texto = r.choices[0].message.content or ""
    tokens_in.append(r.usage.prompt_tokens)
    tokens_out.append(r.usage.completion_tokens)
    citas = rag.respaldo(texto, recuperados)
    citados = {c.split("/")[0] for c in citas}
    if caso["doc"]:
        aciertos += caso["doc"] in citados
    else:
        abstenciones += not citas
    estado = "ok" if (caso["doc"] in citados if caso["doc"] else not citas) else "FALLA"
    print(f"{estado:5} · {caso['pregunta'][:60]:60} · recuperó {docs[0]:22} · citó {sorted(citados) or '—'}")

fuera = len(casos) - n
print()
print(f"recall@1 {r1}/{n} = {r1/n:.0%} · recall@4 {r4}/{n} = {r4/n:.0%} · fragmentos vencidos recuperados: {vencidas}")
print(f"respuestas que citan la política correcta: {aciertos}/{n} = {aciertos/n:.0%} · abstención fuera de alcance: {abstenciones}/{fuera}")
print(f"tokens de entrada por consulta: media {statistics.mean(tokens_in):.0f} (mín {min(tokens_in)}, máx {max(tokens_in)}) · salida media {statistics.mean(tokens_out):.0f}")
