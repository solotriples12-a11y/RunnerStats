package com.runnerstats.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "carrera_muestreo",
    foreignKeys = [
        ForeignKey(
            entity = CarreraSummaryEntity::class,
            parentColumns = ["id"],
            childColumns = ["carrera_id"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("carrera_id")],
)
data class CarreraMuestreoEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    @ColumnInfo(name = "carrera_id")
    val carreraId: String,
    @ColumnInfo(name = "timestamp_unix")
    val timestampUnix: Long,
    @ColumnInfo(name = "frecuencia_cardiaca")
    val frecuenciaCardiaca: Int?,
    @ColumnInfo(name = "cadencia_spm")
    val cadenciaSpm: Int?,
    @ColumnInfo(name = "velocidad_ms")
    val velocidadMs: Float?,
    @ColumnInfo(name = "altitud_metros")
    val altitudMetros: Float?,
    @ColumnInfo(name = "latitud")
    val latitud: Double?,
    @ColumnInfo(name = "longitud")
    val longitud: Double?,
)
