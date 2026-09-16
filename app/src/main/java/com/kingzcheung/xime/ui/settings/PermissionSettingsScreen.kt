package com.kingzcheung.xime.ui.settings

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.twotone.Security
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.net.toUri

private data class RuntimePermission(
    val permission: String,
    val title: String,
    val description: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PermissionSettingsContent(onBack: () -> Unit) {
    val context = LocalContext.current
    var refreshKey by remember { mutableStateOf(0) }
    val permissions = remember(refreshKey) { findRuntimePermissions(context) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { refreshKey++ }

    fun request(permissionList: List<String>) {
        val applicable = permissionList.filter { isApplicable(it) && !isGranted(context, it) }
        if (applicable.isNotEmpty()) launcher.launch(applicable.toTypedArray())
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("权限设置") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(padding)
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                "系统会根据 Android 版本决定哪些权限可以弹窗申请。受系统保护的权限只能进入系统设置授权。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OutlinedButton(
                onClick = { request(permissions.map { it.permission }) }
            ) {
                Icon(Icons.TwoTone.Security, contentDescription = null)
                Text("申请全部可动态申请权限")
            }
            SettingsSection(title = "动态权限") {
                permissions.forEachIndexed { index, item ->
                    if (index > 0) {
                        androidx.compose.material3.HorizontalDivider(
                            modifier = Modifier.padding(start = 56.dp),
                            thickness = 0.5.dp,
                            color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
                        )
                    }
                    SettingsItem(
                        icon = Icons.TwoTone.Security,
                        title = item.title,
                        subtitle = if (isGranted(context, item.permission)) "已授权 · ${item.description}"
                        else "未授权 · ${item.description}",
                        onClick = { request(listOf(item.permission)) },
                        showArrow = false
                    )
                }
            }
            SettingsSection(title = "特殊权限") {
                SpecialPermissionItem(
                    title = "悬浮窗",
                    granted = Settings.canDrawOverlays(context),
                    onClick = {
                        openSettings(context, Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
                    }
                )
                SpecialPermissionItem(
                    title = "修改系统设置",
                    granted = Settings.System.canWrite(context),
                    onClick = {
                        openSettings(context, Settings.ACTION_MANAGE_WRITE_SETTINGS)
                    }
                )
                SpecialPermissionItem(
                    title = "忽略电池优化",
                    granted = isIgnoringBatteryOptimizations(context),
                    onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                            openSettings(context, Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
                        }
                    }
                )
                SpecialPermissionItem(
                    title = "所有文件访问",
                    granted = Build.VERSION.SDK_INT < Build.VERSION_CODES.R || Environment.isExternalStorageManager(),
                    onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                            openSettings(context, Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                        }
                    }
                )
                SpecialPermissionItem(
                    title = "安装未知应用",
                    granted = Build.VERSION.SDK_INT < Build.VERSION_CODES.O || context.packageManager.canRequestPackageInstalls(),
                    onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                            openSettings(context, Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES)
                        }
                    }
                )
            }
        }
    }
}

@Composable
private fun SpecialPermissionItem(title: String, granted: Boolean, onClick: () -> Unit) {
    SettingsItem(
        icon = Icons.TwoTone.Security,
        title = title,
        subtitle = if (granted) "已授权" else "未授权 · 点击打开系统设置",
        onClick = onClick,
        showArrow = true
    )
}

private fun findRuntimePermissions(context: Context): List<RuntimePermission> {
    val packageInfo = context.packageManager.getPackageInfo(
        context.packageName,
        PackageManager.GET_PERMISSIONS
    )
    return packageInfo.requestedPermissions.orEmpty().mapNotNull { permission ->
        val info = runCatching {
            context.packageManager.getPermissionInfo(permission, 0)
        }.getOrNull() ?: return@mapNotNull null
        if (info.protectionLevel and 0xF != 1) {
            return@mapNotNull null
        }
        RuntimePermission(permission, permissionTitle(permission), permissionDescription(permission))
    }.filter { isApplicable(it.permission) }
}

private fun permissionTitle(permission: String): String = when (permission) {
    Manifest.permission.RECORD_AUDIO -> "麦克风"
    Manifest.permission.CAMERA -> "相机"
    Manifest.permission.ACCESS_FINE_LOCATION -> "精确位置"
    Manifest.permission.ACCESS_COARSE_LOCATION -> "大致位置"
    Manifest.permission.ACCESS_BACKGROUND_LOCATION -> "后台位置"
    Manifest.permission.POST_NOTIFICATIONS -> "通知"
    Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT,
    Manifest.permission.BLUETOOTH_ADVERTISE -> "附近设备"
    Manifest.permission.READ_MEDIA_IMAGES, Manifest.permission.READ_MEDIA_VIDEO,
    Manifest.permission.READ_MEDIA_VISUAL_USER_SELECTED -> "照片和视频"
    Manifest.permission.READ_MEDIA_AUDIO -> "音乐和音频"
    Manifest.permission.READ_EXTERNAL_STORAGE -> "读取存储空间"
    Manifest.permission.WRITE_EXTERNAL_STORAGE -> "写入存储空间"
    Manifest.permission.READ_CONTACTS, Manifest.permission.WRITE_CONTACTS -> "联系人"
    Manifest.permission.READ_CALENDAR, Manifest.permission.WRITE_CALENDAR -> "日历"
    Manifest.permission.READ_PHONE_STATE -> "电话状态"
    Manifest.permission.READ_SMS, Manifest.permission.RECEIVE_SMS, Manifest.permission.SEND_SMS -> "短信"
    else -> permission.substringAfterLast('.').lowercase().replace('_', ' ')
}

private fun permissionDescription(permission: String): String = permission.substringAfterLast('.')

private fun isGranted(context: Context, permission: String): Boolean =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

private fun isApplicable(permission: String): Boolean = when {
    Build.VERSION.SDK_INT < 23 -> false
    permission == Manifest.permission.POST_NOTIFICATIONS -> Build.VERSION.SDK_INT >= 33
    permission.startsWith("android.permission.READ_MEDIA_") -> Build.VERSION.SDK_INT >= 33
    permission == Manifest.permission.ACCESS_BACKGROUND_LOCATION -> Build.VERSION.SDK_INT >= 29
    permission == Manifest.permission.BLUETOOTH_SCAN ||
        permission == Manifest.permission.BLUETOOTH_CONNECT ||
        permission == Manifest.permission.BLUETOOTH_ADVERTISE -> Build.VERSION.SDK_INT >= 31
    permission == Manifest.permission.READ_EXTERNAL_STORAGE -> Build.VERSION.SDK_INT <= 32
    permission == Manifest.permission.WRITE_EXTERNAL_STORAGE -> Build.VERSION.SDK_INT <= 29
    else -> true
}

private fun isIgnoringBatteryOptimizations(context: Context): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.M ||
        (context.getSystemService(android.os.PowerManager::class.java)
            ?.isIgnoringBatteryOptimizations(context.packageName) == true)

private fun openSettings(context: Context, action: String) {
    val intent = Intent(action, "package:${context.packageName}".toUri())
    if (context !is Activity) intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    context.startActivity(intent)
}
