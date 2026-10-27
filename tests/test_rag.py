import pytest
from fastapi.testclient import TestClient

from app import rag
from app.main import app

client = TestClient(app)


def frag(id_, estado="vigente", vector=(1.0, 0.0)):
    doc = id_.split("/")[0]
    return {"id": id_, "doc": doc, "titulo": doc, "version": 1, "vigente_desde": "2026-09-15",
            "estado": estado, "texto": id_, "vector": list(vector)}


@pytest.fixture
def indice_falso(monkeypatch):
    falso = [
        frag("cambios-talla/plazo", estado="reemplazada", vector=(1.0, 0.0)),
        frag("cambios-talla/plazo", vector=(0.9, 0.1)),
        frag("garantia-legal/plazo", vector=(0.0, 1.0)),
    ]
    monkeypatch.setattr(rag, "_indice", falso)
    return falso


def test_fragmenta_por_seccion_con_version_y_estado():
    fragmentos = rag.cargar_fragmentos()
    vigente = [f for f in fragmentos if f["doc"] == "cambios-talla" and f["estado"] == "vigente"]
    antigua = [f for f in fragmentos if f["doc"] == "cambios-talla" and f["estado"] == "reemplazada"]
    assert {f["id"] for f in vigente} == {"cambios-talla/plazo", "cambios-talla/condiciones", "cambios-talla/donde"}
    assert vigente[0]["version"] == 2 and antigua[0]["version"] == 1


def test_busqueda_ignora_politicas_reemplazadas(indice_falso):
    resultado = rag.buscar([1.0, 0.0], indice_falso, k=2)
    assert all(f["estado"] == "vigente" for f in resultado)
    assert resultado[0]["id"] == "cambios-talla/plazo"


def test_solo_valen_citas_de_fragmentos_recuperados(indice_falso):
    texto = "Son 30 días [cambios-talla/plazo] y además [inventada/seccion]."
    assert rag.citas_validas(texto, indice_falso) == ["cambios-talla/plazo"]


def test_responde_con_citas_cuando_hay_respaldo(indice_falso):
    r = rag.responder("¿plazo de cambio?", "modelo", embed=lambda t: [[1.0, 0.0]],
                      llm=lambda p, f, m: "Hasta 30 días [cambios-talla/plazo].")
    assert r["fuente"] == "rag" and r["citas"] == ["cambios-talla/plazo"]


def test_se_abstiene_si_la_respuesta_no_cita(indice_falso):
    r = rag.responder("¿horario de tienda?", "modelo", embed=lambda t: [[0.0, 1.0]],
                      llm=lambda p, f, m: "Abre a las 10.")
    assert r["fuente"] == "ayuda" and r["respuesta"] == rag.SIN_RESPALDO


def test_se_abstiene_si_declara_sin_respaldo_aunque_cite(indice_falso):
    r = rag.responder("¿descuento de colaboradores?", "modelo", embed=lambda t: [[1.0, 0.0]],
                      llm=lambda p, f, m: "SIN_RESPALDO [cambios-talla/plazo]")
    assert r["fuente"] == "ayuda" and r["citas"] == []


def test_api_posventa_sin_clave_no_falla(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/posventa", json={"mensaje": "¿Puedo cambiar una talla?"})
    assert r.status_code == 200 and r.json()["fuente"] == "ayuda"
    assert client.post("/posventa", json={"mensaje": ""}).status_code == 422
