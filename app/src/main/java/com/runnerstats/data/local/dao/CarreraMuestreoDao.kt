package com.runnerstats.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.runnerstats.data.local.entity.CarreraMuestreoEntity

@Dao
interface CarreraMuestreoDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(items: List<CarreraMuestreoEntity>)

    @Query("SELECT * FROM carrera_muestreo WHERE carrera_id = :carreraId ORDER BY timestamp_unix")
    suspend fun getDeCarrera(carreraId: String): List<CarreraMuestreoEntity>

    @Query("SELECT COUNT(*) FROM carrera_muestreo WHERE carrera_id = :carreraId")
    suspend fun contarDeCarrera(carreraId: String): Int
}
