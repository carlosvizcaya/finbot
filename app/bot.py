"""Lógica de Finbot: primero reglas, después glosario y el LLM solo al final.

responder() devuelve {"respuesta": str, "fuente": "reglas" | "glosario" | "llm" | "ayuda"}.
Los números siempre los calculan las funciones de finanzas.py; el LLM nunca calcula.
"""

import os
import re
import unicodedata

from app import finanzas

GLOSARIO = {
    "uf": (
        "La UF (Unidad de Fomento) es una unidad de cuenta chilena que se reajusta "
        "diariamente según la inflación (IPC). Se usa en créditos hipotecarios, arriendos "
        "y seguros para que el valor no pierda poder de compra."
    ),
    "cae": (
        "La CAE (Carga Anual Equivalente) es el costo total anual de un crédito, con "
        "intereses, comisiones y seguros. Sirve para comparar créditos entre sí: a menor "
        "CAE, más barato."
    ),
    "apv": (
        "El APV (Ahorro Previsional Voluntario) es un ahorro adicional para la jubilación, "
        "aparte de la cotización obligatoria de la AFP. Tiene beneficios tributarios según "
        "el régimen que elijas (A o B)."
    ),
    "inflacion": (
        "La inflación es el aumento sostenido de los precios. En Chile se mide con el IPC. "
        "Si tu ahorro rinde menos que la inflación, en la práctica pierde poder de compra."
    ),
    "fondo mutuo": (
        "Un fondo mutuo junta el dinero de muchas personas y lo invierte en una cartera "
        "de instrumentos (acciones, bonos, depósitos). Cada aportante tiene cuotas cuyo "
        "valor sube o baja; no tiene rentabilidad garantizada."
    ),
}

AYUDA = (
    "Puedo ayudarte con: (1) la cuota de un crédito, por ejemplo «crédito de 10 millones "
    "a 36 meses al 12 %»; (2) cuánto ahorrar al mes, por ejemplo «quiero juntar 3 millones "
    "en 18 meses»; (3) interés compuesto, por ejemplo «invertir 1 millón al 6 % por 2 años»; "
    "y (4) términos como UF, CAE, APV, inflación o fondo mutuo. "
    "Es información educativa, no una asesoría financiera."
)

SYSTEM_PROMPT = (
    "Eres Finbot, un asistente de educación financiera para personas en Chile. Responde en "
    "español, en un máximo de cinco frases, con lenguaje simple. No inventes cifras, tasas ni "
    "productos específicos; si hace falta un cálculo, sugiere al usuario pedirlo con monto, "
    "plazo y tasa. No des recomendaciones de inversión personalizadas y aclara que es "
    "información educativa."
)

PALABRAS_CREDITO = ("credito", "prestamo", "cuota", "pago", "pagar", "pagaria", "deuda")
PALABRAS_AHORRO = ("juntar", "ahorrar", "ahorro", "meta", "reunir")
PALABRAS_INVERSION = ("invertir", "invierto", "inversion", "interes compuesto", "rentabilidad", "deposito")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.lower()


def _a_numero(texto: str) -> float:
    return float(texto.replace(",", "."))


def _formato_pesos(valor: float) -> str:
    return "$" + f"{round(valor):,}".replace(",", ".")


def _formato_tasa(tasa: float) -> str:
    return f"{tasa:g}".replace(".", ",")


def extraer_monto(texto: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:millones|millon|mm\b)", texto)
    if m:
        return _a_numero(m.group(1)) * 1_000_000
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*mil\b", texto)
    if m:
        return _a_numero(m.group(1)) * 1_000
    m = re.search(r"\$?\s*(\d{1,3}(?:\.\d{3})+|\d{4,})", texto)
    if m:
        return float(m.group(1).replace(".", ""))
    return None


def extraer_meses(texto: str) -> int | None:
    m = re.search(r"(\d+)\s*mes(?:es)?\b", texto)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*anos?\b", texto)
    if m:
        return int(m.group(1)) * 12
    return None


def extraer_tasa(texto: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:%|por ciento)", texto)
    return _a_numero(m.group(1)) if m else None


def _contiene(texto: str, palabras: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{p}", texto) for p in palabras)


def _por_reglas(texto: str) -> str | None:
    monto, meses, tasa = extraer_monto(texto), extraer_meses(texto), extraer_tasa(texto)
    if monto is None and meses is None and tasa is None:
        # Sin cifras es una pregunta abierta («¿me conviene prepagar?»), no un cálculo.
        return None

    if _contiene(texto, PALABRAS_AHORRO):
        if monto is None or meses is None:
            return "Para calcular tu ahorro necesito la meta y el plazo, por ejemplo «juntar 2 millones en 10 meses»."
        cuota = finanzas.ahorro_mensual_para_meta(monto, meses, tasa or 0)
        extra = f" con una rentabilidad de {_formato_tasa(tasa)} % anual" if tasa else ""
        return (
            f"Para juntar {_formato_pesos(monto)} en {meses} meses{extra} necesitas ahorrar "
            f"{_formato_pesos(cuota)} al mes."
        )

    if _contiene(texto, PALABRAS_INVERSION):
        if monto is None or meses is None or tasa is None:
            return "Para calcular interés compuesto necesito capital, tasa anual y plazo, por ejemplo «invertir 1 millón al 6 % por 2 años»."
        final = finanzas.interes_compuesto(monto, tasa, meses)
        return (
            f"Si inviertes {_formato_pesos(monto)} al {_formato_tasa(tasa)} % anual durante {meses} meses "
            f"(capitalización mensual), terminas con {_formato_pesos(final)}: "
            f"{_formato_pesos(final - monto)} de intereses."
        )

    if _contiene(texto, PALABRAS_CREDITO) or (monto and meses and tasa):
        if monto is None or meses is None or tasa is None:
            return "Para calcular la cuota necesito monto, plazo y tasa anual, por ejemplo «crédito de 10 millones a 36 meses al 12 %»."
        cuota = finanzas.cuota_mensual(monto, tasa, meses)
        total = finanzas.total_pagado(monto, tasa, meses)
        return (
            f"Para un crédito de {_formato_pesos(monto)} a {meses} meses con tasa "
            f"{_formato_tasa(tasa)} % anual: la cuota es de {_formato_pesos(cuota)} al mes. "
            f"Pagarías {_formato_pesos(total)} en total, de los cuales "
            f"{_formato_pesos(total - monto)} son intereses."
        )

    return None


def _por_glosario(texto: str) -> str | None:
    for termino, definicion in GLOSARIO.items():
        if re.search(rf"\b{termino}\b", texto):
            return definicion
    return None


def modelo_llm() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-6-luna")


def llm_disponible() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _por_llm(mensaje: str) -> str | None:
    if not llm_disponible():
        return None
    try:
        from openai import OpenAI

        cliente = OpenAI(timeout=20)
        r = cliente.chat.completions.create(
            model=modelo_llm(),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": mensaje},
            ],
        )
        return (r.choices[0].message.content or "").strip() or None
    except Exception:
        # Si el LLM falla, el bot degrada a la ayuda en vez de caerse.
        return None


def responder(mensaje: str) -> dict:
    texto = _normalizar(mensaje)

    respuesta = _por_reglas(texto)
    if respuesta:
        return {"respuesta": respuesta, "fuente": "reglas"}

    respuesta = _por_glosario(texto)
    if respuesta:
        return {"respuesta": respuesta, "fuente": "glosario"}

    respuesta = _por_llm(mensaje)
    if respuesta:
        return {"respuesta": respuesta, "fuente": "llm"}

    return {"respuesta": AYUDA, "fuente": "ayuda"}
