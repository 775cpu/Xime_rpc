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

if [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
    export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
fi

git submodule update --init --recursive

./gradlew assembleDebug --quiet "-PbuildAbis=$BUILD_ABIS" "$@"

echo "生成的 APK："
find app/build/outputs/apk/debug -maxdepth 1 -type f -name '*.apk' -print