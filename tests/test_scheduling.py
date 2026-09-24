"""
Pruebas del planificador: cuándo le corresponde a una mujer cada cuestionario.

Son unitarias sobre funciones puras a propósito. Las reglas de periodicidad son
decisiones de producto, y conviene poder leerlas y discutirlas sin atravesar la
base ni el protocolo.
"""

from datetime import datetime, timedelta

from app.models.clinical import DisparadorType, FrecuenciaType
from app.services.scheduling import (
    Disponibilidad,
    calcular_disponibilidad,
    es_bloqueante,
)

AHORA = datetime(2026, 9, 24, 12, 0)
ALTA = AHORA - timedelta(days=60)


def estado(frecuencia, disparador=DisparadorType.AL_REGISTRO, ultima=None, alta=ALTA):
    return calcular_disponibilidad(frecuencia, disparador, ultima, alta, AHORA)


# ─────────────────────────────────────────────────────────────────────────────
# Frecuencia
# ─────────────────────────────────────────────────────────────────────────────


def test_sin_responder_todo_esta_disponible():
    for f in FrecuenciaType:
        assert estado(f)[0] == Disponibilidad.DISPONIBLE


def test_de_unica_vez_no_vuelve_a_ofrecerse():
    e, proxima = estado(FrecuenciaType.UNICA_VEZ, ultima=AHORA - timedelta(days=400))
    assert e == Disponibilidad.COMPLETADO
    assert proxima is None


def test_a_demanda_siempre_esta_a_mano():
    e, _ = estado(FrecuenciaType.A_DEMANDA, ultima=AHORA - timedelta(minutes=1))
    assert e == Disponibilidad.DISPONIBLE


def test_el_semanal_espera_su_ventana():
    e, proxima = estado(FrecuenciaType.SEMANAL, ultima=AHORA - timedelta(days=3))
    assert e == Disponibilidad.EN_ESPERA
    assert proxima == AHORA - timedelta(days=3) + timedelta(days=7)


def test_el_semanal_reaparece_cumplida_la_ventana():
    e, _ = estado(FrecuenciaType.SEMANAL, ultima=AHORA - timedelta(days=7))
    assert e == Disponibilidad.DISPONIBLE


def test_el_diario_y_el_mensual_usan_su_propio_periodo():
    assert estado(FrecuenciaType.DIARIO, ultima=AHORA - timedelta(hours=23))[0] == Disponibilidad.EN_ESPERA
    assert estado(FrecuenciaType.DIARIO, ultima=AHORA - timedelta(days=1))[0] == Disponibilidad.DISPONIBLE
    assert estado(FrecuenciaType.MENSUAL, ultima=AHORA - timedelta(days=29))[0] == Disponibilidad.EN_ESPERA
    assert estado(FrecuenciaType.MENSUAL, ultima=AHORA - timedelta(days=30))[0] == Disponibilidad.DISPONIBLE


def test_los_periodos_salteados_no_se_acumulan():
    """
    DECISIÓN DE PRODUCTO. Si una mujer no responde el semanal durante dos meses,
    al volver le corresponde uno solo, no nueve atrasados.

    Acumular la enfrentaría a una pila que crece sola, que es exactamente lo
    que hace abandonar un tratamiento.
    """
    e, proxima = estado(FrecuenciaType.SEMANAL, ultima=AHORA - timedelta(days=60))
    assert e == Disponibilidad.DISPONIBLE
    assert proxima is None


def test_la_ventana_se_cuenta_desde_la_ultima_respuesta():
    """
    DECISIÓN DE PRODUCTO. No hay fecha fija de calendario: si responde un
    viernes, el próximo le toca el viernes siguiente. Es más predecible para
    ella que un día fijo que se corre.
    """
    ultima = AHORA - timedelta(days=2)
    _, proxima = estado(FrecuenciaType.SEMANAL, ultima=ultima)
    assert proxima == ultima + timedelta(days=7)


# ─────────────────────────────────────────────────────────────────────────────
# Disparador
# ─────────────────────────────────────────────────────────────────────────────


def test_un_cuestionario_manual_no_se_ofrece_solo():
    """
    DECISIÓN DE PRODUCTO. Se llega por enlace directo, normalmente porque
    alguien del equipo clínico lo indicó.
    """
    e, _ = estado(FrecuenciaType.UNICA_VEZ, disparador=DisparadorType.MANUAL)
    assert e == Disponibilidad.MANUAL


def test_el_dia_7_no_aparece_antes_de_tiempo():
    """
    DECISIÓN DE PRODUCTO. Los disparadores temporales cuentan desde el alta de
    la usuaria, que es la lectura natural de un hito de incorporación.
    """
    alta = AHORA - timedelta(days=3)
    e, desde = estado(FrecuenciaType.UNICA_VEZ, disparador=DisparadorType.DIA_7, alta=alta)
    assert e == Disponibilidad.PROXIMAMENTE
    assert desde == alta + timedelta(days=7)


def test_el_dia_7_aparece_cumplido_el_plazo():
    alta = AHORA - timedelta(days=8)
    e, _ = estado(FrecuenciaType.UNICA_VEZ, disparador=DisparadorType.DIA_7, alta=alta)
    assert e == Disponibilidad.DISPONIBLE


def test_el_dia_30_respondido_antes_de_tiempo_no_vuelve_a_pedirse():
    """Si llegó a responderlo por otra vía, el plazo ya no tiene sentido."""
    alta = AHORA - timedelta(days=3)
    e, _ = calcular_disponibilidad(
        FrecuenciaType.UNICA_VEZ,
        DisparadorType.DIA_30,
        AHORA - timedelta(days=1),
        alta,
        AHORA,
    )
    assert e == Disponibilidad.COMPLETADO


def test_sin_fecha_de_alta_el_disparador_temporal_no_bloquea():
    """Ante un dato ausente conviene ofrecer el cuestionario, no esconderlo."""
    e, _ = estado(FrecuenciaType.UNICA_VEZ, disparador=DisparadorType.DIA_7, alta=None)
    assert e == Disponibilidad.DISPONIBLE


# ─────────────────────────────────────────────────────────────────────────────
# Bloqueante
# ─────────────────────────────────────────────────────────────────────────────


def test_un_bloqueante_pendiente_se_antepone():
    assert es_bloqueante(DisparadorType.BLOQUEANTE, Disponibilidad.DISPONIBLE) is True


def test_un_bloqueante_ya_respondido_deja_de_bloquear():
    assert es_bloqueante(DisparadorType.BLOQUEANTE, Disponibilidad.COMPLETADO) is False
    assert es_bloqueante(DisparadorType.BLOQUEANTE, Disponibilidad.EN_ESPERA) is False


def test_lo_que_no_es_bloqueante_no_bloquea():
    assert es_bloqueante(DisparadorType.AL_REGISTRO, Disponibilidad.DISPONIBLE) is False


def test_valores_ausentes_usan_el_comportamiento_por_defecto():
    """Un formulario viejo sin frecuencia ni disparador sigue funcionando."""
    e, _ = calcular_disponibilidad(None, None, None, ALTA, AHORA)
    assert e == Disponibilidad.DISPONIBLE
