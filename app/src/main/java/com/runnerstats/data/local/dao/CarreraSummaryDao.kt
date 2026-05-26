package com.runnerstats.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.runnerstats.data.local.entity.CarreraSummaryEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface CarreraSummaryDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<CarreraSummaryEntity>)

    @Query("SELECT * FROM carrera_summary ORDER BY fecha_inicio_unix DESC")
    fun observarOrdenadas(): Flow<List<CarreraSummaryEntity>>

    @Query("SELECT * FROM carrera_summary WHERE id = :id")
    suspend fun getPorId(id: String): CarreraSummaryEntity?

    @Query("SELECT MAX(fecha_inicio_unix) FROM carrera_summary")
    suspend fun getUltimaFechaUnix(): Long?

    @Query("DELETE FROM carrera_summary WHERE id = :id")
    suspend fun borrarPorId(id: String)
}
