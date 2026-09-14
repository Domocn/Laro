# Laro Home Assistant Integration (HACS)

Connect **[laro.food](https://laro.food)** (cloud) or any self-hosted Laro server to Home Assistant.

This repository is the **HACS custom integration only** — sensors, meal calendar, and services.

It is **not** the Supervisor add-on. The add-on runs a full Laro stack inside Home Assistant OS and lives here separately:

→ [Domocn/Laro-home-assistant-addon](https://github.com/Domocn/Laro-home-assistant-addon)

| Goal | Use |
|------|-----|
| Cloud (**laro.food**) in Home Assistant | **This repo** via HACS |
| Remote / self-hosted Laro API in Home Assistant | **This repo** via HACS |
| Run Laro server inside HA OS | [Supervisor add-on](https://github.com/Domocn/Laro-home-assistant-addon) |

## Install with HACS

1. **HACS → Integrations → ⋮ → Custom repositories**
2. Repository: `https://github.com/Domocn/laro-ha-intergration`
3. Category: **Integration**
4. Download **Laro** → restart Home Assistant
5. **Settings → Devices & Services → Add Integration → Laro**

### Cloud (laro.food)

1. Sign in at [laro.food](https://laro.food)
2. **Settings → API Tokens** → create a token (e.g. `Home Assistant`)
3. In the Laro integration: URL `https://laro.food` → paste the token

### Self-hosted

Same steps with your server URL, e.g. `http://192.168.1.50:8001` or `https://laro.yourdomain.com`.

## Manual install

Copy `custom_components/laro` into Home Assistant `config/custom_components/`, restart, then add the integration.

## Features

- Sensors: recipes, today’s meals, tonight’s suggestion, shopping items, favorites, weekly plans, AI quota
- Calendar: meal plan
- Services: shopping list, meal plan, import recipe
- Zeroconf discovery for local self-hosted instances

## Support

- Issues: https://github.com/Domocn/Laro/issues
- Cloud app: https://laro.food
- Supervisor add-on (separate): https://github.com/Domocn/Laro-home-assistant-addon

## License

MIT
