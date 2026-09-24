"""
Cuándo le corresponde a una mujer responder cada cuestionario.

Los formularios declaran desde siempre una frecuencia (única vez, diario,
semanal, mensual, a demanda) y un disparador (al registro, bloqueante, manual,
día 7, día 30). Hasta ahora ninguno de los dos se leía en ninguna parte: el
listado devolvía todo lo publicado sin mirar si ya se había respondido, así que
un cuestionario de única vez se repetía para siempre y uno mensual no volvía
nunca (F5).

DECISIONES DE PRODUCTO tomadas acá, pendientes de revisión:

1. Los períodos salteados se pierden, no se acumulan. Si una mujer no responde
   el cuestionario semanal, la semana siguiente le corresponde uno solo, no
   dos. Acumular la enfrentaría a una pila de atrasos que crece sola, que es
   exactamente lo que hace abandonar un tratamiento.

2. La ventana se cuenta desde la última respuesta, no desde el calendario. Si
   responde el semanal un martes y el siguiente un viernes, el próximo le toca
   el viernes siguiente. Es más predecible para ella que una fecha fija.

3. Los disparadores temporales cuentan desde el alta de la usuaria. "Día 7"
   significa siete días desde que se registró, que es la lectura natural de un
   hito de incorporación.

4. Un cuestionario manual no se ofrece solo. Se llega a él por un enlace
   directo, normalmente porque alguien del equipo clínico se lo indicó.

5. Bloqueante no bloquea la aplicación entera desde el backend: se marca y la
   aplicación decide. Impedir el acceso a todo es una decisión de producto que
   no corresponde tomar acá.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Tuple

from app.models.clinical import DisparadorType, FrecuenciaType


class Disponibilidad(str, Enum):
    """Por qué un cuestionario se le ofrece o no a una mujer, hoy."""

    DISPONIBLE = "disponible"
    COMPLETADO = "completado"        # de única vez, ya respondido
    EN_ESPERA = "en_espera"          # periódico, esperando su próxima ventana
    PROXIMAMENTE = "proximamente"    # su disparador temporal todavía no llegó
    MANUAL = "manual"                # no se ofrece solo


PERIODOS = {
    FrecuenciaType.DIARIO: timedelta(days=1),
    FrecuenciaType.SEMANAL: timedelta(days=7),
    FrecuenciaType.MENSUAL: timedelta(days=30),
}

DEMORAS = {
    DisparadorType.DIA_7: timedelta(days=7),
    DisparadorType.DIA_30: timedelta(days=30),
}


def calcular_disponibilidad(
    frecuencia: Optional[FrecuenciaType],
    disparador: Optional[DisparadorType],
    ultima_respuesta: Optional[datetime],
    alta_usuaria: Optional[datetime],
    ahora: datetime,
) -> Tuple[Disponibilidad, Optional[datetime]]:
    """
    Devuelve el estado del cuestionario y, si corresponde, desde cuándo estará
    disponible.

    Es una función pura: no toca la base. Todo lo que necesita saber entra por
    parámetro, para que las reglas se puedan leer y probar de un vistazo.
    """
    frecuencia = frecuencia or FrecuenciaType.UNICA_VEZ
    disparador = disparador or DisparadorType.AL_REGISTRO

    # 1. Los manuales no se ofrecen solos, se respondan o no.
    if disparador == DisparadorType.MANUAL:
        return Disponibilidad.MANUAL, None

    # 2. Un disparador temporal que todavía no llegó gana sobre todo lo demás,
    #    salvo que la mujer ya lo haya respondido por otra vía.
    demora = DEMORAS.get(disparador)
    if demora and alta_usuaria and not ultima_respuesta:
        disponible_desde = alta_usuaria + demora
        if ahora < disponible_desde:
            return Disponibilidad.PROXIMAMENTE, disponible_desde

    # 3. A demanda siempre está a mano: es la que la mujer decide repetir.
    if frecuencia == FrecuenciaType.A_DEMANDA:
        return Disponibilidad.DISPONIBLE, None

    # 4. Sin respuesta previa, cualquier cuestionario está disponible.
    if not ultima_respuesta:
        return Disponibilidad.DISPONIBLE, None

    # 5. De única vez: respondido es respondido.
    if frecuencia == FrecuenciaType.UNICA_VEZ:
        return Disponibilidad.COMPLETADO, None

    # 6. Periódico: la ventana se cuenta desde la última respuesta, y los
    #    períodos salteados no se acumulan.
    periodo = PERIODOS.get(frecuencia)
    if not periodo:
        return Disponibilidad.DISPONIBLE, None

    proxima = ultima_respuesta + periodo
    if ahora >= proxima:
        return Disponibilidad.DISPONIBLE, None
    return Disponibilidad.EN_ESPERA, proxima


def es_bloqueante(
    disparador: Optional[DisparadorType], estado: Disponibilidad
) -> bool:
    """
    Si este cuestionario debería anteponerse a todo lo demás.

    Sólo tiene sentido mientras esté disponible: uno bloqueante ya respondido
    no bloquea nada.
    """
    return (
        disparador == DisparadorType.BLOQUEANTE
        and estado == Disponibilidad.DISPONIBLE
    )
