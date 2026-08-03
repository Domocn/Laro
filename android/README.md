# Laro Android app

A native Android client for the self-hosted [Laro](../README.md) recipe manager,
built with Kotlin + Jetpack Compose. It talks to your Laro backend over the same
REST API the web app uses, and can parse recipes with **on-device AI** — using the
phone's own accelerators (GPU / NPU, e.g. the on-board AI chip on modern Samsung
Galaxy devices) so recipe text never has to leave the device.

## Features

- Connect to any self-hosted Laro server (enter the URL, e.g. `http://192.168.1.10:8001`).
- Register / log in against the backend (`/api/auth/*`).
- Browse your recipes (`GET /api/recipes`) and add new ones (`POST /api/recipes`).
- **Add a recipe from pasted text using on-device AI.** When a local model is
  installed the parsing runs entirely on the phone; otherwise it automatically
  falls back to the server's AI endpoint (`POST /api/ai/import-text`).

## On-device AI

On-device generation is provided by MediaPipe's LLM Inference API
(`com.google.mediapipe:tasks-genai`), which executes a local model on the device's
available accelerators. The engine is abstracted behind
[`OnDeviceAi`](app/src/main/java/food/laro/app/ai/OnDeviceAi.kt), so it can be
swapped for an AICore / Gemini Nano implementation on devices that expose the
system on-device model.

### Installing a model

No model is bundled (they are hundreds of MB). To enable fully on-device parsing,
push a compatible `.task` or `.bin` model (e.g. a quantized Gemma) into the app's
external files directory:

```
adb push gemma-2b-it-int4.task /sdcard/Android/data/food.laro.app/files/
```

The app auto-detects the first `.task`/`.bin` file there. Without a model, the app
still works and uses the server's AI for parsing (the UI shows which engine was
used).

> Note: true NPU acceleration and the exact on-device model availability depend on
> the device (a compatible Samsung Galaxy / Pixel is required). This project could
> not exercise real on-device inference in CI — see "Testing" below.

## Build

Requires the Android SDK (platform 35, build-tools 35) and JDK 17+.

```bash
cd android
# point the build at your SDK (or set ANDROID_HOME / sdk.dir in local.properties)
./gradlew :app:assembleDebug
# APK: app/build/outputs/apk/debug/app-debug.apk
```

Install on a device: `adb install -r app/build/outputs/apk/debug/app-debug.apk`.

## Project layout

- `app/src/main/java/food/laro/app/data` — Retrofit API client, models, session store.
- `app/src/main/java/food/laro/app/ai` — on-device AI engine + recipe parser (with server fallback).
- `app/src/main/java/food/laro/app/ui` — Compose screens and the app view model.

## Testing

- The app is compile-verified via `./gradlew :app:assembleDebug` (produces a
  working debug APK).
- Runtime UI and real on-device NPU inference require a physical device/emulator
  and a local model, which are outside this repo's CI. The server-fallback path
  exercises the same backend endpoints the web app and API tests already cover.
