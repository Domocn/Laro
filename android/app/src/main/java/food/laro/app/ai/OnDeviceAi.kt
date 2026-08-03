package food.laro.app.ai

/**
 * Abstraction over an on-device generative model.
 *
 * The default implementation ([MediaPipeOnDeviceAi]) runs a local LLM via
 * MediaPipe's LLM Inference API, which uses the device's available accelerators
 * (GPU / NPU) where supported — e.g. the on-board AI chip on modern Samsung
 * Galaxy devices. It can be swapped for an AICore / Gemini Nano backed
 * implementation on devices that expose the system on-device model.
 */
interface OnDeviceAi {

    /** True when a local model is present and can be used for inference. */
    fun isAvailable(): Boolean

    /** A short human-readable description of the on-device engine/model, for the UI. */
    fun describe(): String

    /** Run a single-shot generation for [prompt]. Throws on failure. */
    suspend fun generate(prompt: String): String
}
