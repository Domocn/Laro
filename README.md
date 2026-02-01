<p align="center">
  <img src="android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.webp" alt="Laro Logo" width="120">
</p>

<h1 align="center">Laro</h1>

<p align="center">
  <strong>Your Recipe Companion</strong><br>
  <em>Self-hosted recipe manager for home cooks</em>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-features">Features</a> •
  <a href="#-android-app">Android App</a> •
  <a href="#%EF%B8%8F-configuration">Configuration</a>
</p>

---

## What is Laro?

Laro is a **self-hosted recipe manager** for home cooks. Import recipes from any website with AI, track your pantry, plan weekly meals, generate shopping lists, and cook with step-by-step guidance.

**Your data stays on your server.** No cloud required.

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/Laro.git
cd Laro

# Copy and configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# Start services
docker-compose up -d

# Open http://localhost:3000
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
# Edit .env with your database and settings

# Run
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend (Node 18+):**
```bash
npm install
npm run dev
# Open http://localhost:5173
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

Build the Android app to connect to your self-hosted server.

### Setup

1. Copy config files:
```bash
cd android
cp local.properties.example local.properties
cp app/google-services.json.example app/google-services.json
```

2. Edit `local.properties`:
```properties
sdk.dir=/path/to/your/android/sdk
MISE_API_BASE_URL=http://YOUR_SERVER_IP:8000/api/v1
```

3. Set up Firebase (for push notifications):
   - Create project at [Firebase Console](https://console.firebase.google.com)
   - Download `google-services.json` to `android/app/`

4. Build:
```bash
./gradlew assembleDebug
# APK at: app/build/outputs/apk/debug/app-debug.apk
```

### Connecting to Your Server

The app connects to your backend via the API URL in `local.properties`:

- **Same network:** `http://192.168.1.100:8000/api/v1`
- **Over internet:** `https://laro.yourdomain.com/api/v1`
- **Emulator to localhost:** `http://10.0.2.2:8000/api/v1`

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

## Docker Compose

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://laro:password@db:5432/laro
      - JWT_SECRET=your-secure-secret
    depends_on:
      - db

  frontend:
    build: .
    ports:
      - "3000:80"
    depends_on:
      - backend

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=laro
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=laro
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Android | Kotlin, Jetpack Compose, Hilt, Room |
| Web | React, Tailwind CSS, Vite |
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
