"""Audio-first import when Instagram captions are promo-only."""

from services.instagram_media import caption_looks_like_recipe


def test_promo_caption_is_not_recipe_like():
    assert not caption_looks_like_recipe(
        "Noodle broth bowl — macros don't lie. Full recipe is in the audio #gym #noodles"
    )
    assert not caption_looks_like_recipe(
        "The meal I have every single day #noodles #anabolic #fyp"
    )


def test_measured_caption_is_recipe_like():
    assert caption_looks_like_recipe(
        "Ingredients:\n1 tbsp soy sauce\n100g noodles\n250g white fish\nBake 15 minutes"
    )
