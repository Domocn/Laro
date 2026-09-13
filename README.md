<p align="center">
  <img src="public/logo.png" alt="Laro Logo" width="120">
</p>

<h1 align="center">Laro</h1>

<p align="center">
  <strong>Your Recipe Companion</strong><br>
  <em>Self-hosted recipe manager for home cooks</em>
</p>

<p align="center">
  <a href="#dont-want-to-self-host">Cloud Version</a> •
  <a href="#quick-start">Self-Host</a> •
  <a href="#features">Features</a> •
  <a href="#configuration">Configuration</a>
</p>

<p align="center">
  <a href="https://vibeappscanner.com/verify/2d378d8cd8825e008c77a436e04e60cfb0bd5ecac4d3dbf2f626146d18712c8e">
    <img src="https://api.vibeappscanner.com/badge/2d378d8cd8825e008c77a436e04e60cfb0bd5ecac4d3dbf2f626146d18712c8e.svg" alt="Audited by VAS">
  </a>
</p>

---

## What is Laro?

Laro is a **self-hosted recipe manager** for home cooks. Import recipes from any website with AI, track your pantry, plan weekly meals, generate shopping lists, and cook with step-by-step guidance.

**Your data stays on your server.** No cloud required.

> This public repo is a **sanitized self-host artefact** generated from the production codebase.
> Production `laro.food` is not deployed from this tree.

---

## Don't Want to Self-Host?

Use our cloud version at **[laro.food](https://laro.food)** - no setup required! Download the Android app from the Play Store and start cooking.

Self-hosted users can also use our official Android app - just point it to your server in the settings.

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repo
git clone https://github.com/Domocn/Laro.git
cd Laro

# Copy and configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings (JWT_SECRET, DATABASE_URL, …)

# Start services
docker compose up -d

# Open http://localhost:3000 (API on :8001 via compose)
# First user becomes admin!
```

### Option 2: Manual Setup

**Backend (Python 3.11+):**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — then export it (config.py does not auto-load .env)
set -a && source .env && set +a

# Run (module is server:app on port 8001)
./venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
```

**Frontend (Node 18+, CRA/craco):**
```bash
npm install
# Prefer mixed hostnames so the SPA does not collapse API port to same-origin:
PORT=3000 BROWSER=none HOST=0.0.0.0 REACT_APP_BACKEND_URL=http://localhost:8001 npm start
# Open http://127.0.0.1:3000
```

**Database (PostgreSQL 15+):**
```bash
# Create database
createdb laro

# Or with Docker
docker run -d --name laro-db \
  -e POSTGRES_USER=laro \
  -e POSTGRES_PASSWORD=your-password \
  -e POSTGRES_DB=laro \
  -p 5432:5432 \
  postgres:15
```

---

## Features

### Recipe Management
- AI-powered import from any URL
- Quick paste - AI parses raw text
- Categories, tags, and favorites
- Scale servings up/down
- Version history

### Pantry Tracking
- Track ingredients with expiry dates
- Swipe to mark used or delete
- Find recipes matching your ingredients
- AI recipe suggestions

### Meal Planning
- Weekly calendar view
- Drag-and-drop planning
- Auto-generate meal plans with AI

### Shopping Lists
- Auto-generate from meal plans
- Check off as you shop
- Smart ingredient grouping

### Cooking Mode
- Full-screen step-by-step
- AI cooking assistant
- Timer integration

---

## Android App

Download our official Android app and connect it to your self-hosted server:

1. Install the Laro app from the Play Store or [laro.food](https://laro.food)
2. Go to **Settings > Server Configuration**
3. Enter your server URL (e.g., `https://laro.yourdomain.com`)

---

## Configuration

### Required: Database

```env
DATABASE_URL=postgresql://laro:password@localhost:5432/laro
```

### Required: JWT Secret

```env
# Generate a secure random string (min 32 characters)
JWT_SECRET=your-very-long-secure-random-string-here
```

### AI Provider (Choose One)

**Ollama (Free, Self-Hosted):**
```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

**OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
```

**Anthropic Claude:**
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Email (Password Reset)

```env
EMAIL_ENABLED=true
RESEND_API_KEY=re_your-key
SMTP_FROM_EMAIL=noreply@yourdomain.com
```

### OAuth (Social Login)

```env
GOOGLE_CLIENT_ID=your-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GITHUB_CLIENT_ID=your-id
GITHUB_CLIENT_SECRET=your-secret
OAUTH_REDIRECT_BASE_URL=https://yourdomain.com
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Web | React, Tailwind CSS, CRA/craco |
| Backend | FastAPI (Python), PostgreSQL |
| AI | Ollama, OpenAI, Claude, Gemini |

---

## Contributing

1. Fork the repo
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push (`git push origin feature/amazing`)
5. Open a Pull Request

---

## License

MIT License - use it, modify it, share it!

---

<p align="center">
  Made with love for home cooks
</p>
