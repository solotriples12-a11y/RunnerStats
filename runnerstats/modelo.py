from dataclasses import dataclass


@dataclass(frozen=True)
class Carrera:
    """Carrera normalizada, común a todos los importadores.

    Los campos opcionales son None cuando la fuente no los aporta. Eso es lo
    que expresa el nivel de fidelidad: una carrera de My Run Stats solo tiene
    fecha, distancia y duración.
    """

    id: str
    fecha_inicio_unix: int
    distancia_metros: float
    duracion_segundos: int
    fuente: str
    fc_media: int | None = None
    fc_maxima: int | None = None
    desnivel_positivo_metros: float | None = None
    desnivel_negativo_metros: float | None = None
    calorias: int | None = None
    dispositivo: str | None = None

    @property
    def ritmo_seg_por_km(self) -> float:
        return self.duracion_segundos / (self.distancia_metros / 1000)
