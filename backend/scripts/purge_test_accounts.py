#!/usr/bin/env python3
"""
Remove smoke/E2E and known dev test accounts from the database.

Usage (inside backend container, from /app):
  python scripts/purge_test_accounts.py --dry-run
  python scripts/purge_test_accounts.py --yes
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("purge_test_accounts")

# Reserved example.com addresses (E2E/smoke) plus known dev-only logins on production.
TEST_EMAIL_PREDICATE = (
    "email ILIKE '%@example.com' OR email IN ('devtest@laro.food')"
)


async def fetch_test_users():
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT id, email, household_id FROM users WHERE {TEST_EMAIL_PREDICATE} ORDER BY email"
        )
    return [(r["id"], r["email"], r["household_id"]) for r in rows]


async def purge_test_only_households(test_ids: set[str], *, dry_run: bool) -> None:
    import dependencies as deps
    from database.connection import get_db

    household_repository = deps.household_repository
    user_repository = deps.user_repository

    pool = await get_db()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, member_ids FROM households")

    for row in rows:
        member_ids = row["member_ids"]
        if isinstance(member_ids, str):
            member_ids = json.loads(member_ids)
        if not member_ids or not all(mid in test_ids for mid in member_ids):
            continue
        logger.info("Test-only household %s (%d members)", row["id"], len(member_ids))
        if dry_run:
            continue
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM household_invites WHERE household_id = $1", row["id"]
            )
        for mid in member_ids:
            await user_repository.update_user(mid, {"household_id": None})
        await household_repository.delete_household(row["id"])


async def sql_cleanup_user(conn, user_id: str) -> None:
    """Delete rows admin permanent-delete may not cover."""
    statements = [
        "DELETE FROM friend_requests WHERE from_user_id = $1 OR to_user_id = $1",
        "DELETE FROM pantry_items WHERE user_id = $1",
        "DELETE FROM cookbooks WHERE user_id = $1 AND household_id IS NULL",
        "DELETE FROM share_links WHERE user_id = $1",
        "DELETE FROM api_tokens WHERE user_id = $1",
        "DELETE FROM support_tickets WHERE user_id = $1",
        "DELETE FROM ai_chat_sessions WHERE user_id = $1",
        "DELETE FROM cook_sessions WHERE user_id = $1",
        "DELETE FROM notifications WHERE user_id = $1",
        "DELETE FROM ingredient_aliases WHERE user_id = $1",
        "DELETE FROM recipe_feedback WHERE user_id = $1",
        "DELETE FROM user_recipe_ratings WHERE user_id = $1",
        "DELETE FROM reward_ledger WHERE user_id = $1",
        "DELETE FROM household_invites WHERE inviter_id = $1",
    ]
    for sql in statements:
        try:
            await conn.execute(sql, user_id)
        except Exception as exc:
            if "does not exist" in str(exc).lower():
                continue
            raise


async def permanently_delete_user(user_id: str, email: str, *, dry_run: bool) -> None:
    import dependencies as deps
    from database.connection import get_db

    custom_prompts_repository = deps.custom_prompts_repository
    llm_settings_repository = deps.llm_settings_repository
    meal_plan_repository = deps.meal_plan_repository
    oauth_account_repository = deps.oauth_account_repository
    recipe_repository = deps.recipe_repository
    session_repository = deps.session_repository
    totp_secret_repository = deps.totp_secret_repository
    user_preferences_repository = deps.user_preferences_repository
    shopping_list_repository = deps.shopping_list_repository
    user_repository = deps.user_repository
    notification_repository = getattr(deps, "notification_repository", None)

    logger.info("%s user %s (%s)", "Would delete" if dry_run else "Deleting", email, user_id)
    if dry_run:
        return

    pool = await get_db()
    user_recipes = await recipe_repository.find_by_author(user_id)
    recipe_ids = [r["id"] for r in user_recipes]

    try:
        await meal_plan_repository.delete_by_user(user_id)
    except Exception as exc:
        logger.warning("meal_plans: %s", exc)

    try:
        if recipe_ids:
            await meal_plan_repository.delete_by_recipe_ids(recipe_ids)
    except Exception as exc:
        logger.warning("meal_plans by recipe: %s", exc)

    for recipe_id in recipe_ids:
        await recipe_repository.delete_recipe(recipe_id)

    try:
        await shopping_list_repository.delete_by_user(user_id)
    except Exception as exc:
        logger.warning("shopping_lists: %s", exc)

    await custom_prompts_repository.delete_by_user(user_id)
    await llm_settings_repository.delete_by_user(user_id)
    await session_repository.delete_by_user(user_id)
    try:
        await totp_secret_repository.delete_by_user(user_id)
    except Exception as exc:
        logger.warning("totp: %s", exc)

    try:
        await oauth_account_repository.delete_by_user(user_id)
    except Exception as exc:
        logger.warning("oauth: %s", exc)

    try:
        await user_preferences_repository.delete_by_user(user_id)
    except Exception as exc:
        logger.warning("preferences: %s", exc)

    if notification_repository:
        try:
            await notification_repository.delete_by_user(user_id)
        except Exception as exc:
            logger.warning("notifications repo: %s", exc)

    pool = await get_db()
    async with pool.acquire() as conn:
        await sql_cleanup_user(conn, user_id)

    await user_repository.delete_user(user_id)
    logger.info("Deleted %s", email)


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Purge @example.com test accounts")
    parser.add_argument("--dry-run", action="store_true", help="List accounts only")
    parser.add_argument("--yes", action="store_true", help="Perform deletion")
    args = parser.parse_args(argv)
    if args.dry_run and args.yes:
        parser.error("Use either --dry-run or --yes")
    if not args.dry_run and not args.yes:
        parser.error("Pass --dry-run or --yes")

    from database.connection import close_db, init_db

    await init_db()
    try:
        users = await fetch_test_users()
        if not users:
            logger.info("No test accounts found (%s)", TEST_EMAIL_PREDICATE)
            return 0

        logger.info("Found %d test account(s)", len(users))
        for _uid, email, _hh in users:
            logger.info("  - %s", email)

        test_ids = {uid for uid, _, _ in users}
        await purge_test_only_households(test_ids, dry_run=args.dry_run)

        failures = 0
        for uid, email, _ in users:
            try:
                await permanently_delete_user(uid, email, dry_run=args.dry_run)
            except Exception as exc:
                failures += 1
                logger.error("Failed to delete %s: %s", email, exc)
        if failures and not args.dry_run:
            logger.error("%d deletion(s) failed", failures)
            return 1

        if not args.dry_run:
            remaining = await fetch_test_users()
            if remaining:
                logger.error("%d account(s) still remain", len(remaining))
                return 1
            logger.info("All test accounts removed.")
        return 0
    finally:
        await close_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
