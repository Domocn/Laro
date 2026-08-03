package food.laro.app.ai

import android.content.Context
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * On-device LLM powered by MediaPipe LLM Inference.
 *
 * A model file (`.task` or `.bin`, e.g. a quantized Gemma) must be placed in the
 * app's external files directory:
 *   /Android/data/food.laro.app/files/
 * When no model is present, [isAvailable] returns false and callers fall back to
 * the server-side AI endpoint.
 */
class MediaPipeOnDeviceAi(private val context: Context) : OnDeviceAi {

    @Volatile
    private var engine: LlmInference? = null

    private fun modelFile(): File? {
        val dir = context.getExternalFilesDir(null) ?: return null
        val candidates = dir.listFiles { f ->
            f.isFile && (f.name.endsWith(".task") || f.name.endsWith(".bin"))
        } ?: return null
        return candidates.firstOrNull()
    }

    override fun isAvailable(): Boolean = modelFile() != null

    override fun describe(): String {
        val model = modelFile()?.name ?: return "No on-device model installed"
        return "On-device (MediaPipe) · $model"
    }

    private fun engine(): LlmInference {
        engine?.let { return it }
        synchronized(this) {
            engine?.let { return it }
            val model = modelFile()
                ?: throw IllegalStateException("No on-device model found in external files dir")
            val options = LlmInference.LlmInferenceOptions.builder()
                .setModelPath(model.absolutePath)
                .setMaxTokens(1024)
                .build()
            return LlmInference.createFromOptions(context, options).also { engine = it }
        }
    }

    override suspend fun generate(prompt: String): String = withContext(Dispatchers.Default) {
        engine().generateResponse(prompt)
    }

    fun close() {
        synchronized(this) {
            engine?.close()
            engine = null
        }
    }
}
