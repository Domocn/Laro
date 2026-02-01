"""
Seed Data Router - Create test recipes for development/testing
"""
from fastapi import APIRouter, Depends
from dependencies import get_current_user, recipe_repository, recipe_version_repository
from datetime import datetime, timezone
import uuid

router = APIRouter(prefix="/seed", tags=["Seed Data"])

# =============================================================================
# TEST RECIPES
# =============================================================================

TEST_RECIPES = [
    {
        "title": "Classic Spaghetti Carbonara",
        "description": "A creamy Italian pasta dish made with eggs, cheese, pancetta, and pepper. Quick, simple, and absolutely delicious.",
        "category": "Dinner",
        "cuisine": "Italian",
        "prep_time": 10,
        "cook_time": 20,
        "servings": 4,
        "difficulty": "Medium",
        "ingredients": [
            {"amount": "400", "unit": "g", "name": "spaghetti"},
            {"amount": "200", "unit": "g", "name": "pancetta or guanciale"},
            {"amount": "4", "unit": "", "name": "large eggs"},
            {"amount": "100", "unit": "g", "name": "Pecorino Romano cheese, grated"},
            {"amount": "50", "unit": "g", "name": "Parmesan cheese, grated"},
            {"amount": "2", "unit": "cloves", "name": "garlic"},
            {"amount": "2", "unit": "tbsp", "name": "olive oil"},
            {"amount": "", "unit": "", "name": "Black pepper, freshly ground"},
            {"amount": "", "unit": "", "name": "Salt to taste"},
        ],
        "instructions": [
            "Bring a large pot of salted water to boil. Cook spaghetti according to package directions until al dente.",
            "While pasta cooks, cut pancetta into small cubes. Heat olive oil in a large skillet over medium heat.",
            "Add pancetta and cook for 5-7 minutes until crispy. Add garlic and cook for 1 minute more, then remove from heat.",
            "In a bowl, whisk together eggs, Pecorino, Parmesan, and plenty of black pepper.",
            "When pasta is ready, reserve 1 cup of pasta water, then drain. Working quickly while pasta is still hot, add it to the skillet with pancetta.",
            "Remove skillet from heat completely. Pour egg mixture over pasta and toss vigorously for 2 minutes. The residual heat will cook the eggs into a creamy sauce.",
            "Add pasta water a little at a time if needed to achieve silky consistency. Season with salt and more pepper.",
            "Serve immediately with extra cheese and pepper on top.",
        ],
        "tags": ["pasta", "italian", "quick", "comfort food", "classic"],
        "image_url": "https://images.unsplash.com/photo-1612874742237-6526221588e3?w=800",
    },
    {
        "title": "Honey Garlic Salmon",
        "description": "Tender, flaky salmon glazed with a sweet and savory honey garlic sauce. Ready in under 30 minutes!",
        "category": "Dinner",
        "cuisine": "Asian-Fusion",
        "prep_time": 10,
        "cook_time": 15,
        "servings": 4,
        "difficulty": "Easy",
        "ingredients": [
            {"amount": "4", "unit": "", "name": "salmon fillets (6 oz each)"},
            {"amount": "4", "unit": "tbsp", "name": "honey"},
            {"amount": "3", "unit": "tbsp", "name": "soy sauce"},
            {"amount": "4", "unit": "cloves", "name": "garlic, minced"},
            {"amount": "1", "unit": "tbsp", "name": "fresh ginger, grated"},
            {"amount": "2", "unit": "tbsp", "name": "olive oil"},
            {"amount": "1", "unit": "tbsp", "name": "sesame oil"},
            {"amount": "1", "unit": "", "name": "lemon, juiced"},
            {"amount": "", "unit": "", "name": "Sesame seeds for garnish"},
            {"amount": "", "unit": "", "name": "Green onions, sliced"},
        ],
        "instructions": [
            "Pat salmon fillets dry with paper towels. Season with salt and pepper on both sides.",
            "In a small bowl, whisk together honey, soy sauce, garlic, ginger, and lemon juice.",
            "Heat olive oil and sesame oil in a large oven-safe skillet over medium-high heat.",
            "Place salmon skin-side up and sear for 3-4 minutes until golden brown.",
            "Flip salmon and pour honey garlic sauce over the fillets.",
            "Transfer skillet to oven preheated to 400°F (200°C). Bake for 8-10 minutes until salmon flakes easily.",
            "Remove from oven and spoon sauce over salmon. Let rest 2 minutes.",
            "Garnish with sesame seeds and green onions. Serve with rice and vegetables.",
        ],
        "tags": ["seafood", "healthy", "quick", "asian", "protein"],
        "image_url": "https://images.unsplash.com/photo-1467003909585-2f8a72700288?w=800",
    },
    {
        "title": "Fluffy Buttermilk Pancakes",
        "description": "Light, fluffy pancakes that are crispy on the outside and tender on the inside. Perfect for weekend brunch!",
        "category": "Breakfast",
        "cuisine": "American",
        "prep_time": 10,
        "cook_time": 20,
        "servings": 8,
        "difficulty": "Easy",
        "ingredients": [
            {"amount": "2", "unit": "cups", "name": "all-purpose flour"},
            {"amount": "2", "unit": "tbsp", "name": "sugar"},
            {"amount": "2", "unit": "tsp", "name": "baking powder"},
            {"amount": "1", "unit": "tsp", "name": "baking soda"},
            {"amount": "1/2", "unit": "tsp", "name": "salt"},
            {"amount": "2", "unit": "cups", "name": "buttermilk"},
            {"amount": "2", "unit": "", "name": "large eggs"},
            {"amount": "1/4", "unit": "cup", "name": "melted butter"},
            {"amount": "1", "unit": "tsp", "name": "vanilla extract"},
            {"amount": "", "unit": "", "name": "Butter for cooking"},
        ],
        "instructions": [
            "In a large bowl, whisk together flour, sugar, baking powder, baking soda, and salt.",
            "In another bowl, whisk buttermilk, eggs, melted butter, and vanilla until combined.",
            "Pour wet ingredients into dry ingredients. Stir until just combined - lumps are okay! Don't overmix.",
            "Let batter rest for 5 minutes while you heat your griddle or pan to medium heat.",
            "Lightly butter the cooking surface. Pour 1/4 cup batter per pancake.",
            "Cook until bubbles form on surface and edges look set, about 2-3 minutes.",
            "Flip and cook another 1-2 minutes until golden brown on both sides.",
            "Keep warm in 200°F oven while cooking remaining pancakes. Serve with maple syrup and fresh berries!",
        ],
        "tags": ["breakfast", "brunch", "vegetarian", "kid-friendly", "classic"],
        "image_url": "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445?w=800",
    },
    {
        "title": "Thai Green Curry",
        "description": "A fragrant, creamy Thai curry with tender chicken, colorful vegetables, and aromatic Thai basil.",
        "category": "Dinner",
        "cuisine": "Thai",
        "prep_time": 15,
        "cook_time": 25,
        "servings": 4,
        "difficulty": "Medium",
        "ingredients": [
            {"amount": "1", "unit": "lb", "name": "chicken breast, sliced"},
            {"amount": "1", "unit": "can", "name": "coconut milk (14 oz)"},
            {"amount": "3", "unit": "tbsp", "name": "green curry paste"},
            {"amount": "1", "unit": "cup", "name": "chicken broth"},
            {"amount": "1", "unit": "", "name": "bell pepper, sliced"},
            {"amount": "1", "unit": "cup", "name": "bamboo shoots"},
            {"amount": "1", "unit": "cup", "name": "Thai eggplant or zucchini"},
            {"amount": "2", "unit": "tbsp", "name": "fish sauce"},
            {"amount": "1", "unit": "tbsp", "name": "palm sugar or brown sugar"},
            {"amount": "1", "unit": "cup", "name": "fresh Thai basil leaves"},
            {"amount": "2", "unit": "", "name": "kaffir lime leaves"},
            {"amount": "", "unit": "", "name": "Thai chilies (optional)"},
        ],
        "instructions": [
            "Heat 2 tbsp of the thick cream from top of coconut milk in a wok over medium-high heat.",
            "Add green curry paste and fry for 1-2 minutes until fragrant and paste darkens slightly.",
            "Add chicken pieces and stir-fry for 3-4 minutes until coated and partially cooked.",
            "Pour in remaining coconut milk and chicken broth. Add kaffir lime leaves.",
            "Bring to a simmer and add vegetables. Cook for 8-10 minutes until chicken is cooked through.",
            "Season with fish sauce and sugar. Taste and adjust - it should be salty, sweet, and a bit spicy.",
            "Remove from heat and stir in Thai basil until just wilted.",
            "Serve hot over jasmine rice. Garnish with extra basil and sliced chilies.",
        ],
        "tags": ["asian", "thai", "curry", "spicy", "gluten-free"],
        "image_url": "https://images.unsplash.com/photo-1455619452474-d2be8b1e70cd?w=800",
    },
    {
        "title": "Classic Margherita Pizza",
        "description": "Simple, authentic Neapolitan-style pizza with fresh tomatoes, mozzarella, and basil.",
        "category": "Dinner",
        "cuisine": "Italian",
        "prep_time": 90,
        "cook_time": 15,
        "servings": 2,
        "difficulty": "Medium",
        "ingredients": [
            {"amount": "2 1/4", "unit": "tsp", "name": "active dry yeast"},
            {"amount": "1", "unit": "cup", "name": "warm water (110°F)"},
            {"amount": "3", "unit": "cups", "name": "all-purpose flour"},
            {"amount": "1", "unit": "tsp", "name": "salt"},
            {"amount": "1", "unit": "tbsp", "name": "olive oil"},
            {"amount": "1", "unit": "can", "name": "San Marzano tomatoes (14 oz)"},
            {"amount": "8", "unit": "oz", "name": "fresh mozzarella, sliced"},
            {"amount": "", "unit": "", "name": "Fresh basil leaves"},
            {"amount": "2", "unit": "tbsp", "name": "extra virgin olive oil"},
            {"amount": "", "unit": "", "name": "Sea salt and pepper"},
        ],
        "instructions": [
            "Dissolve yeast in warm water, let stand 5 minutes until foamy. Mix flour and salt in large bowl.",
            "Add yeast mixture and olive oil. Knead for 8-10 minutes until smooth and elastic.",
            "Place in oiled bowl, cover, let rise 1 hour until doubled in size.",
            "For sauce: Crush San Marzano tomatoes by hand, season with salt. Don't cook it.",
            "Preheat oven to highest setting (500°F/260°C) with pizza stone or baking sheet inside.",
            "Divide dough in half. Stretch each half into 12-inch circle on floured surface.",
            "Spread thin layer of tomato sauce, leaving 1-inch border. Add mozzarella slices.",
            "Carefully transfer to hot stone. Bake 8-12 minutes until crust is golden and cheese bubbles.",
            "Remove from oven, top with fresh basil, drizzle with olive oil. Slice and serve immediately!",
        ],
        "tags": ["pizza", "italian", "vegetarian", "homemade", "classic"],
        "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=800",
    },
    {
        "title": "Chocolate Lava Cakes",
        "description": "Individual chocolate cakes with a gooey, molten center. An impressive dessert that's easier than you think!",
        "category": "Dessert",
        "cuisine": "French",
        "prep_time": 15,
        "cook_time": 14,
        "servings": 4,
        "difficulty": "Medium",
        "ingredients": [
            {"amount": "4", "unit": "oz", "name": "dark chocolate (70% cocoa)"},
            {"amount": "1/2", "unit": "cup", "name": "unsalted butter"},
            {"amount": "1", "unit": "cup", "name": "powdered sugar"},
            {"amount": "2", "unit": "", "name": "large eggs"},
            {"amount": "2", "unit": "", "name": "egg yolks"},
            {"amount": "6", "unit": "tbsp", "name": "all-purpose flour"},
            {"amount": "1", "unit": "tsp", "name": "vanilla extract"},
            {"amount": "", "unit": "", "name": "Butter and cocoa for ramekins"},
            {"amount": "", "unit": "", "name": "Vanilla ice cream for serving"},
        ],
        "instructions": [
            "Preheat oven to 425°F (220°C). Butter 4 ramekins and dust with cocoa powder.",
            "Melt chocolate and butter together in microwave (30-second intervals) or double boiler. Stir until smooth.",
            "Whisk in powdered sugar until combined. Add eggs and egg yolks, whisk well.",
            "Fold in flour and vanilla until just combined. Don't overmix!",
            "Divide batter evenly among prepared ramekins. Can refrigerate up to 24 hours at this point.",
            "Place ramekins on baking sheet. Bake 12-14 minutes until edges are firm but center is soft.",
            "Let cool 1 minute only. Run knife around edges and invert onto plates.",
            "Serve immediately with vanilla ice cream. The center should ooze when cut open!",
        ],
        "tags": ["dessert", "chocolate", "french", "impressive", "date night"],
        "image_url": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=800",
    },
    {
        "title": "Greek Chicken Salad Bowl",
        "description": "A fresh, healthy bowl packed with grilled chicken, crisp vegetables, feta, and tangy tzatziki.",
        "category": "Lunch",
        "cuisine": "Mediterranean",
        "prep_time": 20,
        "cook_time": 15,
        "servings": 4,
        "difficulty": "Easy",
        "ingredients": [
            {"amount": "1", "unit": "lb", "name": "chicken breast"},
            {"amount": "2", "unit": "cups", "name": "cucumber, diced"},
            {"amount": "2", "unit": "cups", "name": "cherry tomatoes, halved"},
            {"amount": "1", "unit": "", "name": "red onion, thinly sliced"},
            {"amount": "1", "unit": "cup", "name": "kalamata olives"},
            {"amount": "1", "unit": "cup", "name": "feta cheese, crumbled"},
            {"amount": "4", "unit": "cups", "name": "mixed greens or romaine"},
            {"amount": "1", "unit": "cup", "name": "cooked quinoa or rice"},
            {"amount": "1", "unit": "cup", "name": "tzatziki sauce"},
            {"amount": "2", "unit": "tbsp", "name": "olive oil"},
            {"amount": "1", "unit": "tbsp", "name": "dried oregano"},
            {"amount": "", "unit": "", "name": "Lemon wedges"},
        ],
        "instructions": [
            "Season chicken with olive oil, oregano, salt, and pepper. Let marinate 15 minutes.",
            "Heat grill or grill pan to medium-high. Cook chicken 6-7 minutes per side until cooked through.",
            "Let chicken rest 5 minutes, then slice into strips.",
            "Prepare tzatziki: mix Greek yogurt, grated cucumber, garlic, dill, lemon juice, and salt.",
            "Divide greens among 4 bowls. Add quinoa or rice to each bowl.",
            "Arrange cucumber, tomatoes, onion, olives, and feta on top of greens.",
            "Add sliced chicken and drizzle generously with tzatziki.",
            "Serve with lemon wedges and extra oregano. Enjoy fresh!",
        ],
        "tags": ["healthy", "salad", "mediterranean", "high-protein", "meal prep"],
        "image_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=800",
    },
    {
        "title": "Homemade Beef Tacos",
        "description": "Flavorful seasoned ground beef in warm tortillas with all your favorite toppings. A family favorite!",
        "category": "Dinner",
        "cuisine": "Mexican",
        "prep_time": 15,
        "cook_time": 20,
        "servings": 6,
        "difficulty": "Easy",
        "ingredients": [
            {"amount": "1.5", "unit": "lbs", "name": "ground beef"},
            {"amount": "1", "unit": "", "name": "onion, diced"},
            {"amount": "3", "unit": "cloves", "name": "garlic, minced"},
            {"amount": "2", "unit": "tbsp", "name": "chili powder"},
            {"amount": "1", "unit": "tsp", "name": "cumin"},
            {"amount": "1", "unit": "tsp", "name": "paprika"},
            {"amount": "1/2", "unit": "tsp", "name": "oregano"},
            {"amount": "12", "unit": "", "name": "small tortillas (corn or flour)"},
            {"amount": "2", "unit": "cups", "name": "shredded lettuce"},
            {"amount": "1", "unit": "cup", "name": "shredded cheese"},
            {"amount": "1", "unit": "cup", "name": "pico de gallo"},
            {"amount": "1", "unit": "cup", "name": "sour cream"},
            {"amount": "", "unit": "", "name": "Fresh cilantro and lime wedges"},
        ],
        "instructions": [
            "Heat large skillet over medium-high heat. Add ground beef and cook, breaking up with spoon.",
            "When beef is halfway cooked, add diced onion. Continue cooking until beef is browned.",
            "Add garlic, chili powder, cumin, paprika, and oregano. Stir well and cook 2 minutes.",
            "Add 1/2 cup water, reduce heat, and simmer 5 minutes until slightly thickened.",
            "Meanwhile, warm tortillas in dry skillet or directly over gas flame until pliable.",
            "Set up taco bar with bowls of lettuce, cheese, pico de gallo, sour cream, and cilantro.",
            "Spoon seasoned beef into warm tortillas and let everyone build their own tacos.",
            "Serve with lime wedges and your favorite hot sauce. Enjoy!",
        ],
        "tags": ["mexican", "tacos", "family-friendly", "customizable", "quick"],
        "image_url": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800",
    },
]

# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/recipes")
async def seed_test_recipes(user: dict = Depends(get_current_user)):
    """Create test recipes for the current user"""
    created_count = 0

    for recipe_data in TEST_RECIPES:
        # Check if recipe already exists
        existing = await recipe_repository.find_by_title_and_author(
            recipe_data["title"], user["id"]
        )

        if existing:
            continue

        now = datetime.now(timezone.utc).isoformat()
        recipe = {
            "id": str(uuid.uuid4()),
            "author_id": user["id"],
            "household_id": user.get("household_id"),
            "created_at": now,
            "updated_at": now,
            "is_favorite": False,
            "times_cooked": 0,
            "current_version": 1,
            **recipe_data
        }

        await recipe_repository.create(recipe)

        # Create initial version
        await recipe_version_repository.create({
            "id": str(uuid.uuid4()),
            "recipe_id": recipe["id"],
            "version": 1,
            "data": recipe_data,
            "change_note": "Initial version",
            "created_by": user["id"],
            "created_at": now
        })

        created_count += 1

    return {
        "message": f"Created {created_count} test recipes",
        "total_test_recipes": len(TEST_RECIPES)
    }


@router.delete("/recipes")
async def delete_test_recipes(user: dict = Depends(get_current_user)):
    """Delete all test recipes created by seeding"""
    test_titles = [r["title"] for r in TEST_RECIPES]
    deleted_count = 0

    for title in test_titles:
        recipe = await recipe_repository.find_by_title_and_author(title, user["id"])
        if recipe:
            await recipe_repository.delete(recipe["id"])
            deleted_count += 1

    return {"message": f"Deleted {deleted_count} test recipes"}


@router.get("/recipes/list")
async def list_test_recipe_titles():
    """List available test recipes"""
    return {
        "test_recipes": [
            {"title": r["title"], "category": r["category"], "cuisine": r["cuisine"]}
            for r in TEST_RECIPES
        ]
    }
