"""
PostgreSQL Database Connection Module
Provides async PostgreSQL connection management with asyncpg
"""
import asyncpg
import os
import logging
import time
from typing import Optional
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Import debug utilities
try:
    from utils.debug import Loggers, log_db_query, DebugContext
    _debug_available = True
except ImportError:
    _debug_available = False

# Global database connection pool
_pool: Optional[asyncpg.Pool] = None

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://mise:mise@localhost:5432/mise")

# SQL Schema
SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY,
    supabase_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    status VARCHAR(50) DEFAULT 'active',
    household_id VARCHAR(255),
    favorites TEXT DEFAULT '[]',
    allergies TEXT DEFAULT '[]',
    created_at TIMESTAMP NOT NULL,
    last_login TIMESTAMP,
    totp_enabled BOOLEAN DEFAULT FALSE,
    oauth_only BOOLEAN DEFAULT FALSE,
    force_password_change BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by VARCHAR(255),
    password_changed_at TIMESTAMP,
    friend_code VARCHAR(20) UNIQUE,
    referred_by VARCHAR(255),
    referral_trial_end TIMESTAMP,
    referral_count INTEGER DEFAULT 0,
    pending_referral_rewards TEXT DEFAULT '[]',
    subscription_status VARCHAR(50) DEFAULT 'free',
    subscription_expires TIMESTAMP,
    subscription_source VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS recipes (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    description TEXT DEFAULT '',
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL,
    prep_time INTEGER DEFAULT 0,
    cook_time INTEGER DEFAULT 0,
    servings INTEGER DEFAULT 4,
    category VARCHAR(100) DEFAULT 'Other',
    tags TEXT DEFAULT '[]',
    image_url TEXT DEFAULT '',
    author_id VARCHAR(255) NOT NULL,
    household_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (author_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS households (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    member_ids TEXT NOT NULL,
    join_code VARCHAR(100),
    join_code_expires TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS meal_plans (
    id VARCHAR(255) PRIMARY KEY,
    date VARCHAR(50) NOT NULL,
    meal_type VARCHAR(50) NOT NULL,
    recipe_id VARCHAR(255) NOT NULL,
    recipe_title VARCHAR(500) NOT NULL,
    notes TEXT DEFAULT '',
    household_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id)
);

CREATE TABLE IF NOT EXISTS shopping_lists (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    items TEXT NOT NULL,
    household_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    token VARCHAR(500) NOT NULL,
    user_agent TEXT,
    ip_address VARCHAR(100),
    created_at TIMESTAMP NOT NULL,
    last_active TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS totp_secrets (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    secret VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    backup_codes TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS oauth_accounts (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    provider_email VARCHAR(255),
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(provider, provider_id)
);

CREATE TABLE IF NOT EXISTS oauth_states (
    id VARCHAR(255) PRIMARY KEY,
    state VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id VARCHAR(255) PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    success BOOLEAN NOT NULL,
    ip_address VARCHAR(100),
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS system_settings (
    type VARCHAR(100) PRIMARY KEY,
    settings TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100),
    target_id VARCHAR(255),
    details TEXT,
    ip_address VARCHAR(100),
    timestamp TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_codes (
    id VARCHAR(255) PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    max_uses INTEGER DEFAULT 1,
    uses INTEGER DEFAULT 0,
    grants_admin BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS ip_allowlist (
    id VARCHAR(255) PRIMARY KEY,
    ip_pattern VARCHAR(100) NOT NULL,
    description TEXT,
    created_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS ip_blocklist (
    id VARCHAR(255) PRIMARY KEY,
    ip_pattern VARCHAR(100) NOT NULL,
    description TEXT,
    created_by VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS backups (
    id VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    size_bytes BIGINT,
    status VARCHAR(50) NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS backup_settings (
    type VARCHAR(100) PRIMARY KEY,
    auto_backup_enabled BOOLEAN DEFAULT FALSE,
    interval_hours INTEGER DEFAULT 24,
    max_backups_to_keep INTEGER DEFAULT 7,
    last_backup TIMESTAMP,
    next_scheduled TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_shares (
    id VARCHAR(255) PRIMARY KEY,
    share_code VARCHAR(100) UNIQUE NOT NULL,
    recipe_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    allow_print BOOLEAN DEFAULT TRUE,
    show_author BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS recipe_feedback (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    recipe_id VARCHAR(255) NOT NULL,
    feedback TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id),
    UNIQUE(user_id, recipe_id)
);

CREATE TABLE IF NOT EXISTS cook_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    recipe_id VARCHAR(255) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    feedback TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (recipe_id) REFERENCES recipes(id)
);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    subscription TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS notification_settings (
    user_id VARCHAR(255) PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    meal_reminders BOOLEAN DEFAULT TRUE,
    reminder_time INTEGER DEFAULT 30,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS llm_settings (
    user_id VARCHAR(255) PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,
    ollama_url VARCHAR(255) DEFAULT 'http://localhost:11434',
    ollama_model VARCHAR(100) DEFAULT 'llama3',
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS llm_cache (
    hash VARCHAR(255) PRIMARY KEY,
    response TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    provider VARCHAR(50),
    model VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS custom_prompts (
    user_id VARCHAR(255) PRIMARY KEY,
    recipe_extraction TEXT,
    meal_planning TEXT,
    fridge_search TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS recipe_versions (
    id VARCHAR(255) PRIMARY KEY,
    recipe_id VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    data TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id VARCHAR(255) PRIMARY KEY,
    recipe_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    rating INTEGER NOT NULL,
    content TEXT,
    tags TEXT DEFAULT '[]',
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP,
    FOREIGN KEY (recipe_id) REFERENCES recipes(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(255) PRIMARY KEY,
    -- Legacy fields
    dietary TEXT DEFAULT '[]',
    units VARCHAR(20) DEFAULT 'metric',
    language VARCHAR(10) DEFAULT 'en',
    -- General preferences
    theme VARCHAR(20) DEFAULT 'system',
    "defaultServings" INTEGER DEFAULT 4,
    "measurementUnit" VARCHAR(20) DEFAULT 'metric',
    "dietaryRestrictions" TEXT DEFAULT '[]',
    "showNutrition" BOOLEAN DEFAULT TRUE,
    "compactView" BOOLEAN DEFAULT FALSE,
    "weekStartsOn" VARCHAR(20) DEFAULT 'monday',
    "mealPlanNotifications" BOOLEAN DEFAULT TRUE,
    "shoppingListAutoSort" BOOLEAN DEFAULT TRUE,
    "defaultCookingTime" INTEGER DEFAULT 30,
    -- Accessibility: Reading Support
    "dyslexicFont" BOOLEAN DEFAULT FALSE,
    "textSpacing" VARCHAR(20) DEFAULT 'normal',
    "lineHeight" VARCHAR(20) DEFAULT 'normal',
    "readingRuler" BOOLEAN DEFAULT FALSE,
    -- Accessibility: Focus & Attention (ADHD)
    "focusMode" BOOLEAN DEFAULT FALSE,
    "simplifiedMode" BOOLEAN DEFAULT FALSE,
    "highlightCurrentStep" BOOLEAN DEFAULT TRUE,
    "showProgressIndicators" BOOLEAN DEFAULT TRUE,
    -- Accessibility: Visual
    "iconLabels" BOOLEAN DEFAULT FALSE,
    "contrastLevel" VARCHAR(20) DEFAULT 'normal',
    "animationLevel" VARCHAR(20) DEFAULT 'normal',
    -- Accessibility: Interaction
    "confirmActions" BOOLEAN DEFAULT TRUE,
    -- Accessibility: Sensory
    "soundEffects" BOOLEAN DEFAULT FALSE,
    "hapticFeedback" BOOLEAN DEFAULT FALSE,
    "timerNotifications" VARCHAR(20) DEFAULT 'both',
    -- Metadata
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS voice_settings (
    user_id VARCHAR(255) PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    auto_read_steps BOOLEAN DEFAULT TRUE,
    voice_language VARCHAR(10) DEFAULT 'en-US',
    speech_rate DOUBLE PRECISION DEFAULT 1.0,
    voice_commands_enabled BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS custom_ingredients (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    calories DOUBLE PRECISION,
    protein DOUBLE PRECISION,
    carbs DOUBLE PRECISION,
    fat DOUBLE PRECISION,
    fiber DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS custom_roles (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    permissions TEXT DEFAULT '[]',
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    device_token VARCHAR(500) UNIQUE NOT NULL,
    device_name VARCHAR(255),
    ip_address VARCHAR(100),
    created_at TIMESTAMP NOT NULL,
    last_used TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ingredient_costs (
    id VARCHAR(255) PRIMARY KEY,
    household_id VARCHAR(255) NOT NULL,
    ingredient_name VARCHAR(255) NOT NULL,
    cost DOUBLE PRECISION NOT NULL,
    unit VARCHAR(50),
    store VARCHAR(255),
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(household_id, ingredient_name)
);

-- API Tokens for integrations (e.g., Home Assistant)
CREATE TABLE IF NOT EXISTS api_tokens (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    scopes TEXT DEFAULT '["read", "write"]',
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Cookbooks for organizing recipes from physical books
CREATE TABLE IF NOT EXISTS cookbooks (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    household_id VARCHAR(255),
    isbn VARCHAR(20),
    title VARCHAR(500) NOT NULL,
    author VARCHAR(255),
    cover_image_url TEXT,
    publisher VARCHAR(255),
    year INTEGER,
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Pantry items for kitchen inventory tracking
CREATE TABLE IF NOT EXISTS pantry_items (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    household_id VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    quantity VARCHAR(50),
    unit VARCHAR(50),
    category VARCHAR(100) DEFAULT 'pantry',
    expiry_date DATE,
    notes TEXT,
    is_staple BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Extended notification settings for mobile push notifications
CREATE TABLE IF NOT EXISTS mobile_notification_settings (
    user_id VARCHAR(255) PRIMARY KEY,
    fcm_token TEXT,
    apns_token TEXT,
    meal_reminders BOOLEAN DEFAULT TRUE,
    expiry_alerts BOOLEAN DEFAULT TRUE,
    shared_list_updates BOOLEAN DEFAULT TRUE,
    import_complete BOOLEAN DEFAULT TRUE,
    reminder_time VARCHAR(10) DEFAULT '17:00',
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Remote instances linked to cloud accounts (like Home Assistant Cloud)
CREATE TABLE IF NOT EXISTS remote_instances (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    instance_name VARCHAR(255) NOT NULL,
    instance_id VARCHAR(255) UNIQUE NOT NULL,
    linking_code VARCHAR(100) UNIQUE,
    linking_code_expires TIMESTAMP,
    is_connected BOOLEAN DEFAULT FALSE,
    last_connected_at TIMESTAMP,
    local_url TEXT,
    webhook_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Cloud relay connections for remote access
CREATE TABLE IF NOT EXISTS relay_connections (
    id VARCHAR(255) PRIMARY KEY,
    instance_id VARCHAR(255) NOT NULL,
    connection_token VARCHAR(500) UNIQUE NOT NULL,
    connected_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP NOT NULL,
    client_ip VARCHAR(100),
    FOREIGN KEY (instance_id) REFERENCES remote_instances(instance_id)
);
"""

# Indices for performance
INDICES = """
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_household ON users(household_id);
CREATE INDEX IF NOT EXISTS idx_recipes_author ON recipes(author_id);
CREATE INDEX IF NOT EXISTS idx_recipes_household ON recipes(household_id);
CREATE INDEX IF NOT EXISTS idx_meal_plans_household ON meal_plans(household_id);
CREATE INDEX IF NOT EXISTS idx_meal_plans_date ON meal_plans(date);
CREATE INDEX IF NOT EXISTS idx_shopping_lists_household ON shopping_lists(household_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email);
CREATE INDEX IF NOT EXISTS idx_login_attempts_timestamp ON login_attempts(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_recipe_feedback_user ON recipe_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_recipe_feedback_recipe ON recipe_feedback(recipe_id);
CREATE INDEX IF NOT EXISTS idx_cook_sessions_user ON cook_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_recipe_shares_recipe ON recipe_shares(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_shares_code ON recipe_shares(share_code);
CREATE INDEX IF NOT EXISTS idx_recipe_shares_user ON recipe_shares(user_id);
CREATE INDEX IF NOT EXISTS idx_recipe_versions_recipe ON recipe_versions(recipe_id);
CREATE INDEX IF NOT EXISTS idx_reviews_recipe ON reviews(recipe_id);
CREATE INDEX IF NOT EXISTS idx_oauth_states_state ON oauth_states(state);
CREATE INDEX IF NOT EXISTS idx_custom_ingredients_user ON custom_ingredients(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_cookbooks_user ON cookbooks(user_id);
CREATE INDEX IF NOT EXISTS idx_cookbooks_household ON cookbooks(household_id);
CREATE INDEX IF NOT EXISTS idx_cookbooks_isbn ON cookbooks(isbn);
CREATE INDEX IF NOT EXISTS idx_pantry_items_user ON pantry_items(user_id);
CREATE INDEX IF NOT EXISTS idx_pantry_items_household ON pantry_items(household_id);
CREATE INDEX IF NOT EXISTS idx_pantry_items_category ON pantry_items(category);
CREATE INDEX IF NOT EXISTS idx_pantry_items_expiry ON pantry_items(expiry_date);
CREATE INDEX IF NOT EXISTS idx_remote_instances_user ON remote_instances(user_id);
CREATE INDEX IF NOT EXISTS idx_remote_instances_instance_id ON remote_instances(instance_id);
CREATE INDEX IF NOT EXISTS idx_remote_instances_linking_code ON remote_instances(linking_code);
CREATE INDEX IF NOT EXISTS idx_relay_connections_instance ON relay_connections(instance_id);
CREATE INDEX IF NOT EXISTS idx_relay_connections_token ON relay_connections(connection_token);
"""

# Database migrations for schema updates
MIGRATIONS = """
-- Add missing columns to user_preferences table (for existing databases)
DO $$
BEGIN
    -- General preferences
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='defaultServings') THEN
        ALTER TABLE user_preferences ADD COLUMN "defaultServings" INTEGER DEFAULT 4;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='measurementUnit') THEN
        ALTER TABLE user_preferences ADD COLUMN "measurementUnit" VARCHAR(20) DEFAULT 'metric';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='dietaryRestrictions') THEN
        ALTER TABLE user_preferences ADD COLUMN "dietaryRestrictions" TEXT DEFAULT '[]';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='showNutrition') THEN
        ALTER TABLE user_preferences ADD COLUMN "showNutrition" BOOLEAN DEFAULT TRUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='compactView') THEN
        ALTER TABLE user_preferences ADD COLUMN "compactView" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='weekStartsOn') THEN
        ALTER TABLE user_preferences ADD COLUMN "weekStartsOn" VARCHAR(20) DEFAULT 'monday';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='mealPlanNotifications') THEN
        ALTER TABLE user_preferences ADD COLUMN "mealPlanNotifications" BOOLEAN DEFAULT TRUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='shoppingListAutoSort') THEN
        ALTER TABLE user_preferences ADD COLUMN "shoppingListAutoSort" BOOLEAN DEFAULT TRUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='defaultCookingTime') THEN
        ALTER TABLE user_preferences ADD COLUMN "defaultCookingTime" INTEGER DEFAULT 30;
    END IF;

    -- Accessibility: Reading Support
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='dyslexicFont') THEN
        ALTER TABLE user_preferences ADD COLUMN "dyslexicFont" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='textSpacing') THEN
        ALTER TABLE user_preferences ADD COLUMN "textSpacing" VARCHAR(20) DEFAULT 'normal';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='lineHeight') THEN
        ALTER TABLE user_preferences ADD COLUMN "lineHeight" VARCHAR(20) DEFAULT 'normal';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='readingRuler') THEN
        ALTER TABLE user_preferences ADD COLUMN "readingRuler" BOOLEAN DEFAULT FALSE;
    END IF;

    -- Accessibility: Focus & Attention (ADHD)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='focusMode') THEN
        ALTER TABLE user_preferences ADD COLUMN "focusMode" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='simplifiedMode') THEN
        ALTER TABLE user_preferences ADD COLUMN "simplifiedMode" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='highlightCurrentStep') THEN
        ALTER TABLE user_preferences ADD COLUMN "highlightCurrentStep" BOOLEAN DEFAULT TRUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='showProgressIndicators') THEN
        ALTER TABLE user_preferences ADD COLUMN "showProgressIndicators" BOOLEAN DEFAULT TRUE;
    END IF;

    -- Accessibility: Visual
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='iconLabels') THEN
        ALTER TABLE user_preferences ADD COLUMN "iconLabels" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='contrastLevel') THEN
        ALTER TABLE user_preferences ADD COLUMN "contrastLevel" VARCHAR(20) DEFAULT 'normal';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='animationLevel') THEN
        ALTER TABLE user_preferences ADD COLUMN "animationLevel" VARCHAR(20) DEFAULT 'normal';
    END IF;

    -- Accessibility: Interaction
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='confirmActions') THEN
        ALTER TABLE user_preferences ADD COLUMN "confirmActions" BOOLEAN DEFAULT TRUE;
    END IF;

    -- Accessibility: Sensory
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='soundEffects') THEN
        ALTER TABLE user_preferences ADD COLUMN "soundEffects" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='hapticFeedback') THEN
        ALTER TABLE user_preferences ADD COLUMN "hapticFeedback" BOOLEAN DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='timerNotifications') THEN
        ALTER TABLE user_preferences ADD COLUMN "timerNotifications" VARCHAR(20) DEFAULT 'both';
    END IF;

    -- Metadata
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='user_preferences' AND column_name='updated_at') THEN
        ALTER TABLE user_preferences ADD COLUMN updated_at TIMESTAMP;
    END IF;

    -- Add cookbook support columns to recipes table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recipes' AND column_name='source_type') THEN
        ALTER TABLE recipes ADD COLUMN source_type VARCHAR(50) DEFAULT 'manual';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recipes' AND column_name='source_url') THEN
        ALTER TABLE recipes ADD COLUMN source_url TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recipes' AND column_name='cookbook_id') THEN
        ALTER TABLE recipes ADD COLUMN cookbook_id VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='recipes' AND column_name='cookbook_page') THEN
        ALTER TABLE recipes ADD COLUMN cookbook_page INTEGER;
    END IF;

    -- Add Supabase auth column to users table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='supabase_id') THEN
        ALTER TABLE users ADD COLUMN supabase_id VARCHAR(255) UNIQUE;
    END IF;

    -- Add referral system columns to users table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='friend_code') THEN
        ALTER TABLE users ADD COLUMN friend_code VARCHAR(20) UNIQUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='referred_by') THEN
        ALTER TABLE users ADD COLUMN referred_by VARCHAR(255);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='referral_trial_end') THEN
        ALTER TABLE users ADD COLUMN referral_trial_end TIMESTAMP;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='referral_count') THEN
        ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='pending_referral_rewards') THEN
        ALTER TABLE users ADD COLUMN pending_referral_rewards TEXT DEFAULT '[]';
    END IF;

    -- Add updated_at column to llm_settings table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='llm_settings' AND column_name='updated_at') THEN
        ALTER TABLE llm_settings ADD COLUMN updated_at TIMESTAMP;
    END IF;

    -- Add subscription fields to users table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='subscription_status') THEN
        ALTER TABLE users ADD COLUMN subscription_status VARCHAR(50) DEFAULT 'free';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='subscription_expires') THEN
        ALTER TABLE users ADD COLUMN subscription_expires TIMESTAMP;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='subscription_source') THEN
        ALTER TABLE users ADD COLUMN subscription_source VARCHAR(50);
    END IF;
END $$;
"""


async def init_db() -> asyncpg.Pool:
    """Initialize the database connection pool and create tables"""
    global _pool

    start_time = time.time()
    logger.info(f"Initializing PostgreSQL connection pool")
    if _debug_available:
        Loggers.db.info("Starting database initialization", database_url=DATABASE_URL.split("@")[-1])  # Log without credentials

    # Create connection pool
    try:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        pool_time = (time.time() - start_time) * 1000
        if _debug_available:
            Loggers.db.debug(f"Connection pool created", duration_ms=f"{pool_time:.2f}", min_size=5, max_size=20)
    except Exception as e:
        if _debug_available:
            Loggers.db.error(f"Failed to create connection pool: {e}", exc_info=True)
        raise

    # Create schema
    schema_start = time.time()
    async with _pool.acquire() as conn:
        if _debug_available:
            Loggers.db.debug("Executing schema creation...")

        # Execute schema creation
        await conn.execute(SCHEMA)
        schema_time = (time.time() - schema_start) * 1000
        if _debug_available:
            Loggers.db.debug("Schema created", duration_ms=f"{schema_time:.2f}")

        # Create indices
        indices_start = time.time()
        await conn.execute(INDICES)
        indices_time = (time.time() - indices_start) * 1000
        if _debug_available:
            Loggers.db.debug("Indices created", duration_ms=f"{indices_time:.2f}")

        # Run migrations for existing databases
        migrations_start = time.time()
        await conn.execute(MIGRATIONS)
        migrations_time = (time.time() - migrations_start) * 1000
        if _debug_available:
            Loggers.db.debug("Migrations executed", duration_ms=f"{migrations_time:.2f}")

    total_time = (time.time() - start_time) * 1000
    logger.info("Database initialized successfully")
    if _debug_available:
        Loggers.db.info("Database initialization complete", total_duration_ms=f"{total_time:.2f}")

    return _pool


async def get_db() -> asyncpg.Pool:
    """Get the database connection pool"""
    global _pool
    if _pool is None:
        _pool = await init_db()
    return _pool


async def close_db():
    """Close the database connection pool"""
    global _pool
    if _pool is not None:
        if _debug_available:
            Loggers.db.info("Closing database connection pool...")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed")
        if _debug_available:
            Loggers.db.info("Database connection pool closed successfully")


@asynccontextmanager
async def get_db_context():
    """Context manager for database connection"""
    start_time = time.time()
    pool = await get_db()
    async with pool.acquire() as conn:
        acquire_time = (time.time() - start_time) * 1000
        if _debug_available and acquire_time > 100:
            Loggers.db.warning("Slow connection acquire", duration_ms=f"{acquire_time:.2f}")
        yield conn


def dict_from_row(row) -> dict:
    """Convert a Record object to a dictionary"""
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: list) -> list:
    """Convert a list of Record objects to dictionaries"""
    return [dict_from_row(row) for row in rows]
