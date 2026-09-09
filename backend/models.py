from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Any, List, Optional, Union
from datetime import datetime
import re

_BLOCKED_NAMES = [
    "test", "testing", "asdf", "qwerty", "aaa", "bbb", "abc",
    "fake", "none", "null", "undefined", "admin", "user",
    "name", "firstname", "lastname", "first", "last",
    "no name", "noname", "n/a", "na", "xxx", "zzz",
]
_KEYBOARD_PATTERNS = [
    "qwer", "wert", "erty", "asdf", "sdfg", "dfgh", "zxcv", "xcvb",
    "1234", "2345", "3456", "abcd", "bcde", "cdef",
]

def _validate_human_name(v: str) -> str:
    name = v.strip()
    if len(name) < 2:
        raise ValueError("Name must be at least 2 characters")
    if len(name) > 50:
        raise ValueError("Name must be under 50 characters")
    if not re.search(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF\u0600-\u06FF\u4E00-\u9FFF\uAC00-\uD7AF]", name):
        raise ValueError("Name must contain at least one letter")
    if re.fullmatch(r"[\d\s]+", name):
        raise ValueError("Please enter a real name")
    if re.fullmatch(r"(.)\1+", name):
        raise ValueError("Please enter a real name")
    if "@" in name:
        raise ValueError("Please enter your name, not your email address")
    if name.lower() in _BLOCKED_NAMES:
        raise ValueError("Please enter your real name")
    name_lower = name.lower()
    for pattern in _KEYBOARD_PATTERNS:
        if pattern in name_lower:
            raise ValueError("Please enter your real name")
    return name


# Auth Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_human_name(v)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    allergies: Optional[List[str]] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    household_id: Optional[str] = None
    allergies: Optional[List[str]] = []
    created_at: str

    @field_validator('created_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

# Household Models
class HouseholdCreate(BaseModel):
    name: str

class HouseholdInvite(BaseModel):
    email: EmailStr

class HouseholdResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    member_ids: List[str]
    created_at: str
    join_code: Optional[str] = None
    join_code_expires: Optional[str] = None

    @field_validator('created_at', 'join_code_expires', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

class JoinHouseholdRequest(BaseModel):
    join_code: str

# Recipe Models
class Ingredient(BaseModel):
    name: str = ""
    amount: str = ""
    unit: Optional[str] = ""

    @field_validator("name", "amount", "unit", mode="before")
    @classmethod
    def coerce_null_strings(cls, v):
        # PDF / AI imports sometimes store amount/unit as JSON null.
        # Without this, GET /recipes 500s on the whole list (E-RL).
        return "" if v is None else v

class NutritionInfo(BaseModel):
    calories: Optional[int] = None
    protein: Optional[int] = None
    carbs: Optional[int] = None
    fat: Optional[int] = None
    fiber: Optional[int] = None
    sugar: Optional[int] = None
    sodium: Optional[int] = None
    # Set when missing macros were filled from the ingredient food DB
    nutrition_estimated: Optional[bool] = None
    nutrition_source: Optional[str] = None  # recipe | estimated | mixed | none

class RecipeCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    ingredients: List[Ingredient]
    instructions: List[str]
    prep_time: Optional[int] = 0
    cook_time: Optional[int] = 0
    servings: Optional[int] = 4
    category: Optional[str] = "Other"
    tags: Optional[List[str]] = []
    image_url: Optional[str] = ""
    dietary_tags: Optional[List[str]] = []
    difficulty: Optional[str] = None
    nutrition: Optional[NutritionInfo] = None
    cookbook_id: Optional[str] = None
    cookbook_page: Optional[int] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_author: Optional[str] = None

class RecipeResponse(BaseModel):
    id: str
    title: str
    description: str
    ingredients: List[Ingredient]
    instructions: List[str]
    prep_time: int
    cook_time: int
    servings: int
    category: str
    tags: List[str]
    image_url: str
    author_id: str
    household_id: Optional[str]
    created_at: str
    updated_at: str
    is_favorite: Optional[bool] = False
    dietary_tags: Optional[List[str]] = []
    difficulty: Optional[str] = None
    nutrition: Optional[NutritionInfo] = None
    user_rating: Optional[int] = None
    personal_notes: Optional[str] = None
    last_cooked_at: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None
    source_author: Optional[str] = None

    @field_validator('created_at', 'updated_at', 'last_cooked_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

# User Recipe Rating Models
class UserRatingCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    personal_notes: Optional[str] = ""

class UserRatingResponse(BaseModel):
    id: str
    user_id: str
    recipe_id: str
    rating: int
    personal_notes: str
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

class ShareRecipeRequest(BaseModel):
    recipe_id: str
    expires_days: Optional[int] = 30

# Meal Plan Models
class MealPlanCreate(BaseModel):
    date: str
    meal_type: str  # breakfast, lunch, dinner, snack
    recipe_id: Optional[str] = None  # required when entry_type=recipe
    recipe_title: Optional[str] = None  # required for note/leftover entries
    notes: Optional[str] = ""
    adult_boost: Optional[str] = ""  # short “For adults: …” upgrade tip
    entry_type: Optional[str] = "recipe"  # recipe | note | leftover

class MealPlanUpdate(BaseModel):
    date: Optional[str] = None
    meal_type: Optional[str] = None
    recipe_id: Optional[str] = None
    recipe_title: Optional[str] = None
    notes: Optional[str] = None
    adult_boost: Optional[str] = None
    entry_type: Optional[str] = None  # recipe | note | leftover

class MealPlanResponse(BaseModel):
    id: str
    date: str
    meal_type: str
    recipe_id: Optional[str] = None
    recipe_title: str
    notes: str
    adult_boost: Optional[str] = ""
    entry_type: Optional[str] = "recipe"
    household_id: str
    created_at: str

    @field_validator('created_at', 'date', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

class AutoMealPlanRequest(BaseModel):
    days: int = 7
    preferences: Optional[str] = ""  # e.g., "vegetarian", "low-carb", "quick meals"
    exclude_recipes: Optional[List[str]] = []
    # YYYY-MM-DD for day 0 (usually the meal planner's visible week start)
    start_date: Optional[str] = None
    # When true, create meal-plan rows for the week (clients just refresh).
    # Default false so older clients that apply themselves are not double-written.
    apply: bool = False
    # Clear existing meal-plan rows in the window before applying
    replace_week: bool = True

class ImportMealPlanRequest(BaseModel):
    """Import a printable weekly meal plan (PDF text or pasted plan)."""
    text: Optional[str] = None
    # YYYY-MM-DD for day 0 of the schedule (usually week start / Monday)
    start_date: Optional[str] = None
    # When true, create recipes + meal-plan rows. When false, preview only.
    apply: bool = True
    # Clear existing meal-plan rows in the 7-day window before applying
    replace_week: bool = True
    # Also create a shopping list from the document's shopping section (if present)
    create_shopping_list: bool = False
    # When true, prepend "From: <plan title>. <daily targets>" onto each recipe description
    include_source_note: bool = False

class MealPackProductInput(BaseModel):
    """User-confirmed meal pack (after online fetch or manual macros)."""
    title: str
    description: Optional[str] = ""
    kind: Optional[str] = "meal"
    meal_type: Optional[str] = None
    servings: Optional[int] = 1
    ingredients: Optional[List[dict]] = None
    instructions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    image_url: Optional[str] = ""
    calories: Optional[int] = None
    protein: Optional[int] = None
    carbs: Optional[int] = None
    fat: Optional[int] = None
    fiber: Optional[int] = None
    sugar: Optional[int] = None
    sodium: Optional[int] = None

class ImportMealPlanUrlRequest(BaseModel):
    """
    Import meals from a public URL and/or confirmed product macros.

    Designed for prepared-meal product pages (Huel shakes / RTD / pouches, etc.).
    Also accepts printable weekly meal-plan article URLs when the page is already
    structured like Laro's PDF importer.

    Flow for packs:
      1) POST with url + apply=false → preview products (macros filled from page when found)
      2) If needs_macros, user enters calories/protein/carbs/fat
      3) POST with apply=true + products=[...] (url optional) to save
    """
    url: Optional[str] = None
    start_date: Optional[str] = None
    apply: bool = True
    replace_week: bool = True
    create_shopping_list: bool = False
    # When true (default), schedule imported packs onto the week.
    # When false, only create recipes in your library.
    schedule: bool = True
    # When true, prepend "From: <plan title>. <daily targets>" onto each recipe description
    include_source_note: bool = False
    # Confirmed products with macros (skips re-fetch when provided on apply)
    products: Optional[List[MealPackProductInput]] = None

# Shopping List Models
class ShoppingItem(BaseModel):
    id: Optional[str] = None
    name: str
    quantity: Optional[float] = None
    amount: Optional[str] = None  # Legacy field, use quantity instead
    unit: Optional[str] = ""
    category: Optional[str] = None
    checked: bool = False
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None
    recipe_ids: Optional[List[str]] = None  # Provenance when items are merged
    recipe_names: Optional[List[str]] = None
    in_pantry: Optional[bool] = False  # Already on hand — review before buying
    price: Optional[float] = None  # Price per unit
    sort_order: Optional[int] = 0  # For aisle / manual reordering

class ShoppingItemCreate(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = ""
    category: Optional[str] = None
    recipe_id: Optional[str] = None
    recipe_name: Optional[str] = None
    price: Optional[float] = None

class ShoppingItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    checked: Optional[bool] = None
    price: Optional[float] = None
    sort_order: Optional[int] = None

class ShoppingListCreate(BaseModel):
    name: str
    items: Optional[List[ShoppingItem]] = []

class ShoppingListResponse(BaseModel):
    id: str
    name: str
    items: List[ShoppingItem]
    household_id: str
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

# AI Models
class ImportURLRequest(BaseModel):
    url: str

class ImportTextRequest(BaseModel):
    text: str

class ImportFeedbackRequest(BaseModel):
    """User rating / correction for an AI recipe import."""
    rating: str  # good | ok | bad
    import_id: Optional[str] = None
    source_url: Optional[str] = None
    import_mode: Optional[str] = None
    recipe_id: Optional[str] = None
    note: Optional[str] = None
    original_recipe: Optional[dict] = None
    corrected_recipe: Optional[dict] = None
    platform: Optional[str] = None

class FridgeSearchRequest(BaseModel):
    ingredients: List[str]
    search_online: bool = False

class LLMSettingsUpdate(BaseModel):
    provider: str  # 'openai', 'anthropic', or 'ollama'
    ollama_url: Optional[str] = 'http://localhost:11434'
    ollama_model: Optional[str] = 'llama3'
    # OpenAI-compatible (official API or LM Studio / local gateways)
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = 'gpt-4o'

class ImportPlatformRequest(BaseModel):
    platform: str  # 'paprika', 'cookmate', 'json', 'text'
    data: str  # JSON string or text content

# Custom AI Prompts
class CustomPromptsUpdate(BaseModel):
    recipe_extraction: Optional[str] = None  # Custom prompt for recipe extraction
    meal_planning: Optional[str] = None  # Custom prompt for meal planning
    fridge_search: Optional[str] = None  # Custom prompt for fridge/ingredient search

# Recipe Feedback (Would cook again?)
class RecipeFeedback(BaseModel):
    recipe_id: str
    feedback: str  # 'yes', 'no', 'meh'

class CookSessionCreate(BaseModel):
    recipe_id: str
    started_at: Optional[str] = None

class CookSessionComplete(BaseModel):
    feedback: Optional[str] = None  # 'yes', 'no', 'meh'
    notes: Optional[str] = None  # personal cook note ("kids loved it")

class MarkCookedRequest(BaseModel):
    """Mark a recipe as cooked without full cook-mode session."""
    notes: Optional[str] = None
    feedback: Optional[str] = None  # 'yes', 'no', 'meh'


# Cookbook Models
class CookbookCreate(BaseModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    cover_image_url: Optional[str] = None
    notes: Optional[str] = None


class CookbookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    cover_image_url: Optional[str] = None
    notes: Optional[str] = None


class CookbookResponse(BaseModel):
    id: str
    user_id: str
    household_id: Optional[str] = None
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    cover_image_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class ISBNLookupResponse(BaseModel):
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    cover_image_url: Optional[str] = None
    isbn: str


class CookbookBuyLink(BaseModel):
    """Outbound legal purchase / borrow / storefront search link (never a pirate host)."""
    label: str
    url: str
    kind: str  # amazon | bookshop | open_library | archive | drm_free_search | publisher


class CookbookBuySearchResult(BaseModel):
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    cover_image_url: Optional[str] = None
    open_library_key: Optional[str] = None
    source: str = "open_library"  # open_library | google_books
    buy_links: List[CookbookBuyLink] = []


class CookbookBuySearchResponse(BaseModel):
    query: str
    results: List[CookbookBuySearchResult]


# Pantry Models
class PantryItemCreate(BaseModel):
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = "pantry"
    expiry_date: Optional[str] = None  # ISO date string
    notes: Optional[str] = None
    is_staple: Optional[bool] = False


class PantryItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = None
    is_staple: Optional[bool] = None


class PantryItemResponse(BaseModel):
    id: str
    user_id: str
    household_id: Optional[str] = None
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    category: str
    expiry_date: Optional[str] = None
    notes: Optional[str] = None
    is_staple: bool
    created_at: str
    updated_at: str

    @field_validator('created_at', 'updated_at', 'expiry_date', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class PantryBulkCreate(BaseModel):
    items: List[PantryItemCreate]


class PantryBulkDelete(BaseModel):
    item_ids: List[str]


class CheckVetoRequest(BaseModel):
    """Check recipe ingredients against the user's adult/kid veto lists."""
    ingredients: List[Any] = []  # [{name, amount, unit}] or plain strings


class CheckVetoSuggestion(BaseModel):
    name: str
    reason: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None  # curated | food_db | function | ai


class CheckVetoHit(BaseModel):
    ingredient: str
    ingredient_index: int
    matched_veto: str
    list: str  # adult | kid
    lists: Optional[List[str]] = None
    severity: Optional[str] = "preference"


class CheckVetoReplacement(CheckVetoHit):
    suggestions: List[CheckVetoSuggestion] = []


class CheckVetoResponse(BaseModel):
    hits: List[CheckVetoHit] = []
    replacements: List[CheckVetoReplacement] = []
    has_hits: bool = False


class IngredientSubstitutionRequest(BaseModel):
    ingredient: str
    limit: Optional[int] = 5
    # Recipe context — used by Laro AI so swaps fit this dish
    recipe_id: Optional[str] = None
    recipe_title: Optional[str] = None
    recipe_description: Optional[str] = None
    ingredients: Optional[List[Any]] = None
    instructions: Optional[List[Any]] = None
    use_ai: Optional[bool] = True


class IngredientSubstitutionResponse(BaseModel):
    ingredient: str
    suggestions: List[CheckVetoSuggestion] = []
    category: Optional[str] = None
    roles: Optional[List[str]] = None
    ai_used: Optional[bool] = False
    source: Optional[str] = None  # ai | local


class RecipeBulkDelete(BaseModel):
    recipe_ids: List[str]


# Recipe Matching Models
class RecipeMatchRequest(BaseModel):
    pantry_item_ids: Optional[List[str]] = None  # If None, use all user's pantry items
    match_threshold: Optional[float] = 0.3  # Minimum match percentage (0.0 to 1.0)
    exclude_staples: Optional[bool] = True  # Ignore common staples in matching


class RecipeMatchResult(BaseModel):
    recipe: RecipeResponse
    match_percentage: float
    matched_ingredients: List[str]
    missing_ingredients: List[str]


class RecipeMatchResponse(BaseModel):
    matches: List[RecipeMatchResult]
    pantry_item_count: int
    total_recipes_checked: int


# Image Extraction Models
class ImageExtractionRequest(BaseModel):
    images: List[str]  # List of base64-encoded images
    cookbook_id: Optional[str] = None
    cookbook_page: Optional[int] = None


# Enhanced Grocery List Models
class GroceryGenerateRequest(BaseModel):
    recipe_ids: List[str]
    exclude_pantry: Optional[bool] = True  # Mark / skip items user already has
    combine_quantities: Optional[bool] = True  # Combine same ingredients
    assign_aisles: Optional[bool] = True
    # When True with exclude_pantry: keep pantry hits on the list (in_pantry=True)
    # for SideChef-style review instead of dropping them.
    keep_pantry_items: Optional[bool] = True


class GroceryGenerateResponse(BaseModel):
    items: List[ShoppingItem]
    excluded_count: int
    excluded_items: List[str]
    recipes_used: Optional[List[dict]] = None


class FromMealPlanRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str
    meal_types: Optional[List[str]] = None
    exclude_pantry: Optional[bool] = True
    combine_quantities: Optional[bool] = True
    assign_aisles: Optional[bool] = True
    keep_pantry_items: Optional[bool] = True
    list_name: Optional[str] = None
    save: Optional[bool] = True


class FromMealPlanResponse(BaseModel):
    list: Optional[ShoppingListResponse] = None
    items: List[ShoppingItem]
    excluded_count: int
    excluded_items: List[str]
    recipes_used: List[dict]
    meal_count: int
    list_name: str


# Mobile Notification Settings
class MobileNotificationSettingsUpdate(BaseModel):
    fcm_token: Optional[str] = None
    apns_token: Optional[str] = None
    reminder_time: Optional[str] = None  # HH:MM format

    # Master toggles
    push_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None

    # Subscription notifications
    subscription_alerts: Optional[bool] = None  # trial ending, billing issues, renewal

    # Engagement notifications
    weekly_digest: Optional[bool] = None
    streak_notifications: Optional[bool] = None
    milestone_notifications: Optional[bool] = None

    # Social notifications
    household_updates: Optional[bool] = None  # joins, invites
    recipe_shared: Optional[bool] = None
    cookbook_updates: Optional[bool] = None

    # Shopping notifications
    shopping_list_updates: Optional[bool] = None
    shopping_reminders: Optional[bool] = None

    # App notifications
    meal_reminders: Optional[bool] = None
    weekly_plan_reminder: Optional[bool] = None
    expiry_alerts: Optional[bool] = None
    import_complete: Optional[bool] = None
    ai_complete: Optional[bool] = None

    # Security notifications (always recommended)
    security_alerts: Optional[bool] = None  # new login, password changed


class MobileNotificationSettingsResponse(BaseModel):
    user_id: str
    fcm_token: Optional[str] = None
    apns_token: Optional[str] = None
    reminder_time: str

    # Master toggles
    push_enabled: bool = True
    email_enabled: bool = True

    # Subscription
    subscription_alerts: bool = True

    # Engagement
    weekly_digest: bool = True
    streak_notifications: bool = True
    milestone_notifications: bool = True

    # Social
    household_updates: bool = True
    recipe_shared: bool = True
    cookbook_updates: bool = True

    # Shopping
    shopping_list_updates: bool = True
    shopping_reminders: bool = True

    # App
    meal_reminders: bool = True
    weekly_plan_reminder: bool = True
    expiry_alerts: bool = True
    import_complete: bool = True
    ai_complete: bool = True

    # Security
    security_alerts: bool = True

    updated_at: Optional[str] = None

    @field_validator('updated_at', mode='before')
    @classmethod
    def convert_datetime_to_string(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v


# Data Export Models
class DataExportRequest(BaseModel):
    format: str  # 'json', 'pdf', 'markdown'
    include: Optional[List[str]] = None  # 'recipes', 'cookbooks', 'pantry', 'meal_plans', 'shopping_lists'


class DataExportResponse(BaseModel):
    download_url: str
    expires_at: str
    format: str
    file_size: Optional[int] = None
