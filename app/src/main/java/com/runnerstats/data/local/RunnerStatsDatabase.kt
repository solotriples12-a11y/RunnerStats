package com.runnerstats.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.runnerstats.data.local.dao.CarreraMuestreoDao
import com.runnerstats.data.local.dao.CarreraSummaryDao
import com.runnerstats.data.local.entity.CarreraMuestreoEntity
import com.runnerstats.data.local.entity.CarreraSummaryEntity

@Database(
    entities = [CarreraSummaryEntity::class, CarreraMuestreoEntity::class],
    version = 1,
    exportSchema = true,
)
abstract class RunnerStatsDatabase : RoomDatabase() {
    abstract fun summaryDao(): CarreraSummaryDao
    abstract fun muestreoDao(): CarreraMuestreoDao
}
