package food.laro.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LaroGreen = Color(0xFF6B8E6B)
private val LaroGreenDark = Color(0xFF4F6B4F)
private val Coral = Color(0xFFE07856)

private val LightColors = lightColorScheme(
    primary = LaroGreen,
    secondary = Coral,
    primaryContainer = Color(0xFFDDE8DD),
)

private val DarkColors = darkColorScheme(
    primary = LaroGreen,
    secondary = Coral,
    primaryContainer = LaroGreenDark,
)

@Composable
fun LaroTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
