# Finbot

Asistente de educación financiera para Chile, hecho con FastAPI. Calcula cuotas de crédito (sistema francés), ahorro mensual para una meta e interés compuesto, y explica términos como UF, CAE, APV, inflación y fondo mutuo. Si hay `OPENAI_API_KEY`, responde preguntas abiertas con un LLM; los números siempre los calculan funciones, nunca el LLM.

Información educativa, no asesoría financiera.

## Estructura

```
app/finanzas.py   funciones puras de cálculo
app/bot.py        responder(mensaje): reglas → glosario → LLM opcional → ayuda
app/main.py       API: GET /health · POST /chat · GET / (chat HTML)
tests/            pruebas con pytest
```

## Correr en local

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q
uvicorn app.main:app --port 8000
```

Abre http://localhost:8000 o prueba con curl:

```bash
curl -s -X POST localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"mensaje":"cuota de 10 millones a 36 meses al 12%"}'
```

Para usar el LLM, copia `.env.example` como `.env`, completa la clave y cárgala antes de arrancar:

```bash
set -a; source .env; set +a
```

## Contenedor

El `Dockerfile` usa `python:3.12-slim` y arranca uvicorn en `0.0.0.0`, en el puerto de la variable `PORT` (8080 por defecto), como exige Cloud Run. `.dockerignore` deja fuera `.env`, `.venv` y las pruebas: la clave nunca viaja dentro de la imagen.

```bash
docker build -t finbot:local .
docker run --rm -e PORT=9090 -p 9090:9090 finbot:local
curl -s localhost:9090/health
```

## API

`POST /chat` recibe `{"mensaje": "..."}` (2 a 500 caracteres) y devuelve `{"respuesta": "...", "fuente": "reglas" | "glosario" | "llm" | "ayuda"}`. El campo `fuente` dice de dónde salió la respuesta.
