package com.kingzcheung.xime.util

import android.content.Context
import com.kingzcheung.xime.rime.RimeEngine
import com.kingzcheung.xime.settings.SchemaManager
import com.kingzcheung.xime.settings.SettingsPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import org.json.JSONArray
import org.json.JSONObject

object RpcUiController {
    private var context: Context? = null
    private val _state = MutableStateFlow<Map<String, String>>(emptyMap())
    val state: StateFlow<Map<String, String>> = _state.asStateFlow()

    fun initialize(appContext: Context) {
        context = appContext.applicationContext
    }

    @JvmStatic
    fun setState(key: String, value: String) {
        require(key.isNotBlank()) { "UI state key must not be blank" }
        _state.update { it + (key to value) }
    }

    @JvmStatic
    fun removeState(key: String) {
        _state.update { it - key }
    }

    @JvmStatic
    fun getState(key: String): String? = _state.value[key]

    @JvmStatic
    fun clearState() {
        _state.value = emptyMap()
    }

    @JvmStatic
    fun listSchemas(): String {
        val appContext = context ?: return JSONObject().put("error", "controller_not_initialized").toString()
        val enabled = SchemaManager.getEnabledSchemas(appContext).toSet()
        val current = SettingsPreferences.getCurrentSchema(appContext)
        val schemas = JSONArray()
        SchemaManager.discoverSchemas(appContext).forEach { schema ->
            schemas.put(JSONObject()
                .put("id", schema.schemaId)
                .put("name", schema.name)
                .put("version", schema.version)
                .put("author", schema.author)
                .put("description", schema.description)
                .put("enabled", schema.schemaId in enabled)
                .put("current", schema.schemaId == current))
        }
        return JSONObject()
            .put("current", current)
            .put("enabled", JSONArray(enabled.toList()))
            .put("schemas", schemas)
            .toString()
    }

    @JvmStatic
    fun setOnlySchema(schemaId: String): String {
        val appContext = context ?: return errorResult("controller_not_initialized")
        val schema = SchemaManager.discoverSchemas(appContext)
            .firstOrNull { it.schemaId == schemaId }
            ?: return errorResult("schema_not_found:$schemaId")

        SchemaManager.setEnabledSchemas(appContext, listOf(schema.schemaId))
        SettingsPreferences.setCurrentSchema(appContext, schema.schemaId)

        val rime = if (RimeEngine.isInitialized()) RimeEngine.getInstance() else null
        val switched = rime?.let { engine ->
            schema.schemaId in engine.getAvailableSchemas() && engine.switchSchema(schema.schemaId)
        } ?: false

        return JSONObject()
            .put("ok", true)
            .put("id", schema.schemaId)
            .put("name", schema.name)
            .put("switched", switched)
            .put("requires_deploy", !switched)
            .toString()
    }

    private fun errorResult(message: String): String =
        JSONObject().put("ok", false).put("error", message).toString()
}