package food.laro.app.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

/** Typed Retrofit interface for the Laro backend REST API under /api. */
interface LaroApi {

    @GET("api/health")
    suspend fun health(): HealthResponse

    @POST("api/auth/register")
    suspend fun register(@Body body: RegisterRequest): AuthResponse

    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequest): AuthResponse

    @GET("api/recipes")
    suspend fun listRecipes(): List<Recipe>

    @POST("api/recipes")
    suspend fun createRecipe(@Body recipe: Recipe): Recipe

    /** Server-side AI recipe parsing; used as a fallback when on-device AI is unavailable. */
    @POST("api/ai/import-text")
    suspend fun importText(@Body body: ImportTextRequest): ImportTextResponse
}
