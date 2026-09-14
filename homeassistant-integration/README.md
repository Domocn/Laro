# Laro Home Assistant Integration

Connect [Laro](https://laro.food) to Home Assistant — works with the **cloud** app at `https://laro.food` and with any **self-hosted** Laro server.

Provides sensors, a meal-plan calendar, and services for recipes, meals, and shopping lists.

## Features

- **Cloud or self-host**: use `https://laro.food` or your own server URL
- **Auto-discovery**: local Laro instances via Zeroconf/mDNS (self-host)
- **Sensors**:
  - Recipe count
  - Today's meals
  - Tonight's cooking suggestion
  - Shopping list items (unchecked)
  - Favorite recipes count
  - Meals planned this week
  - AI quota remaining (free-tier uses left, or `unlimited` for Premium)
- **Calendar**: meal plans as a Home Assistant calendar
- **Services**:
  - Add items to shopping list
  - Create meal plan entries
  - Import recipes from URLs

## Installation

### HACS (Recommended)

1. Add this repository (or the `homeassistant-integration` folder) to HACS as a custom repository
2. Search for "Laro" in HACS
3. Install the integration
4. Restart Home Assistant

### Manual Installation

1. Copy `custom_components/laro` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

### Cloud (laro.food)

1. Sign in at [laro.food](https://laro.food)
2. Go to **Settings → API Tokens** (Integrations)
3. Create a token named e.g. `Home Assistant`
4. In Home Assistant: **Settings → Devices & Services → Add Integration → Laro**
5. Server URL: `https://laro.food`
6. Paste the API token

### Self-hosted

1. Open your Laro web UI → **Settings → API Tokens**
2. Create a token
3. Add the Laro integration in Home Assistant
4. Server URL examples:
   - LAN: `http://192.168.1.100:8001`
   - Local add-on: `http://localhost:8001` (or the add-on's published port)
   - Public HTTPS: `https://laro.yourdomain.com`

### Auto-discovery

If Zeroconf is enabled on a self-hosted Laro (default), Home Assistant may discover it on your LAN. Cloud accounts are configured manually with `https://laro.food`.

## Getting an API Token

1. Log into Laro (cloud or self-host)
2. Go to **Settings → API Tokens** / **Integrations**
3. Click **Create New Token**
4. Copy the token (shown once)

Tokens are for integrations such as Home Assistant — they are not your login password.

## Available Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.laro_recipe_count` | Total number of recipes |
| `sensor.laro_today_meals` | Summary of today's planned meals |
| `sensor.laro_tonight_suggestion` | Dinner suggestion for tonight |
| `sensor.laro_shopping_items_unchecked` | Number of unchecked shopping list items |
| `sensor.laro_favorite_count` | Number of favorite recipes |
| `sensor.laro_meal_plans_this_week` | Number of meals planned this week |
| `sensor.laro_ai_quota_remaining` | Remaining free AI uses (`unlimited` if Premium) |

### Calendar

| Entity | Description |
|--------|-------------|
| `calendar.laro_meal_plan` | Your meal plan as a calendar |

## Services

### `laro.add_to_shopping_list`

```yaml
service: laro.add_to_shopping_list
data:
  items:
    - Milk
    - Eggs
    - Bread
```

### `laro.create_meal_plan`

```yaml
service: laro.create_meal_plan
data:
  recipe_id: "abc123"
  date: "2024-01-15"
  meal_type: "dinner"
```

### `laro.import_recipe`

```yaml
service: laro.import_recipe
data:
  url: "https://www.allrecipes.com/recipe/12345"
```

## Example Automations

### Notify about today's dinner

```yaml
automation:
  - alias: "Dinner reminder"
    trigger:
      - platform: time
        at: "16:00:00"
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Tonight's Dinner"
          message: "{{ states('sensor.laro_today_meals') }}"
```

### Shopping list alert

```yaml
automation:
  - alias: "Shopping reminder"
    trigger:
      - platform: numeric_state
        entity_id: sensor.laro_shopping_items_unchecked
        above: 10
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Shopping List"
          message: "You have {{ states('sensor.laro_shopping_items_unchecked') }} items on your shopping list"
```

## Add-on vs integration

| Setup | Use |
|-------|-----|
| **laro.food** (cloud) | This custom integration → URL `https://laro.food` |
| Self-hosted Docker / VPS | This custom integration → your server URL |
| Want Laro **inside** HA OS | [Supervisor add-on](../laro-home-assistant-addon) (separate from this integration) |

## Troubleshooting

### Cannot connect to laro.food

- Confirm the URL is exactly `https://laro.food` (HTTPS, no trailing path)
- Confirm the API token was copied in full
- From a machine on the HA network: `curl -I https://laro.food/api/health`
- If you get Cloudflare/WAF blocks (403/challenge), allow Home Assistant’s egress IP or ask support to allowlist `/api/health`, `/api/auth/me`, and `/api/homeassistant/*`

### Integration not discovering local Laro

- Discovery is LAN/Zeroconf only — cloud users should configure manually
- Ensure Laro is running and reachable
- Try manual setup with the server URL

### Invalid token

- Create a new API token in Laro Settings
- Use an API token, not a browser session cookie / JWT from DevTools
- Confirm the token has not been revoked

### Cannot connect (self-host)

- Verify the URL (include port if needed, e.g. `:8001`)
- Ensure Home Assistant can reach the host (same network or valid public HTTPS)
- Check firewall / reverse-proxy headers

## License

MIT License — see [LICENSE](../LICENSE).
