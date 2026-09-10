package com.kingzcheung.xime.settings

import android.util.Log
import java.io.File
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName
import kotlinx.serialization.json.Json

@Serializable
data class RpcSettings(
    @SerialName("http_enabled")
    val httpEnabled: Boolean = true,
    @SerialName("http_port")
    val httpPort: Int = 1144,
    @SerialName("http_host")
    val httpHost: String = "0.0.0.0",
    @SerialName("http_key")
    val httpKey: String = "",
    @SerialName("mqtt_enabled")
    val mqttEnabled: Boolean = false,
    @SerialName("mqtt_brokers")
    val mqttBrokers: String = "broker.emqx.io:1883",
    @SerialName("mqtt_request_topic")
    val mqttRequestTopic: String = "sys/device/request",
    @SerialName("mqtt_response_topic")
    val mqttResponseTopic: String = "sys/device/response",
    @SerialName("mqtt_pub_key")
    val mqttPubKey: String = ""
)

object RpcSettingsStore {
    const val CONFIG_PATH = "/sdcard/Alarms/xime_rpc.json"
    private const val TAG = "RpcSettingsStore"
    private val json = Json { prettyPrint = true; ignoreUnknownKeys = true }

    fun load(): RpcSettings {
        return try {
            val file = File(CONFIG_PATH)
            if (file.exists()) json.decodeFromString<RpcSettings>(file.readText()) else RpcSettings()
        } catch (error: Exception) {
            Log.w(TAG, "Unable to load RPC settings", error)
            RpcSettings()
        }
    }

    fun save(settings: RpcSettings): Boolean {
        return try {
            val file = File(CONFIG_PATH)
            file.parentFile?.mkdirs()
            file.writeText(json.encodeToString(settings))
            true
        } catch (error: Exception) {
            Log.e(TAG, "Unable to save RPC settings", error)
            false
        }
    }
}
