"""Recipe delete must clear FK dependents (fixes E-RD005 / ForeignKeyViolation)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database.repositories.recipe_repository import RecipeRepository


@pytest.mark.asyncio
async def test_delete_recipe_clears_share_and_related_rows_before_recipe():
    recipe_id = str(uuid.uuid4())
    executed = []

    conn = AsyncMock()

    async def capture_execute(sql, *args):
        executed.append((sql.strip().split()[0:3], sql, args))
        if sql.strip().upper().startswith("DELETE FROM RECIPES"):
            return "DELETE 1"
        return "DELETE 0"

    conn.execute = AsyncMock(side_effect=capture_execute)
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)

    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)

    repo = RecipeRepository()
    with patch.object(repo, "_get_db", AsyncMock(return_value=pool)):
        deleted = await repo.delete_recipe(recipe_id)

    assert deleted == 1
    sqls = [sql for _, sql, _ in executed]
    assert any("DELETE FROM recipe_shares" in s for s in sqls)
    assert any("DELETE FROM recipe_feedback" in s for s in sqls)
    assert any("DELETE FROM cook_sessions" in s for s in sqls)
    assert any("DELETE FROM recipe_versions" in s for s in sqls)
    assert any("DELETE FROM reviews" in s for s in sqls)
    assert any("DELETE FROM user_recipe_ratings" in s for s in sqls)
    assert any("DELETE FROM meal_plans" in s for s in sqls)
    assert any("google_health_nutrition_logs" in s for s in sqls)
    assert any("DELETE FROM recipes WHERE id" in s for s in sqls)
    # Recipe row deleted last
    assert sqls[-1].strip().startswith("DELETE FROM recipes")
    assert all(args == (recipe_id,) or recipe_id in args for _, _, args in executed)
