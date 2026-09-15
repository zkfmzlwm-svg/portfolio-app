#!/usr/bin/env sh
# Gradle wrapper 실행기.
# gradle-wrapper.jar가 없으면 시스템에 설치된 gradle로 폴백한다.
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
JAR="$DIR/gradle/wrapper/gradle-wrapper.jar"
if [ -f "$JAR" ]; then
  exec java -classpath "$JAR" org.gradle.wrapper.GradleWrapperMain "$@"
fi
if command -v gradle >/dev/null 2>&1; then
  echo "gradle-wrapper.jar 없음 — 시스템 gradle 사용" >&2
  exec gradle "$@"
fi
echo "오류: gradle-wrapper.jar가 없고 시스템 gradle도 설치되어 있지 않습니다." >&2
echo "Android Studio에서 열거나, 'brew install gradle'(또는 sdkman) 후 재시도하세요." >&2
exit 1
