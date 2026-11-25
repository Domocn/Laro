"""Typed names without accents still match Mealime catalog names."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.mealime_migrate import mealime_slug, normalize_name  # noqa: E402


def test_accents_fold():
    assert normalize_name("Parsley Saut\u00e9ed Carrots") == normalize_name("Parsley Sauteed Carrots")


def test_slug_folds_accents():
    assert mealime_slug("Balsamic Chicken Drumsticks with Garlic & Parsley Saut\u00e9ed Carrots") == \
        "balsamic-chicken-drumsticks-garlic-parsley-sauteed-carrots"
