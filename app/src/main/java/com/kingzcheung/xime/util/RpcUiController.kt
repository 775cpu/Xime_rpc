package com.kingzcheung.xime.util

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

object RpcUiController {
    private val _state = MutableStateFlow<Map<String, String>>(emptyMap())
    val state: StateFlow<Map<String, String>> = _state.asStateFlow()

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
}