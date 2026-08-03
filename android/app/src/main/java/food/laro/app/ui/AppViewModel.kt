package food.laro.app.ui

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import food.laro.app.ai.MediaPipeOnDeviceAi
import food.laro.app.ai.RecipeParser
import food.laro.app.data.ApiClient
import food.laro.app.data.Ingredient
import food.laro.app.data.LaroApi
import food.laro.app.data.LoginRequest
import food.laro.app.data.Recipe
import food.laro.app.data.RegisterRequest
import food.laro.app.data.Session
import kotlinx.coroutines.launch

enum class Screen { ServerConfig, Auth, Recipes }

data class UiState(
    val screen: Screen = Screen.ServerConfig,
    val serverUrl: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
    val recipes: List<Recipe> = emptyList(),
    val userName: String? = null,
    val onDeviceInfo: String = "",
    val onDeviceAvailable: Boolean = false,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val session = Session(app)
    private val onDeviceAi = MediaPipeOnDeviceAi(app)

    private var token: String? = null
    private var apiRef: LaroApi? = null
    private var apiBaseUrl: String = ""

    var state by mutableStateOf(UiState())
        private set

    init {
        onDeviceAi.let {
            state = state.copy(
                onDeviceAvailable = it.isAvailable(),
                onDeviceInfo = it.describe(),
            )
        }
        viewModelScope.launch {
            val url = session.serverUrlOnce()
            token = session.tokenOnce()
            val name = session.userNameOnce()
            if (url.isNullOrBlank()) {
                state = state.copy(screen = Screen.ServerConfig)
            } else {
                apiBaseUrl = url
                state = state.copy(serverUrl = url, userName = name)
                if (!token.isNullOrBlank()) {
                    state = state.copy(screen = Screen.Recipes)
                    loadRecipes()
                } else {
                    state = state.copy(screen = Screen.Auth)
                }
            }
        }
    }

    private fun api(): LaroApi {
        val current = apiRef
        if (current != null && apiBaseUrl == state.serverUrl) return current
        val built = ApiClient.create(state.serverUrl) { token }
        apiRef = built
        apiBaseUrl = state.serverUrl
        return built
    }

    private fun recipeParser() = RecipeParser(onDeviceAi, api())

    fun clearMessages() {
        state = state.copy(error = null, message = null)
    }

    fun connect(url: String) {
        val normalized = normalizeUrl(url)
        viewModelScope.launch {
            state = state.copy(loading = true, error = null, message = null)
            try {
                val probe = ApiClient.create(normalized) { token }
                val health = probe.health()
                session.setServerUrl(normalized)
                state = state.copy(
                    serverUrl = normalized,
                    loading = false,
                    screen = if (!token.isNullOrBlank()) Screen.Recipes else Screen.Auth,
                    message = "Connected to ${health.app ?: "server"}",
                )
                if (!token.isNullOrBlank()) loadRecipes()
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Cannot reach server: ${e.message}")
            }
        }
    }

    fun register(name: String, email: String, password: String) {
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                val res = api().register(RegisterRequest(email.trim(), password, name.trim()))
                onAuth(res.token, res.user.name)
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Registration failed: ${e.message}")
            }
        }
    }

    fun login(email: String, password: String) {
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                val res = api().login(LoginRequest(email.trim(), password))
                onAuth(res.token, res.user.name)
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Login failed: ${e.message}")
            }
        }
    }

    private suspend fun onAuth(newToken: String, name: String?) {
        token = newToken
        session.setAuth(newToken, name)
        state = state.copy(loading = false, screen = Screen.Recipes, userName = name)
        loadRecipes()
    }

    fun loadRecipes() {
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                val recipes = api().listRecipes()
                state = state.copy(loading = false, recipes = recipes)
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Could not load recipes: ${e.message}")
            }
        }
    }

    /** Parse pasted text into a recipe (on-device when possible) and save it. */
    fun addRecipeFromText(text: String, onDone: () -> Unit) {
        if (text.isBlank()) {
            state = state.copy(error = "Paste some recipe text first")
            return
        }
        viewModelScope.launch {
            state = state.copy(loading = true, error = null, message = null)
            try {
                val parsed = recipeParser().parse(text)
                val saved = api().createRecipe(parsed.recipe.copy(id = null))
                val where = if (parsed.usedOnDevice) "on-device AI (${parsed.engine})" else "server AI"
                state = state.copy(
                    loading = false,
                    message = "Added \"${saved.title}\" via $where",
                )
                loadRecipes()
                onDone()
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Import failed: ${e.message}")
            }
        }
    }

    /** Save a manually-entered recipe. */
    fun addRecipeManual(title: String, ingredientsText: String, stepsText: String, onDone: () -> Unit) {
        if (title.isBlank()) {
            state = state.copy(error = "Give the recipe a title")
            return
        }
        val ingredients = ingredientsText.lines()
            .map { it.trim() }.filter { it.isNotEmpty() }
            .map { Ingredient(name = it) }
        val steps = stepsText.lines().map { it.trim() }.filter { it.isNotEmpty() }
        viewModelScope.launch {
            state = state.copy(loading = true, error = null)
            try {
                val saved = api().createRecipe(
                    Recipe(title = title.trim(), ingredients = ingredients, instructions = steps)
                )
                state = state.copy(loading = false, message = "Added \"${saved.title}\"")
                loadRecipes()
                onDone()
            } catch (e: Exception) {
                state = state.copy(loading = false, error = "Save failed: ${e.message}")
            }
        }
    }

    fun logout() {
        viewModelScope.launch {
            token = null
            session.clearAuth()
            state = state.copy(screen = Screen.Auth, recipes = emptyList(), userName = null)
        }
    }

    private fun normalizeUrl(raw: String): String {
        var url = raw.trim()
        if (!url.startsWith("http://") && !url.startsWith("https://")) url = "http://$url"
        return url.trimEnd('/')
    }
}
