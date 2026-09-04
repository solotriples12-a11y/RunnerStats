-- Modelo de datos de RunnerStats. Ver ARCHITECTURE.md.

CREATE TABLE IF NOT EXISTS carrera (
    id                        TEXT    PRIMARY KEY,
    fecha_inicio_unix         INTEGER NOT NULL,
    distancia_metros          REAL    NOT NULL,
    duracion_segundos         INTEGER NOT NULL,
    fuente                    TEXT    NOT NULL,
    fc_media                  INTEGER,
    fc_maxima                 INTEGER,
    desnivel_positivo_metros  REAL,
    desnivel_negativo_metros  REAL,
    calorias                  INTEGER,
    dispositivo               TEXT,
    importado_en              INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_carrera_fecha
    ON carrera (fecha_inicio_unix DESC);

-- Muestreos segundo a segundo. Solo los tienen las carreras de fuentes de
-- fidelidad completa; las de My Run Stats no tienen ninguno.
CREATE TABLE IF NOT EXISTS muestreo (
    carrera_id                  TEXT    NOT NULL
        REFERENCES carrera (id) ON DELETE CASCADE,
    timestamp_unix              INTEGER NOT NULL,
    distancia_acumulada_metros  REAL,
    frecuencia_cardiaca         INTEGER,
    cadencia_spm                INTEGER,
    velocidad_ms                REAL,
    altitud_metros              REAL,
    latitud                     REAL,
    longitud                    REAL,
    PRIMARY KEY (carrera_id, timestamp_unix)
);
