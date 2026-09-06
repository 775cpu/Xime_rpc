#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")"

ANDROID_HOME_DEFAULT="/home/vscode/.cache/briefcase/tools/android_sdk"
if [[ ! -d "$ANDROID_HOME_DEFAULT" && -d /home/vscode/.buildozer/android/platform/android-sdk ]]; then
    ANDROID_HOME_DEFAULT="/home/vscode/.buildozer/android/platform/android-sdk"
fi

export ANDROID_HOME="${ANDROID_HOME:-$ANDROID_HOME_DEFAULT}"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$ANDROID_HOME}"
ANDROID_NDK_DEFAULT="$ANDROID_HOME/ndk/29.0.14206865"
if [[ ! -d "$ANDROID_NDK_DEFAULT" && -d /home/vscode/.buildozer/android/platform/android-ndk-r25b ]]; then
    ANDROID_NDK_DEFAULT="/home/vscode/.buildozer/android/platform/android-ndk-r25b"
fi
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_NDK_DEFAULT}"
export ANDROID_NDK_ROOT="${ANDROID_NDK_ROOT:-$ANDROID_NDK_HOME}"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-/home/vscode/.gradle}"
export PATH="/home/vscode/.local/bin:/home/vscode/.gradle/wrapper/dists/gradle-8.14.3-all/h9bud5ffjflfoe91ghcb596uv/gradle-8.14.3/bin:$PATH"
BUILD_ABIS="${BUILD_ABIS:-arm64-v8a}"
APP_NAME="${APP_NAME:-点击使用中文输入法}"
APPLICATION_ID="${APPLICATION_ID:-com.kingzcheung.xime}"
VERSION_CODE="${VERSION_CODE:-20260907}"
VERSION_NAME="${VERSION_NAME:-ABCDEFGHIJKLMNOPQRSTUVWX最多12个中文版本号字符串安装界面最多显示超过会用省略号表示长度17个字符android规范合法的是1024}"

APP_NAME="${VERSION_CODE: -4}输入法"


if [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
    export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
fi

git submodule update --init --recursive

./gradlew assembleDebug --quiet \
    "-PappName=$APP_NAME" \
    "-PapplicationId=$APPLICATION_ID" \
    "-PversionCode=$VERSION_CODE" \
    "-PversionName=$VERSION_NAME" \
    "-PbuildAbis=$BUILD_ABIS" "$@"

echo "生成的 APK："
find app/build/outputs/apk/debug -maxdepth 1 -type f -name '*.apk' -print