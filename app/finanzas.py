"""Funciones financieras puras: no dependen de FastAPI ni de ningún servicio externo.

Las tasas se expresan en porcentaje anual (12 significa 12 % anual).
"""


def _tasa_mensual(tasa_anual_pct: float) -> float:
    if tasa_anual_pct < 0:
        raise ValueError("La tasa no puede ser negativa")
    return tasa_anual_pct / 100 / 12


def _validar(monto: float, meses: int) -> None:
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que cero")
    if meses <= 0:
        raise ValueError("El plazo debe ser de al menos un mes")


def cuota_mensual(monto: float, tasa_anual_pct: float, meses: int) -> float:
    """Cuota fija de un crédito con sistema francés (amortización constante en cuota)."""
    _validar(monto, meses)
    i = _tasa_mensual(tasa_anual_pct)
    if i == 0:
        return monto / meses
    return monto * i / (1 - (1 + i) ** -meses)


def total_pagado(monto: float, tasa_anual_pct: float, meses: int) -> float:
    """Suma de todas las cuotas del crédito."""
    return cuota_mensual(monto, tasa_anual_pct, meses) * meses


def intereses_totales(monto: float, tasa_anual_pct: float, meses: int) -> float:
    """Lo que se paga por sobre el monto pedido."""
    return total_pagado(monto, tasa_anual_pct, meses) - monto


def ahorro_mensual_para_meta(meta: float, meses: int, tasa_anual_pct: float = 0.0) -> float:
    """Depósito mensual fijo para juntar `meta` en `meses`, con rentabilidad opcional."""
    _validar(meta, meses)
    i = _tasa_mensual(tasa_anual_pct)
    if i == 0:
        return meta / meses
    return meta * i / ((1 + i) ** meses - 1)


def interes_compuesto(
    capital: float, tasa_anual_pct: float, meses: int, capitalizaciones_por_anio: int = 12
) -> float:
    """Monto final de un capital invertido a interés compuesto durante `meses`."""
    _validar(capital, meses)
    if tasa_anual_pct < 0:
        raise ValueError("La tasa no puede ser negativa")
    r = tasa_anual_pct / 100 / capitalizaciones_por_anio
    periodos = capitalizaciones_por_anio * meses / 12
    return capital * (1 + r) ** periodos
