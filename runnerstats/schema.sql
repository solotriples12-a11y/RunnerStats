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
    -- Id de la carrera que la supersede cuando dos fuentes traen la misma
    -- carrera. No se borra nada: se oculta de las consultas.
    sustituida_por            TEXT,
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

-- Mejor ventana de cada distancia dentro de cada carrera. Es una tabla
-- derivada: recorrer los 222.000 muestreos en cada visita costaba 300 ms.
-- Se recalcula al importar.
CREATE TABLE IF NOT EXISTS record_ventana (
    carrera_id   TEXT    NOT NULL
        REFERENCES carrera (id) ON DELETE CASCADE,
    metros       INTEGER NOT NULL,
    segundos     REAL    NOT NULL,
    inicio_unix  INTEGER NOT NULL,
    PRIMARY KEY (carrera_id, metros)
);

CREATE INDEX IF NOT EXISTS idx_record_metros ON record_ventana (metros, segundos);
