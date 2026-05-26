package com.runnerstats.data.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.runnerstats.data.local.entity.CarreraMuestreoEntity
import com.runnerstats.data.local.entity.CarreraSummaryEntity
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class RunnerStatsDatabaseTest {

    private lateinit var db: RunnerStatsDatabase

    @Before
    fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, RunnerStatsDatabase::class.java)
            .build()
    }

    @After
    fun tearDown() {
        db.close()
    }

    @Test
    fun insertarSummary_seLeeOrdenado() = runTest {
        val antigua = summary(id = "a", fecha = 1_700_000_000L)
        val reciente = summary(id = "b", fecha = 1_800_000_000L)
        db.summaryDao().upsertAll(listOf(antigua, reciente))

        val orden = db.summaryDao().observarOrdenadas().first()

        assertEquals(listOf("b", "a"), orden.map { it.id })
        assertEquals(1_800_000_000L, db.summaryDao().getUltimaFechaUnix())
    }

    @Test
    fun borrarSummary_cascadeaMuestreos() = runTest {
        val carrera = summary(id = "c", fecha = 1_700_000_000L)
        db.summaryDao().upsertAll(listOf(carrera))
        db.muestreoDao().upsertAll(
            (0 until 3).map { i ->
                muestreo(carreraId = "c", timestamp = 1_700_000_000L + i)
            },
        )
        assertEquals(3, db.muestreoDao().contarDeCarrera("c"))

        db.summaryDao().borrarPorId("c")

        assertEquals(0, db.muestreoDao().contarDeCarrera("c"))
        assertNull(db.summaryDao().getPorId("c"))
    }

    private fun summary(id: String, fecha: Long) = CarreraSummaryEntity(
        id = id,
        fechaInicioUnix = fecha,
        distanciaMetros = 5000,
        duracionSegundos = 1500,
        ritmoMedioSegPerKm = 300,
        frecuenciaCardiacaMedia = 150,
        vo2Max = null,
        desnivelPositivoMetros = 0,
        desnivelNegativoMetros = 0,
        esRecordPersonal = false,
    )

    private fun muestreo(carreraId: String, timestamp: Long) = CarreraMuestreoEntity(
        carreraId = carreraId,
        timestampUnix = timestamp,
        frecuenciaCardiaca = 150,
        cadenciaSpm = 170,
        velocidadMs = 3.3f,
        altitudMetros = 100f,
        latitud = 40.4168,
        longitud = -3.7038,
    )
}
