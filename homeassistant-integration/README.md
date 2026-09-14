# Laro Home Assistant Integration

Connect [Laro](https://laro.food) to Home Assistant — works with the **cloud** app at `https://laro.food` and with any **self-hosted** Laro server.

Provides sensors, a meal-plan calendar, and services for recipes, meals, and shopping lists.

## Features

- **Cloud or self-host**: use `https://laro.food` or your own server URL
- **Auto-discovery**: local Laro instances via Zeroconf/mDNS (self-host)
- **Sensors**: recipe count, today's meals, tonight's suggestion, shopping items, favorites, weekly plans, AI quota
- **Calendar**: meal plans as a Home Assistant calendar
- **Services**: add to shopping list, create meal plan, import recipe from URL

## Installation

### HACS (recommended)

The public HACS repository is:

`https://github.com/Domocn/Laro-home-assistant-addon`

(Same GitHub repo as the Supervisor add-on store — HACS installs only the **integration** under `custom_components/laro`.)

1. In Home Assistant open **HACS → Integrations**
2. ⋮ menu → **Custom repositories**
3. Repository: `https://github.com/Domocn/Laro-home-assistant-addon`
4. Category: **Integration** (not Theme / Plugin)
5. Add → search **Laro** → **Download**
6. Restart Home Assistant
7. **Settings → Devices & Services → Add Integration → Laro**

### Manual installation

1. Copy `custom_components/laro` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

### Cloud (laro.food)

1. Sign in at [laro.food](https://laro.food)
2. Go to **Settings → API Tokens**
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
   - Local add-on: use the add-on's published port / ingress backend URL
   - Public HTTPS: `https://laro.yourdomain.com`

### Auto-discovery

If Zeroconf is enabled on a self-hosted Laro (default), Home Assistant may discover it on your LAN. Cloud accounts are configured manually with `https://laro.food`.

## Getting an API Token

1. Log into Laro (cloud or self-host)
2. Go to **Settings → API Tokens**
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
  url: "https://example.com/recipe"
```

## Supervisor add-on vs integration

| | Custom integration (this) | Supervisor add-on |
|--|---------------------------|-------------------|
| Purpose | Sensors / calendar / services against an existing Laro API | Runs a full Laro stack inside HA OS |
| Cloud (`laro.food`) | Yes | No — skip the add-on |
| Install via | **HACS → Integration** | **Add-on Store → Repositories** |
| Repo URL | `https://github.com/Domocn/Laro-home-assistant-addon` | same URL |

## Support

- Docs / issues: [Domocn/Laro](https://github.com/Domocn/Laro/issues)
- HACS + add-on store repo: [Domocn/Laro-home-assistant-addon](https://github.com/Domocn/Laro-home-assistant-addon)

## License

MIT
