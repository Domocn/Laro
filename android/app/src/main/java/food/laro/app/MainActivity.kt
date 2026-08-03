package food.laro.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import food.laro.app.ui.AppViewModel
import food.laro.app.ui.AuthScreen
import food.laro.app.ui.RecipesScreen
import food.laro.app.ui.Screen
import food.laro.app.ui.ServerConfigScreen
import food.laro.app.ui.theme.LaroTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            LaroTheme {
                val vm: AppViewModel = viewModel()
                val state = vm.state
                val snackbar = remember { SnackbarHostState() }

                LaunchedEffect(state.error, state.message) {
                    val text = state.error ?: state.message
                    if (text != null) {
                        snackbar.showSnackbar(text)
                        vm.clearMessages()
                    }
                }

                Scaffold(
                    modifier = Modifier.fillMaxSize(),
                    snackbarHost = { SnackbarHost(snackbar) },
                ) { padding ->
                    val contentModifier = Modifier.padding(padding)
                    when (state.screen) {
                        Screen.ServerConfig -> ServerConfigScreen(
                            state = state,
                            modifier = contentModifier,
                            onConnect = vm::connect,
                        )
                        Screen.Auth -> AuthScreen(
                            state = state,
                            modifier = contentModifier,
                            onLogin = vm::login,
                            onRegister = vm::register,
                        )
                        Screen.Recipes -> RecipesScreen(
                            state = state,
                            modifier = contentModifier,
                            onRefresh = vm::loadRecipes,
                            onAddFromText = vm::addRecipeFromText,
                            onAddManual = vm::addRecipeManual,
                            onLogout = vm::logout,
                        )
                    }
                }
            }
        }
    }
}
