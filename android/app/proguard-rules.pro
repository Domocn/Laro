# Keep Gson model classes (used via reflection by the Retrofit Gson converter)
-keep class food.laro.app.data.** { *; }

# Retrofit / OkHttp
-dontwarn okhttp3.**
-dontwarn retrofit2.**
-keepattributes Signature
-keepattributes *Annotation*
