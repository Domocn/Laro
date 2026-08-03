package food.laro.app.data

import com.google.gson.annotations.SerializedName

data class HealthResponse(
    val app: String? = null,
    val version: String? = null,
)

data class RegisterRequest(
    val email: String,
    val password: String,
    val name: String,
)

data class LoginRequest(
    val email: String,
    val password: String,
)

data class User(
    val id: String,
    val email: String,
    val name: String?,
    val role: String?,
)

data class AuthResponse(
    val token: String,
    val user: User,
)

data class Ingredient(
    val name: String,
    val amount: String? = null,
    val unit: String? = null,
)

/**
 * A recipe as accepted by POST /api/recipes and returned by GET /api/recipes.
 * `id` is null when creating a new recipe.
 */
data class Recipe(
    val id: String? = null,
    val title: String,
    val description: String? = "",
    val ingredients: List<Ingredient> = emptyList(),
    val instructions: List<String> = emptyList(),
    val servings: Int? = 4,
    @SerializedName("prep_time") val prepTime: Int? = 0,
    @SerializedName("cook_time") val cookTime: Int? = 0,
    val category: String? = "Other",
    val tags: List<String> = emptyList(),
)

data class ImportTextRequest(
    val text: String,
)

/** Response wrapper for POST /api/ai/import-text -> { "recipe": {...} }. */
data class ImportTextResponse(
    val recipe: Recipe,
)
