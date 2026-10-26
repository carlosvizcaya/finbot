import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def sin_llm(monkeypatch):
    # Las pruebas no dependen de una clave real ni de la red.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def chat(mensaje):
    return client.post("/chat", json={"mensaje": mensaje})


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["llm"] is False


def test_cuota_de_credito():
    r = chat("¿Cuánto pago por un crédito de 10 millones a 36 meses al 12%?")
    assert r.status_code == 200
    assert r.json()["fuente"] == "reglas"
    assert "$332.143" in r.json()["respuesta"]


def test_meta_de_ahorro():
    r = chat("Quiero juntar 3 millones en 18 meses")
    assert r.json()["fuente"] == "reglas"
    assert "$166.667" in r.json()["respuesta"]


def test_termino_del_glosario():
    r = chat("¿Qué es la CAE?")
    assert r.json()["fuente"] == "glosario"
    assert "Carga Anual Equivalente" in r.json()["respuesta"]


def test_pregunta_abierta_sin_clave_responde_ayuda():
    r = chat("¿Me conviene prepagar mi crédito?")
    assert r.status_code == 200
    assert r.json()["fuente"] == "ayuda"


@pytest.mark.parametrize("mensaje", ["", "   ", "x" * 600])
def test_entrada_invalida_devuelve_422(mensaje):
    assert chat(mensaje).status_code == 422


def test_pagina_de_chat():
    r = client.get("/")
    assert r.status_code == 200
    assert "Finbot" in r.text
