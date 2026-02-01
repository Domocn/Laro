from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List, Optional, Union
from datetime import datetime

# Auth Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str

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
    name: str
    amount: str
    unit: Optional[str] = ""

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
    recipe_id: str
    notes: Optional[str] = ""

class MealPlanResponse(BaseModel):
    id: str
    date: str
    meal_type: str
    recipe_id: str
    recipe_title: str
    notes: str
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
    price: Optional[float] = None  # Price per unit
    sort_order: Optional[int] = 0  # For manual reordering

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

class FridgeSearchRequest(BaseModel):
    ingredients: List[str]
    search_online: bool = False

class LLMSettingsUpdate(BaseModel):
    provider: str  # 'openai', 'anthropic', or 'ollama'
    ollama_url: Optional[str] = 'http://localhost:11434'
    ollama_model: Optional[str] = 'llama3'

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
    feedback: str  # 'yes', 'no', 'meh'


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
    exclude_pantry: Optional[bool] = True  # Don't add items user already has
    combine_quantities: Optional[bool] = True  # Combine same ingredients


class GroceryGenerateResponse(BaseModel):
    items: List[ShoppingItem]
    excluded_count: int
    excluded_items: List[str]


# Mobile Notification Settings
class MobileNotificationSettingsUpdate(BaseModel):
    fcm_token: Optional[str] = None
    apns_token: Optional[str] = None
    meal_reminders: Optional[bool] = None
    expiry_alerts: Optional[bool] = None
    shared_list_updates: Optional[bool] = None
    import_complete: Optional[bool] = None
    reminder_time: Optional[str] = None  # HH:MM format


class MobileNotificationSettingsResponse(BaseModel):
    user_id: str
    fcm_token: Optional[str] = None
    apns_token: Optional[str] = None
    meal_reminders: bool
    expiry_alerts: bool
    shared_list_updates: bool
    import_complete: bool
    reminder_time: str
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
