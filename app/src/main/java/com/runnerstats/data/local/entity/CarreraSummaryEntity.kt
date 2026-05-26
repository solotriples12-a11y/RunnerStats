package com.runnerstats.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "carrera_summary",
    indices = [Index("fecha_inicio_unix")],
)
data class CarreraSummaryEntity(
    @PrimaryKey
    val id: String,
    @ColumnInfo(name = "fecha_inicio_unix")
    val fechaInicioUnix: Long,
    @ColumnInfo(name = "distancia_metros")
    val distanciaMetros: Int,
    @ColumnInfo(name = "duracion_segundos")
    val duracionSegundos: Int,
    @ColumnInfo(name = "ritmo_medio_seg_per_km")
    val ritmoMedioSegPerKm: Int,
    @ColumnInfo(name = "frecuencia_cardiaca_media")
    val frecuenciaCardiacaMedia: Int?,
    @ColumnInfo(name = "vo2_max")
    val vo2Max: Float?,
    @ColumnInfo(name = "desnivel_positivo_metros")
    val desnivelPositivoMetros: Int,
    @ColumnInfo(name = "desnivel_negativo_metros")
    val desnivelNegativoMetros: Int,
    @ColumnInfo(name = "es_record_personal")
    val esRecordPersonal: Boolean,
)
