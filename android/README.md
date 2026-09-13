# SPIREXA for Android

A phone client for the dashboard: alerts pushed from the district console,
the live risk map, and the ground sensor readout. It talks to the same
server over the local network — no cloud, no Firebase, nothing to sign up
for. Five plain `GET`s over `HttpURLConnection`.

## Build

```bash
cd android
./gradlew :app:assembleDebug
```

The APK lands in `app/build/outputs/apk/debug/app-debug.apk`.

**It needs JDK 17.** Gradle 8.11 cannot parse a JDK 24+ version string and
fails with a bare `IllegalArgumentException: 26.0.2.1` that says nothing
about the cause. If `java -version` reports anything newer, point the build
at 17 for that command only:

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home ./gradlew :app:assembleDebug
```

or install it first with `brew install openjdk@17`. Android Studio uses its
own bundled JDK and is unaffected.

## Install

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

## Point it at the server

Start the server so it listens on the network rather than only on localhost:

```bash
./run.sh --lan
```

It prints an address like `http://192.168.1.24:8000`. Open **Setup** in the
app, type that in, and press *Save and reconnect*. On an emulator the host
machine is always `http://10.0.2.2:8000`.

The phone and the laptop have to be on the same WiFi. An exhibition hall
guest network that isolates clients from each other will block it — a phone
hotspot is the reliable fallback.

## What each screen does

**Alerts** — warnings an authority has pushed from the dashboard's warning
modal, each in every language that district uses, with unverified machine
translations marked as such. A foreground service keeps polling while the
app is closed and raises a system notification when one arrives.

**Map** — the eight NER states, their road network and all 311 monitored
slopes, drawn from `/api/geo`, which is the same projected geometry the web
dashboard uses, thinned for a phone. Pinch or use the buttons to zoom, tap a
point for its name, state and coordinates.

**Setup** — server address, and whatever the ground sensor is reporting. If
no node is connected it says so rather than showing invented numbers.
