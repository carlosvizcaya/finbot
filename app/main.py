"""API de Finbot: GET /health, POST /chat y un chat HTML mínimo en GET /."""

from typing import Annotated, Literal

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, StringConstraints

from app import bot

app = FastAPI(title="Finbot", description="Asistente de educación financiera para Chile")


class Pregunta(BaseModel):
    mensaje: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class Respuesta(BaseModel):
    respuesta: str
    fuente: Literal["reglas", "glosario", "llm", "ayuda"]


@app.get("/health")
def health() -> dict:
    return {"ok": True, "modelo": bot.modelo_llm(), "llm": bot.llm_disponible()}


@app.post("/chat", response_model=Respuesta)
def chat(pregunta: Pregunta) -> dict:
    return bot.responder(pregunta.mensaje)


PAGINA = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Finbot</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { color: #0a7ea4; margin-bottom: .25rem; }
  p.ayuda { color: #555; margin-top: 0; }
  #chat { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; min-height: 240px; }
  .msg { padding: .5rem .75rem; border-radius: 8px; margin: .5rem 0; max-width: 85%; }
  .yo { background: #eef2f5; margin-left: auto; text-align: right; }
  .bot { background: #f5f5f5; }
  .fuente { font-size: .75rem; color: #888; margin: -.25rem 0 .5rem; }
  form { display: flex; gap: .5rem; margin-top: 1rem; }
  input { flex: 1; padding: .6rem; border: 1px solid #ccc; border-radius: 6px; }
  button { padding: .6rem 1rem; border: 0; border-radius: 6px; background: #0a7ea4; color: #fff; cursor: pointer; }
</style>
</head>
<body>
<h1>Finbot</h1>
<p class="ayuda">Prueba: “crédito de 10 millones a 36 meses al 12 %”, “juntar 2 millones en 10 meses”, “¿qué es la CAE?”</p>
<div id="chat"></div>
<form id="f">
  <input id="m" autocomplete="off" placeholder="Escribe tu pregunta" maxlength="500" required>
  <button>Enviar</button>
</form>
<script>
const chat = document.getElementById("chat");
function agregar(texto, clase, fuente) {
  const d = document.createElement("div");
  d.className = "msg " + clase;
  d.textContent = texto;
  chat.appendChild(d);
  if (fuente) {
    const f = document.createElement("div");
    f.className = "fuente";
    f.textContent = "fuente: " + fuente;
    chat.appendChild(f);
  }
}
document.getElementById("f").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("m");
  const mensaje = input.value.trim();
  if (!mensaje) return;
  agregar(mensaje, "yo");
  input.value = "";
  try {
    const r = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensaje }),
    });
    if (!r.ok) { agregar("Escribe entre 2 y 500 caracteres.", "bot"); return; }
    const data = await r.json();
    agregar(data.respuesta, "bot", data.fuente);
  } catch {
    agregar("No pude conectar con el servidor.", "bot");
  }
});
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def inicio() -> str:
    return PAGINA
