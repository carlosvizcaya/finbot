import pytest

from app import finanzas


def test_cuota_caso_de_referencia():
    # 10 millones a 36 meses al 12 % anual: cuota conocida de $332.143
    assert round(finanzas.cuota_mensual(10_000_000, 12, 36)) == 332_143


def test_cuota_con_tasa_cero_divide_en_partes_iguales():
    assert finanzas.cuota_mensual(1_200_000, 0, 12) == 100_000


def test_total_e_intereses_son_consistentes():
    total = finanzas.total_pagado(10_000_000, 12, 36)
    intereses = finanzas.intereses_totales(10_000_000, 12, 36)
    # Total exacto (sin redondear la cuota antes de multiplicar)
    assert round(total) == 11_957_152
    assert intereses == pytest.approx(total - 10_000_000)


def test_ahorro_mensual_sin_rentabilidad():
    assert round(finanzas.ahorro_mensual_para_meta(3_000_000, 18)) == 166_667


def test_interes_compuesto_un_anio_capitalizacion_mensual():
    assert round(finanzas.interes_compuesto(1_000_000, 12, 12)) == 1_126_825


@pytest.mark.parametrize("args", [(0, 12, 36), (10_000, 12, 0), (10_000, -1, 12)])
def test_valores_invalidos_lanzan_error(args):
    with pytest.raises(ValueError):
        finanzas.cuota_mensual(*args)
