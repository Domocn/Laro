package food.laro.app.ai

import com.google.gson.Gson
import food.laro.app.data.ImportTextRequest
import food.laro.app.data.LaroApi
import food.laro.app.data.Recipe

data class ParseResult(
    val recipe: Recipe,
    val usedOnDevice: Boolean,
    val engine: String,
)

/**
 * Turns free-form pasted text into a structured [Recipe].
 *
 * Prefers the phone's on-device AI (no data leaves the device, works offline).
 * Falls back to the server's /api/ai/import-text endpoint when no local model is
 * available.
 */
class RecipeParser(
    private val onDeviceAi: OnDeviceAi,
    private val api: LaroApi,
    private val gson: Gson = Gson(),
) {

    suspend fun parse(text: String): ParseResult {
        if (onDeviceAi.isAvailable()) {
            val json = onDeviceAi.generate(buildPrompt(text))
            val recipe = parseRecipeJson(json)
            if (recipe != null) {
                return ParseResult(recipe, usedOnDevice = true, engine = onDeviceAi.describe())
            }
            // On-device output wasn't valid JSON; fall through to the server.
        }
        val response = api.importText(ImportTextRequest(text))
        return ParseResult(response.recipe, usedOnDevice = false, engine = "Server AI")
    }

    private fun parseRecipeJson(raw: String): Recipe? {
        val json = extractJsonObject(raw) ?: return null
        return try {
            val recipe = gson.fromJson(json, Recipe::class.java)
            if (recipe?.title.isNullOrBlank()) null else recipe
        } catch (e: Exception) {
            null
        }
    }

    /** Models often wrap JSON in prose or ```json fences; pull out the object. */
    private fun extractJsonObject(raw: String): String? {
        val start = raw.indexOf('{')
        val end = raw.lastIndexOf('}')
        if (start == -1 || end == -1 || end <= start) return null
        return raw.substring(start, end + 1)
    }

    private fun buildPrompt(text: String): String = """
        You are a recipe parser. Read the recipe below and respond with ONLY a JSON
        object (no markdown, no commentary) using exactly these keys:
        {
          "title": string,
          "description": string,
          "ingredients": [{"name": string, "amount": string, "unit": string}],
          "instructions": [string],
          "servings": number,
          "prep_time": number,
          "cook_time": number,
          "category": string
        }

        Recipe:
        ${text.take(3000)}
    """.trimIndent()
}
