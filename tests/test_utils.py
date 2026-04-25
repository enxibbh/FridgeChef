import utils


def make_meal(
    meal_id: str,
    name: str,
    area: str,
    category: str,
    ingredients: list[tuple[str, str]],
    tags: str = "",
) -> dict:
    meal = {
        "idMeal": meal_id,
        "strMeal": name,
        "strArea": area,
        "strCategory": category,
        "strTags": tags,
        "strInstructions": f"Cook {name}",
        "strMealThumb": f"https://example.com/{meal_id}.jpg",
        "strYoutube": "",
        "strSource": "",
    }
    for index in range(1, 21):
        meal[f"strIngredient{index}"] = ""
        meal[f"strMeasure{index}"] = ""
    for index, (ingredient, measure) in enumerate(ingredients, start=1):
        meal[f"strIngredient{index}"] = ingredient
        meal[f"strMeasure{index}"] = measure
    return meal


def sample_recipes() -> list[dict]:
    pasta = make_meal(
        "1",
        "Garlic Pasta",
        "Italian",
        "Pasta",
        [
            ("garlic", "2 cloves"),
            ("pasta", "200g"),
            ("olive oil", "1 tbsp"),
            ("salt", "1 tsp"),
        ],
        tags="Quick,Comfort Food",
    )
    stir_fry = make_meal(
        "2",
        "Veggie Stir Fry",
        "Chinese",
        "Vegetarian",
        [
            ("broccoli", "1 cup"),
            ("soy sauce", "2 tbsp"),
            ("garlic", "1 clove"),
            ("carrot", "1"),
        ],
        tags="Spicy,Quick",
    )
    return [pasta, stir_fry]


def recipe_view(detail: dict, fridge: list[str], source_hits: int = 1) -> dict:
    completion_pct, have, missing = utils.calc_match(detail, fridge)
    return {
        "id": detail["idMeal"],
        "name": detail["strMeal"],
        "area": detail.get("strArea") or "Unknown",
        "category": detail.get("strCategory") or "Unknown",
        "thumbnail": detail.get("strMealThumb") or "",
        "instructions": detail.get("strInstructions") or "",
        "youtube": detail.get("strYoutube") or "",
        "source": detail.get("strSource") or "",
        "ingredients": utils.extract_ingredients(detail),
        "have": have,
        "missing": missing,
        "completion_pct": completion_pct,
        "target_score": 0,
        "source_hits": source_hits,
    }


def test_parse_ingredient_text_splits_normalizes_and_deduplicates():
    parsed = utils.parse_ingredient_text("Chicken, onion / GARLIC\nonion")
    assert parsed == ["chicken", "onion", "garlic"]


def test_is_match_handles_simple_plural_and_preparation_words():
    assert utils.is_match("chopped tomatoes", "tomato")
    assert utils.is_match("garlic cloves", "garlic")
    assert not utils.is_match("beef", "chicken")


def test_low_impact_ingredients_have_lower_weight():
    assert utils.ingredient_weight("olive oil") == 0.25
    assert utils.ingredient_weight("sea salt") == 0.25
    assert utils.ingredient_weight("garlic") == 1.0


def test_calc_match_uses_weighted_completion_for_pantry_items():
    pasta = sample_recipes()[0]
    pct, have, missing = utils.calc_match(pasta, ["garlic", "pasta"])

    assert pct == 80
    assert [item["name"] for item in have] == ["garlic", "pasta"]
    assert [item["name"] for item in missing] == ["olive oil", "salt"]


def test_target_fit_score_rewards_area_and_flavor_keywords():
    pasta, stir_fry = sample_recipes()

    assert utils.target_fit_score(pasta, "Italian") >= 5
    assert utils.target_fit_score(stir_fry, "Spicy") >= 1
    assert utils.target_fit_score(stir_fry, "Vegetarian") >= 6


def test_build_rankings_frame_preserves_recipe_order_and_missing_text():
    pasta, stir_fry = sample_recipes()
    rankings = utils.build_rankings_frame(
        [
            recipe_view(pasta, ["garlic", "pasta"]),
            recipe_view(stir_fry, ["garlic"]),
        ]
    )

    assert list(rankings["Rank"]) == [1, 2]
    assert list(rankings["Recipe"]) == ["Garlic Pasta", "Veggie Stir Fry"]
    assert rankings.iloc[0]["Missing ingredients"] == "olive oil, salt"


def test_build_shopping_list_merges_same_missing_ingredient_across_recipes():
    pasta, stir_fry = sample_recipes()
    shopping_list = utils.build_shopping_list(
        [
            recipe_view(pasta, ["garlic", "pasta"]),
            recipe_view(stir_fry, ["garlic"]),
        ]
    )

    soy_row = next(item for item in shopping_list if item["Ingredient"] == "Soy Sauce")
    assert soy_row["Recipe count"] == 1

    garlic_row_names = [item["Ingredient"] for item in shopping_list]
    assert "Olive Oil" in garlic_row_names
    assert "Salt" in garlic_row_names


def test_get_ingredient_frequency_counts_have_and_missing_occurrences():
    pasta, stir_fry = sample_recipes()
    frequency = utils.get_ingredient_frequency(
        [
            recipe_view(pasta, ["garlic", "pasta"]),
            recipe_view(stir_fry, ["garlic"]),
        ]
    )

    garlic_count = frequency.loc[frequency["Ingredient"] == "garlic", "Appears in # recipes"].iloc[0]
    assert garlic_count == 2


def test_build_interactive_network_html_includes_selected_and_fridge_colors():
    pasta, stir_fry = sample_recipes()
    recipes = [
        recipe_view(pasta, ["garlic", "pasta"]),
        recipe_view(stir_fry, ["garlic"]),
    ]

    html = utils.build_interactive_network_html(recipes, ["carrot"], selected_recipe_id="1", height=500)

    assert 'height:500px' in html
    assert "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js" in html
    assert "#ef4444" in html
    assert "#d9f99d" in html
    assert "hover\": false" in html


def test_discover_recipes_ranks_and_filters_results(monkeypatch):
    pasta, stir_fry = sample_recipes()

    utils.search_by_ingredient.cache_clear()
    utils.search_by_area.cache_clear()
    utils.search_by_category.cache_clear()
    utils.get_meal_detail.cache_clear()

    monkeypatch.setattr(
        utils,
        "search_by_ingredient",
        lambda ingredient: [{"idMeal": "1"}, {"idMeal": "2"}] if ingredient == "garlic" else [],
    )
    monkeypatch.setattr(
        utils,
        "search_by_area",
        lambda area: [{"idMeal": "1"}] if area == "Italian" else [],
    )
    monkeypatch.setattr(utils, "search_by_category", lambda category: [])
    monkeypatch.setattr(
        utils,
        "fetch_recipes_parallel",
        lambda recipe_ids: [pasta, stir_fry],
    )

    recipes = utils.discover_recipes(["garlic", "pasta"], target="Italian", max_recipes=5)

    assert [recipe["id"] for recipe in recipes] == ["1", "2"]
    assert recipes[0]["completion_pct"] > recipes[1]["completion_pct"]
    assert recipes[0]["target_score"] >= recipes[1]["target_score"]
