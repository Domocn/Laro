#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL
Run this script after setting up PostgreSQL to migrate existing data
"""
import asyncio
import aiosqlite
import asyncpg
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
SQLITE_PATH = os.getenv("SQLITE_DB_PATH", "/app/data/mise.db")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://mise:mise@localhost:5432/mise")

# Tables to migrate (in dependency order - parent tables first)
TABLES = [
    "users",
    "households",
    "recipes",
    "meal_plans",
    "shopping_lists",
    "sessions",
    "totp_secrets",
    "oauth_accounts",
    "oauth_states",
    "login_attempts",
    "system_settings",
    "audit_logs",
    "invite_codes",
    "ip_allowlist",
    "ip_blocklist",
    "backups",
    "backup_settings",
    "recipe_shares",
    "recipe_feedback",
    "cook_sessions",
    "push_subscriptions",
    "notification_settings",
    "llm_settings",
    "llm_cache",
    "custom_prompts",
    "recipe_versions",
    "reviews",
    "user_preferences",
    "voice_settings",
    "custom_ingredients",
    "custom_roles",
    "trusted_devices",
    "ingredient_costs"
]


def convert_value(value):
    """Convert SQLite value to PostgreSQL compatible value"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        # SQLite booleans are stored as 0/1
        # We'll handle this per-column basis
        return value
    if isinstance(value, float):
        return value
    return value


def convert_boolean_fields(table_name, row_dict):
    """Convert integer boolean fields (0/1) to actual booleans"""
    boolean_fields = {
        "users": ["totp_enabled", "oauth_only", "force_password_change"],
        "login_attempts": ["success"],
        "invite_codes": ["grants_admin"],
        "backups": [],
        "backup_settings": ["auto_backup_enabled"],
        "recipe_shares": ["allow_print", "show_author", "is_active"],
        "totp_secrets": ["verified"],
        "notification_settings": ["enabled", "meal_reminders"],
        "voice_settings": ["enabled", "auto_read_steps", "voice_commands_enabled"],
    }

    if table_name in boolean_fields:
        for field in boolean_fields[table_name]:
            if field in row_dict and row_dict[field] is not None:
                row_dict[field] = bool(row_dict[field])

    return row_dict


def convert_timestamp_fields(table_name, row_dict):
    """Convert TEXT timestamps to TIMESTAMP objects"""
    timestamp_fields = {
        "users": ["created_at", "last_login", "deleted_at", "password_changed_at"],
        "recipes": ["created_at", "updated_at"],
        "households": ["created_at", "join_code_expires"],
        "meal_plans": ["created_at"],
        "shopping_lists": ["created_at", "updated_at"],
        "sessions": ["created_at", "last_active"],
        "totp_secrets": ["created_at"],
        "oauth_accounts": ["created_at"],
        "oauth_states": ["created_at"],
        "login_attempts": ["timestamp"],
        "audit_logs": ["timestamp"],
        "invite_codes": ["expires_at", "created_at"],
        "ip_allowlist": ["created_at"],
        "ip_blocklist": ["created_at"],
        "backups": ["created_at"],
        "backup_settings": ["last_backup", "next_scheduled"],
        "recipe_shares": ["created_at", "expires_at"],
        "recipe_feedback": ["updated_at"],
        "cook_sessions": ["started_at", "completed_at"],
        "push_subscriptions": ["created_at"],
        "recipe_versions": ["created_at"],
        "reviews": ["created_at", "updated_at"],
        "voice_settings": ["updated_at"],
        "custom_ingredients": ["created_at"],
        "custom_roles": ["created_at"],
        "trusted_devices": ["created_at", "last_used"],
        "ingredient_costs": ["updated_at"],
    }

    if table_name in timestamp_fields:
        for field in timestamp_fields[table_name]:
            if field in row_dict and row_dict[field] is not None:
                # SQLite stores as ISO format strings
                try:
                    # Try to parse ISO format
                    row_dict[field] = datetime.fromisoformat(row_dict[field].replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    # If parsing fails, set to None
                    row_dict[field] = None

    return row_dict


async def migrate_table(sqlite_conn, pg_conn, table_name):
    """Migrate a single table from SQLite to PostgreSQL"""
    logger.info(f"Migrating table: {table_name}")

    try:
        # Get all rows from SQLite
        async with sqlite_conn.execute(f"SELECT * FROM {table_name}") as cursor:
            sqlite_conn.row_factory = aiosqlite.Row
            rows = await cursor.fetchall()

        if not rows:
            logger.info(f"  ✓ Table {table_name} is empty, skipping")
            return

        # Get column names from first row
        columns = list(rows[0].keys())

        migrated = 0
        for row in rows:
            row_dict = dict(row)

            # Convert boolean fields
            row_dict = convert_boolean_fields(table_name, row_dict)

            # Convert timestamp fields
            row_dict = convert_timestamp_fields(table_name, row_dict)

            # Build INSERT query
            placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
            column_names = ", ".join(columns)
            query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

            # Extract values in column order
            values = [row_dict[col] for col in columns]

            try:
                await pg_conn.execute(query, *values)
                migrated += 1
            except Exception as e:
                logger.warning(f"  ⚠ Failed to insert row in {table_name}: {e}")
                logger.debug(f"    Row data: {row_dict}")

        logger.info(f"  ✓ Migrated {migrated}/{len(rows)} rows from {table_name}")

    except Exception as e:
        logger.error(f"  ✗ Failed to migrate table {table_name}: {e}")
        raise


async def main():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("SQLite to PostgreSQL Migration")
    logger.info("=" * 60)

    # Check if SQLite database exists
    if not os.path.exists(SQLITE_PATH):
        logger.error(f"SQLite database not found at: {SQLITE_PATH}")
        sys.exit(1)

    logger.info(f"Source: {SQLITE_PATH}")
    logger.info(f"Target: {POSTGRES_URL}")
    logger.info("")

    # Connect to both databases
    logger.info("Connecting to databases...")
    sqlite_conn = await aiosqlite.connect(SQLITE_PATH)
    pg_conn = await asyncpg.connect(POSTGRES_URL)

    try:
        # Migrate each table
        total_tables = len(TABLES)
        for i, table in enumerate(TABLES, 1):
            logger.info(f"[{i}/{total_tables}] Processing {table}...")
            await migrate_table(sqlite_conn, pg_conn, table)

        logger.info("")
        logger.info("=" * 60)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error(f"✗ Migration failed: {e}")
        logger.error("=" * 60)
        sys.exit(1)

    finally:
        await sqlite_conn.close()
        await pg_conn.close()


if __name__ == "__main__":
    asyncio.run(main())
