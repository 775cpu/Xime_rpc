#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# 路径前缀变量（末尾带斜杠）
PREFIX="/home/vscode/"

ANDROID_HOME_DEFAULT="${PREFIX}.cache/briefcase/tools/android_sdk"
if [[ ! -d "$ANDROID_HOME_DEFAULT" && -d "${PREFIX}.buildozer/android/platform/android-sdk" ]]; then
    ANDROID_HOME_DEFAULT="${PREFIX}.buildozer/android/platform/android-sdk"
fi

export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_HOME_DEFAULT}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
ANDROID_NDK_DEFAULT="$ANDROID_HOME/ndk/29.0.14206865"
if [[ ! -d "$ANDROID_NDK_DEFAULT" && -d "${PREFIX}.buildozer/android/platform/android-ndk-r25b" ]]; then
    ANDROID_NDK_DEFAULT="${PREFIX}.buildozer/android/platform/android-ndk-r25b"
fi
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_NDK_DEFAULT}"
export ANDROID_NDK_ROOT="${ANDROID_NDK_ROOT:-$ANDROID_NDK_HOME}"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-${PREFIX}.gradle}"
export PATH="${PREFIX}.local/bin:${PREFIX}.gradle/wrapper/dists/gradle-8.14.3-all/h9bud5ffjflfoe91ghcb596uv/gradle-8.14.3/bin:$PATH"
BUILD_ABIS="${BUILD_ABIS:-arm64-v8a}"
APP_NAME="${APP_NAME:-点击使用中文输入法}"
APPLICATION_ID="${APPLICATION_ID:-com.kingzcheung.xime}"
VERSION_CODE="${VERSION_CODE:-20260911}"
VERSION_NAME="${VERSION_NAME:-最多19个英语ABCDEFGHIJKLMNOPQRS最多12个中文版本号字符串安装界面最多显示超过会用省略号表示长度17个字符android规范合法的是1024}"

APP_NAME="${VERSION_CODE: -4}输入法"


if [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
    export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
fi

git submodule update --init --recursive

ensure_native_dependency() {
    local repository="$1"
    local destination="$2"
    local marker="$destination/CMakeLists.txt"
    if [[ -f "$marker" ]]; then
        return
    fi

    local temporary_directory
    temporary_directory="$(mktemp -d)"
    trap 'rm -rf "$temporary_directory"' RETURN
    echo "缺少 native 依赖，正在下载: $repository"
    git clone --depth 1 --recurse-submodules "$repository" "$temporary_directory/source"
    mkdir -p "$destination"
    cp -a "$temporary_directory/source/." "$destination/"
    trap - RETURN
    rm -rf "$temporary_directory"
}

ensure_native_dependency "https://github.com/rime/librime.git" "app/src/main/jni/librime"
ensure_native_dependency "https://github.com/google/snappy.git" "app/src/main/jni/snappy"

# 使用数组传参，避免续行符问题
gradle_args=(
    "-PappName=$APP_NAME"
    "-PapplicationId=$APPLICATION_ID"
    "-PversionCode=$VERSION_CODE"
    "-PversionName=$VERSION_NAME"
    "-PbuildAbis=$BUILD_ABIS"
)

./gradlew assembleDebug --quiet "${gradle_args[@]}" "$@"

echo "生成的 APK："
find app/build/outputs/apk/debug -maxdepth 1 -type f -name '*.apk' -print