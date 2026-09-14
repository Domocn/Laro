# Laro Home Assistant Integration

**For cloud users ([laro.food](https://laro.food)) and self-hosted Laro.**

This is the Home Assistant **custom integration** (sensors, meal calendar, services).  
It is **not** the Supervisor add-on (that runs a full Laro server inside HA OS).

| You use… | Install this |
|----------|----------------|
| **laro.food** (cloud) | This integration via **HACS** |
| Your own Laro server | This integration via **HACS** |
| Want Laro **inside** HA OS | [Supervisor add-on](https://github.com/Domocn/Laro-home-assistant-addon) instead |

## Install with HACS (cloud-friendly)

1. Open **HACS → Integrations**
2. ⋮ → **Custom repositories**
3. Repository (pick one):
   - Preferred (when available): `https://github.com/Domocn/Laro-home-assistant`
   - Works today: `https://github.com/Domocn/Laro`
4. Category: **Integration**
5. Download **Laro** → restart Home Assistant
6. **Settings → Devices & Services → Add Integration → Laro**
7. Server URL: `https://laro.food`  
8. API token: from Laro **Settings → API Tokens**

## Manual install

Copy `custom_components/laro` into Home Assistant `config/custom_components/`, restart, then add the integration as above.

## Configuration

### Cloud (laro.food)

1. Sign in at [laro.food](https://laro.food)
2. **Settings → API Tokens** → create a token (e.g. `Home Assistant`)
3. In Home Assistant add the **Laro** integration
4. URL: `https://laro.food`
5. Paste the token

### Self-hosted Laro

Same steps with your server URL, e.g. `http://192.168.1.50:8001` or `https://laro.yourdomain.com`.

## What you get

- Sensors: recipes, today’s meals, tonight’s suggestion, shopping items, favorites, weekly plans, AI quota  
- Calendar: meal plan  
- Services: shopping list, meal plan, import recipe  

## Not this package

- **Supervisor add-on** (Postgres/Redis/full stack in HA OS):  
  `https://github.com/Domocn/Laro-home-assistant-addon`  
  Skip that if you only use **laro.food**.

## Support

- Issues: https://github.com/Domocn/Laro/issues  
- Cloud app: https://laro.food  

## License

MIT
