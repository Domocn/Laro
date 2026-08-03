package food.laro.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import food.laro.app.data.Recipe

@Composable
fun ServerConfigScreen(
    state: UiState,
    modifier: Modifier = Modifier,
    onConnect: (String) -> Unit,
) {
    var url by remember { mutableStateOf(state.serverUrl.ifBlank { "http://" }) }
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Connect to your Laro server", fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(8.dp))
        Text("Enter the address of your self-hosted Laro backend, e.g. http://192.168.1.10:8001")
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Server URL") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = { onConnect(url) },
            enabled = !state.loading,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (state.loading) "Connecting…" else "Connect") }
        Spacer(Modifier.height(24.dp))
        OnDeviceBadge(state)
    }
}

@Composable
fun AuthScreen(
    state: UiState,
    modifier: Modifier = Modifier,
    onLogin: (String, String) -> Unit,
    onRegister: (String, String, String) -> Unit,
) {
    var isRegister by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.Center,
    ) {
        Text(if (isRegister) "Create your account" else "Welcome back", fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(16.dp))
        if (isRegister) {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
        }
        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = {
                if (isRegister) onRegister(name, email, password) else onLogin(email, password)
            },
            enabled = !state.loading,
            modifier = Modifier.fillMaxWidth(),
        ) { Text(if (isRegister) "Sign up" else "Log in") }
        TextButton(onClick = { isRegister = !isRegister }) {
            Text(if (isRegister) "Have an account? Log in" else "New here? Create an account")
        }
        Spacer(Modifier.height(8.dp))
        Text("Server: ${state.serverUrl}")
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecipesScreen(
    state: UiState,
    modifier: Modifier = Modifier,
    onRefresh: () -> Unit,
    onAddFromText: (String, () -> Unit) -> Unit,
    onAddManual: (String, String, String, () -> Unit) -> Unit,
    onLogout: () -> Unit,
) {
    var showAdd by remember { mutableStateOf(false) }

    Column(modifier = modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("Recipes") },
            actions = {
                IconButton(onClick = onRefresh) {
                    Icon(Icons.Filled.Refresh, contentDescription = "Refresh")
                }
                IconButton(onClick = onLogout) {
                    Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Log out")
                }
            },
        )
        OnDeviceBadge(state, modifier = Modifier.padding(horizontal = 16.dp))
        Spacer(Modifier.height(8.dp))
        Button(
            onClick = { showAdd = true },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
        ) {
            Icon(Icons.Filled.Add, contentDescription = null)
            Spacer(Modifier.height(0.dp))
            Text("  Add recipe")
        }
        Spacer(Modifier.height(8.dp))

        if (state.recipes.isEmpty()) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                if (state.loading) CircularProgressIndicator()
                else Text("No recipes yet. Tap \u201CAdd recipe\u201D to create one.")
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                items(state.recipes) { recipe -> RecipeCard(recipe) }
            }
        }
    }

    if (showAdd) {
        AddRecipeDialog(
            state = state,
            onDismiss = { showAdd = false },
            onAddFromText = { text -> onAddFromText(text) { showAdd = false } },
            onAddManual = { t, i, s -> onAddManual(t, i, s) { showAdd = false } },
        )
    }
}

@Composable
private fun RecipeCard(recipe: Recipe) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Text(recipe.title, fontWeight = FontWeight.Bold)
            if (!recipe.description.isNullOrBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(recipe.description)
            }
            Spacer(Modifier.height(4.dp))
            Text("${recipe.ingredients.size} ingredients · ${recipe.instructions.size} steps · serves ${recipe.servings ?: 4}")
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddRecipeDialog(
    state: UiState,
    onDismiss: () -> Unit,
    onAddFromText: (String) -> Unit,
    onAddManual: (String, String, String) -> Unit,
) {
    var useAi by remember { mutableStateOf(true) }
    var pasted by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var ingredients by remember { mutableStateOf("") }
    var steps by remember { mutableStateOf("") }

    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {
            Button(
                enabled = !state.loading,
                onClick = {
                    if (useAi) onAddFromText(pasted) else onAddManual(title, ingredients, steps)
                },
            ) { Text(if (state.loading) "Working…" else "Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
        title = { Text(if (useAi) "Add from text (AI)" else "Add manually") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Row {
                    OutlinedButton(onClick = { useAi = true }, enabled = !useAi) { Text("AI") }
                    Spacer(Modifier.height(0.dp))
                    Text("  ")
                    OutlinedButton(onClick = { useAi = false }, enabled = useAi) { Text("Manual") }
                }
                Spacer(Modifier.height(8.dp))
                if (useAi) {
                    Text(
                        if (state.onDeviceAvailable)
                            "Parsed on this phone using ${state.onDeviceInfo}."
                        else
                            "No on-device model found — will use the server's AI. Add a .task/.bin model to the app's files dir to run fully on-device.",
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = pasted,
                        onValueChange = { pasted = it },
                        label = { Text("Paste recipe text") },
                        modifier = Modifier.fillMaxWidth().height(180.dp),
                    )
                } else {
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it },
                        label = { Text("Title") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = ingredients,
                        onValueChange = { ingredients = it },
                        label = { Text("Ingredients (one per line)") },
                        modifier = Modifier.fillMaxWidth().height(120.dp),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = steps,
                        onValueChange = { steps = it },
                        label = { Text("Steps (one per line)") },
                        modifier = Modifier.fillMaxWidth().height(120.dp),
                    )
                }
            }
        },
    )
}

@Composable
private fun OnDeviceBadge(state: UiState, modifier: Modifier = Modifier) {
    Card(modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text(
                if (state.onDeviceAvailable) "On-device AI ready" else "On-device AI: not configured",
                fontWeight = FontWeight.Bold,
            )
            Text(state.onDeviceInfo)
        }
    }
}
