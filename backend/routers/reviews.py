"""
Reviews Router - Recipe ratings and reviews
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from dependencies import get_current_user, recipe_repository, review_repository
from utils.activity_logger import log_action
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/reviews", tags=["Reviews"])

# =============================================================================
# MODELS
# =============================================================================

class CreateReview(BaseModel):
    recipe_id: str
    rating: int  # 1-5 stars
    title: Optional[str] = None
    comment: Optional[str] = None
    would_make_again: Optional[bool] = None
    difficulty_rating: Optional[int] = None  # 1-5 (1=easy, 5=hard)
    tags: Optional[List[str]] = None  # ["kid-approved", "date-night", "too-salty"]

class UpdateReview(BaseModel):
    rating: Optional[int] = None
    title: Optional[str] = None
    comment: Optional[str] = None
    would_make_again: Optional[bool] = None
    difficulty_rating: Optional[int] = None
    tags: Optional[List[str]] = None

class ReviewReaction(BaseModel):
    reaction: str  # "helpful", "funny", "agree"

# =============================================================================
# PREDEFINED TAGS
# =============================================================================

REVIEW_TAGS = {
    "positive": [
        "kid-approved",
        "crowd-pleaser",
        "date-night-worthy",
        "meal-prep-friendly",
        "quick-and-easy",
        "impressive",
        "comfort-food",
        "healthy-feel",
        "budget-friendly",
        "leftovers-great",
    ],
    "tips": [
        "needs-more-salt",
        "reduce-sugar",
        "add-more-spice",
        "double-the-sauce",
        "longer-cook-time",
        "shorter-cook-time",
        "let-it-rest",
        "toast-the-spices",
    ],
    "occasions": [
        "weeknight-dinner",
        "weekend-project",
        "holiday-worthy",
        "potluck-perfect",
        "game-day",
        "brunch",
    ]
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def update_recipe_rating(recipe_id: str):
    """Update recipe's average rating based on all reviews"""
    reviews = await review_repository.find_by_recipe(recipe_id)

    if not reviews:
        return

    total_rating = sum(r["rating"] for r in reviews)
    count = len(reviews)
    avg_rating = total_rating / count

    would_make_again_count = sum(1 for r in reviews if r.get("would_make_again"))
    would_make_again_percent = round((would_make_again_count / count) * 100) if count > 0 else 0

    await recipe_repository.update_recipe(recipe_id, {
        "rating_average": round(avg_rating, 1),
        "rating_count": count,
        "would_make_again_percent": would_make_again_percent
    })

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/tags")
async def get_review_tags():
    """Get predefined review tags"""
    return {"tags": REVIEW_TAGS}

@router.post("")
async def create_review(
    data: CreateReview,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Create a review for a recipe"""
    # Validate rating
    if not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    if data.difficulty_rating and not 1 <= data.difficulty_rating <= 5:
        raise HTTPException(status_code=400, detail="Difficulty rating must be between 1 and 5")

    # Check recipe exists
    recipe = await recipe_repository.find_by_id(data.recipe_id)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Check if user already reviewed this recipe
    existing = await review_repository.find_by_user_and_recipe(user["id"], data.recipe_id)

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You've already reviewed this recipe. Edit your existing review instead."
        )

    review = {
        "id": str(uuid.uuid4()),
        "recipe_id": data.recipe_id,
        "user_id": user["id"],
        "user_name": user.get("name", "Anonymous"),
        "rating": data.rating,
        "title": data.title,
        "comment": data.comment,
        "would_make_again": data.would_make_again,
        "difficulty_rating": data.difficulty_rating,
        "tags": data.tags or [],
        "helpful_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await review_repository.create(review)

    # Log review creation
    await log_action(
        user, "review_created", request,
        target_type="review",
        target_id=review["id"],
        details={"recipe_id": data.recipe_id, "rating": data.rating}
    )

    # Update recipe's average rating
    await update_recipe_rating(data.recipe_id)

    return {"message": "Review created", "review": review}

@router.get("/recipe/{recipe_id}")
async def get_recipe_reviews(
    recipe_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all reviews for a recipe"""
    reviews = await review_repository.find_by_recipe(recipe_id)

    # Get recipe rating stats
    recipe = await recipe_repository.find_by_id(recipe_id)

    # Calculate rating distribution
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for review in reviews:
        rating = review.get("rating", 0)
        if rating in distribution:
            distribution[rating] += 1

    # Get common tags
    all_tags = []
    for review in reviews:
        tags = review.get("tags", [])
        if isinstance(tags, list):
            all_tags.extend(tags)

    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    common_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Check if current user has reviewed
    user_review = next((r for r in reviews if r["user_id"] == user["id"]), None)

    # Format rating summary
    rating_summary = None
    if recipe:
        rating_summary = {
            "average": recipe.get("rating_average"),
            "count": recipe.get("rating_count"),
            "would_make_again_percent": recipe.get("would_make_again_percent")
        }

    return {
        "recipe_id": recipe_id,
        "recipe_title": recipe.get("title") if recipe else None,
        "rating_summary": rating_summary,
        "rating_distribution": distribution,
        "common_tags": [{"tag": t[0], "count": t[1]} for t in common_tags],
        "reviews": reviews,
        "total_reviews": len(reviews),
        "user_has_reviewed": user_review is not None,
        "user_review": user_review
    }

@router.get("/user")
async def get_user_reviews(user: dict = Depends(get_current_user)):
    """Get all reviews by the current user"""
    reviews = await review_repository.find_many(
        {"user_id": user["id"]},
        order_by="created_at",
        order_dir="DESC",
        limit=100
    )

    # Add recipe titles
    for review in reviews:
        recipe = await recipe_repository.find_by_id(review["recipe_id"])
        if recipe:
            review["recipe_title"] = recipe.get("title")
            review["recipe_image"] = recipe.get("image_url")

    return {
        "reviews": reviews,
        "total": len(reviews)
    }

@router.get("/top-rated")
async def get_top_rated_recipes(
    limit: int = 10,
    user: dict = Depends(get_current_user)
):
    """Get top-rated recipes"""
    from database.connection import get_db, rows_to_dicts

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT id, title, rating_average, rating_count, image_url
            FROM recipes
            WHERE author_id = $1
            AND rating_count >= 1
            ORDER BY rating_average DESC
            LIMIT $2
        """
        rows = await conn.fetch(query, user["id"], limit)

    recipes = rows_to_dicts(rows)

    # Format rating info
    for r in recipes:
        r["rating"] = {
            "average": r.pop("rating_average", None),
            "count": r.pop("rating_count", None)
        }

    return {"recipes": recipes}

@router.get("/would-make-again")
async def get_would_make_again_recipes(user: dict = Depends(get_current_user)):
    """Get recipes with high 'would make again' percentage"""
    from database.connection import get_db, rows_to_dicts

    pool = await get_db()
    async with pool.acquire() as conn:
        query = """
            SELECT id, title, rating_average, rating_count, would_make_again_percent, image_url
            FROM recipes
            WHERE author_id = $1
            AND would_make_again_percent >= 80
            ORDER BY would_make_again_percent DESC
            LIMIT 20
        """
        rows = await conn.fetch(query, user["id"])

    recipes = rows_to_dicts(rows)

    # Format rating info
    for r in recipes:
        r["rating"] = {
            "average": r.pop("rating_average", None),
            "count": r.pop("rating_count", None),
            "would_make_again_percent": r.pop("would_make_again_percent", None)
        }

    return {"recipes": recipes}

@router.get("/{review_id}")
async def get_review(
    review_id: str,
    user: dict = Depends(get_current_user)
):
    """Get a specific review"""
    review = await review_repository.find_one({"id": review_id})

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    return review

@router.put("/{review_id}")
async def update_review(
    review_id: str,
    data: UpdateReview,
    user: dict = Depends(get_current_user)
):
    """Update a review"""
    review = await review_repository.find_one({"id": review_id})

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    if review["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="You can only edit your own reviews")

    # Validate ratings
    if data.rating and not 1 <= data.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    if data.difficulty_rating and not 1 <= data.difficulty_rating <= 5:
        raise HTTPException(status_code=400, detail="Difficulty rating must be between 1 and 5")

    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await review_repository.update_review(review_id, update_data)

    # Update recipe rating if rating changed
    if data.rating:
        await update_recipe_rating(review["recipe_id"])

    return {"message": "Review updated"}

@router.delete("/{review_id}")
async def delete_review(
    review_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Delete a review"""
    review = await review_repository.find_one({"id": review_id})

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Allow user to delete own review, or admin to delete any
    if review["user_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="You can only delete your own reviews")

    recipe_id = review["recipe_id"]
    await review_repository.delete_review(review_id)

    # Log review deletion
    await log_action(
        user, "review_deleted", request,
        target_type="review",
        target_id=review_id,
        details={"recipe_id": recipe_id}
    )

    # Update recipe rating
    await update_recipe_rating(recipe_id)

    return {"message": "Review deleted"}

@router.post("/{review_id}/helpful")
async def mark_review_helpful(
    review_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark a review as helpful"""
    review = await review_repository.find_one({"id": review_id})

    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # For simplicity, we'll just increment the count
    # A full implementation would track which users marked what as helpful
    from database.connection import get_db

    pool = await get_db()
    async with pool.acquire() as conn:
        # Check if already marked helpful (using a simple approach)
        # Note: In production, you'd use a separate review_reactions table
        current_count = review.get("helpful_count", 0)

        await conn.execute(
            "UPDATE reviews SET helpful_count = $1 WHERE id = $2",
            current_count + 1, review_id
        )

    return {"message": "Marked as helpful", "is_helpful": True}
