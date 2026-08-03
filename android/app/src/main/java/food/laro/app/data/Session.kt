package food.laro.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "laro_session")

/**
 * Persists the configured server URL and auth token (mirrors the web app's
 * localStorage keys so behaviour is consistent across clients).
 */
class Session(private val context: Context) {

    private val serverUrlKey = stringPreferencesKey("laro_server_url")
    private val tokenKey = stringPreferencesKey("token")
    private val userNameKey = stringPreferencesKey("user_name")

    val serverUrl = context.dataStore.data.map { it[serverUrlKey] }
    val token = context.dataStore.data.map { it[tokenKey] }

    suspend fun serverUrlOnce(): String? = context.dataStore.data.map { it[serverUrlKey] }.first()
    suspend fun tokenOnce(): String? = context.dataStore.data.map { it[tokenKey] }.first()
    suspend fun userNameOnce(): String? = context.dataStore.data.map { it[userNameKey] }.first()

    suspend fun setServerUrl(url: String) {
        context.dataStore.edit { it[serverUrlKey] = url.trimEnd('/') }
    }

    suspend fun setAuth(token: String, userName: String?) {
        context.dataStore.edit {
            it[tokenKey] = token
            if (userName != null) it[userNameKey] = userName
        }
    }

    suspend fun clearAuth() {
        context.dataStore.edit {
            it.remove(tokenKey)
            it.remove(userNameKey)
        }
    }
}
