from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import pandas as pd
import requests


BASE_URL = "https://www.themealdb.com/api/json/v1/1"

CUISINES = [
    "American",
    "British",
    "Canadian",
    "Chinese",
    "Croatian",
    "Dutch",
    "Egyptian",
    "Filipino",
    "French",
    "Greek",
    "Indian",
    "Irish",
    "Italian",
    "Jamaican",
    "Japanese",
    "Kenyan",
    "Malaysian",
    "Mexican",
    "Moroccan",
    "Polish",
    "Portuguese",
    "Russian",
    "Spanish",
    "Thai",
    "Tunisian",
    "Turkish",
    "Ukrainian",
    "Vietnamese",
]

SUGGESTION_INGREDIENTS = [
    "chicken",
    "eggs",
    "garlic",
    "onion",
    "tomato",
    "pasta",
    "cheese",
    "potato",
    "lemon",
    "butter",
    "beef",
    "mushroom",
    "spinach",
    "carrot",
    "ginger",
    "milk",
    "flour",
    "shrimp",
]

TARGET_PROFILES = [
    "Italian",
    "Mexican",
    "Chinese",
    "Indian",
    "Japanese",
    "Thai",
    "French",
    "Greek",
    "American",
    "Spicy",
    "Creamy",
    "Fresh",
    "Savory",
    "Comfort Food",
    "Vegetarian",
    "Protein-Packed",
]

CATEGORY_TARGETS = {
    "Vegetarian": "Vegetarian",
}

FLAVOR_KEYWORDS = {
    "Spicy": ["chili", "pepper", "curry", "jalapeno", "spice", "harissa", "hot"],
    "Creamy": ["cream", "milk", "butter", "cheese", "alfredo", "coconut milk", "yogurt"],
    "Fresh": ["lemon", "lime", "mint", "parsley", "cucumber", "salad", "zest"],
    "Savory": ["garlic", "onion", "soy", "mushroom", "stock", "roast", "herb"],
    "Comfort Food": ["pie", "stew", "bake", "casserole", "potato", "cheese", "pasta"],
    "Protein-Packed": ["chicken", "beef", "pork", "fish", "tofu", "egg", "beans", "lentils"],
    "Vegetarian": ["vegetarian", "tofu", "beans", "lentils", "chickpeas", "spinach"],
}

STOP_WORDS = {
    "chopped",
    "sliced",
    "diced",
    "fresh",
    "dried",
    "large",
    "small",
    "minced",
    "powdered",
    "ground",
    "grated",
    "shredded",
    "crushed",
    "to",
    "taste",
    "extra",
    "virgin",
    "boneless",
    "skinless",
}

LOW_IMPACT_INGREDIENTS = {
    "salt",
    "sea salt",
    "pepper",
    "black pepper",
    "white pepper",
    "olive oil",
    "vegetable oil",
    "canola oil",
    "sunflower oil",
    "sesame oil",
    "oil",
    "water",
    "sugar",
    "soy sauce",
    "vinegar",
}


def _safe_get_json(endpoint: str, **params) -> dict:
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=8)
        response.raise_for_status()
        return response.json()
    except Exception:
        return {}


@lru_cache(maxsize=256)
def search_by_ingredient(ingredient: str) -> list[dict]:
    ingredient = ingredient.strip().lower()
    if not ingredient:
        return []
    data = _safe_get_json("filter.php", i=ingredient)
    return data.get("meals") or []


@lru_cache(maxsize=128)
def search_by_area(area: str) -> list[dict]:
    area = area.strip()
    if not area:
        return []
    data = _safe_get_json("filter.php", a=area)
    return data.get("meals") or []


@lru_cache(maxsize=128)
def search_by_category(category: str) -> list[dict]:
    category = category.strip()
    if not category:
        return []
    data = _safe_get_json("filter.php", c=category)
    return data.get("meals") or []


@lru_cache(maxsize=512)
def get_meal_detail(meal_id: str) -> dict | None:
    if not meal_id:
        return None
    data = _safe_get_json("lookup.php", i=meal_id)
    meals = data.get("meals")
    return meals[0] if meals else None


def fetch_recipes_parallel(recipe_ids: list[str]) -> list[dict]:
    if not recipe_ids:
        return []

    with ThreadPoolExecutor(max_workers=12) as executor:
        details = list(executor.map(get_meal_detail, recipe_ids))

    return [detail for detail in details if detail]


def parse_ingredient_text(text: str) -> list[str]:
    parts = re.split(r"[,/\n]", text or "")
    cleaned = []
    for part in parts:
        item = part.strip().lower()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def normalize_text(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", (text or "").lower())
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def singularize(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("oes") and len(token) > 4:
        return token[:-2]
    if token.endswith("es") and len(token) > 4 and token[-3] in {"s", "x", "z"}:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> set[str]:
    tokens = normalize_text(text).split()
    return {singularize(token) for token in tokens if token and token not in STOP_WORDS}


def canonical_ingredient_name(name: str) -> str:
    tokens = sorted(tokenize(name))
    return " ".join(tokens) if tokens else normalize_text(name)


def is_match(item_name: str, fridge_item: str) -> bool:
    recipe_tokens = tokenize(item_name)
    fridge_tokens = tokenize(fridge_item)

    if not recipe_tokens or not fridge_tokens:
        return False

    return (
        fridge_tokens.issubset(recipe_tokens)
        or recipe_tokens.issubset(fridge_tokens)
        or bool(recipe_tokens.intersection(fridge_tokens))
    )


def extract_ingredients(meal: dict) -> list[dict]:
    items = []
    for index in range(1, 21):
        name = (meal.get(f"strIngredient{index}") or "").strip()
        measure = (meal.get(f"strMeasure{index}") or "").strip()
        if name:
            items.append({"name": name.lower(), "measure": measure})
    return items


def ingredient_weight(ingredient_name: str) -> float:
    normalized = canonical_ingredient_name(ingredient_name)
    if normalized in LOW_IMPACT_INGREDIENTS:
        return 0.25

    tokens = tokenize(ingredient_name)
    if tokens and any(token in LOW_IMPACT_INGREDIENTS for token in tokens):
        return 0.25

    return 1.0


def calc_match(meal_detail: dict, fridge: list[str]) -> tuple[int, list[dict], list[dict]]:
    recipe_ingredients = extract_ingredients(meal_detail)
    if not recipe_ingredients:
        return 0, [], []

    have = []
    missing = []
    matched_weight = 0.0
    total_weight = 0.0

    for ingredient in recipe_ingredients:
        weight = ingredient_weight(ingredient["name"])
        total_weight += weight

        if any(is_match(ingredient["name"], fridge_item) for fridge_item in fridge):
            have.append(ingredient)
            matched_weight += weight
        else:
            missing.append(ingredient)

    pct = round(matched_weight / total_weight * 100) if total_weight else 0
    return pct, have, missing


def target_fit_score(meal_detail: dict, target: str) -> int:
    if not target:
        return 0

    area = meal_detail.get("strArea") or ""
    category = meal_detail.get("strCategory") or ""
    tags = meal_detail.get("strTags") or ""
    meal_name = meal_detail.get("strMeal") or ""
    ingredients = " ".join(item["name"] for item in extract_ingredients(meal_detail))
    search_blob = " ".join([area, category, tags, meal_name, ingredients]).lower()

    score = 0
    target_lower = target.lower()

    if area.lower() == target_lower:
        score += 5
    if category.lower() == target_lower:
        score += 4
    if target_lower in search_blob:
        score += 2

    for keyword in FLAVOR_KEYWORDS.get(target, []):
        if keyword.lower() in search_blob:
            score += 1

    if target == "Vegetarian":
        animal_terms = {"chicken", "beef", "pork", "lamb", "fish", "shrimp", "bacon", "ham"}
        ingredient_tokens = set()
        for ingredient in extract_ingredients(meal_detail):
            ingredient_tokens.update(tokenize(ingredient["name"]))
        if not ingredient_tokens.intersection(animal_terms):
            score += 2

    return score


def recipe_sort_key(recipe: dict) -> tuple:
    return (
        recipe["completion_pct"],
        recipe["target_score"],
        len(recipe["have"]),
        -len(recipe["missing"]),
        recipe["source_hits"],
    )


def discover_recipes(fridge: list[str], target: str | None = None, max_recipes: int = 18) -> list[dict]:
    fridge = [item.strip().lower() for item in fridge if item.strip()]
    target = (target or "").strip()

    recipe_summaries: dict[str, dict] = {}
    source_hits: Counter = Counter()

    for ingredient in fridge:
        for meal in search_by_ingredient(ingredient):
            meal_id = meal["idMeal"]
            recipe_summaries[meal_id] = meal
            source_hits[meal_id] += 2

    if target in CUISINES:
        for meal in search_by_area(target):
            meal_id = meal["idMeal"]
            recipe_summaries[meal_id] = meal
            source_hits[meal_id] += 3

    category = CATEGORY_TARGETS.get(target)
    if category:
        for meal in search_by_category(category):
            meal_id = meal["idMeal"]
            recipe_summaries[meal_id] = meal
            source_hits[meal_id] += 3

    if not recipe_summaries:
        return []

    ranked_ids = [
        meal_id
        for meal_id, _score in sorted(
            source_hits.items(),
            key=lambda pair: (-pair[1], pair[0]),
        )
    ][: max(max_recipes * 3, 24)]

    details = fetch_recipes_parallel(ranked_ids)

    recipes = []
    for detail in details:
        completion_pct, have, missing = calc_match(detail, fridge)
        score = target_fit_score(detail, target)

        if fridge and completion_pct == 0 and target and score == 0:
            continue

        recipes.append(
            {
                "id": detail["idMeal"],
                "name": detail["strMeal"],
                "area": detail.get("strArea") or "Unknown",
                "category": detail.get("strCategory") or "Unknown",
                "thumbnail": detail.get("strMealThumb") or "",
                "instructions": detail.get("strInstructions") or "",
                "youtube": detail.get("strYoutube") or "",
                "source": detail.get("strSource") or "",
                "ingredients": extract_ingredients(detail),
                "have": have,
                "missing": missing,
                "completion_pct": completion_pct,
                "target_score": score,
                "source_hits": source_hits[detail["idMeal"]],
            }
        )

    recipes.sort(key=recipe_sort_key, reverse=True)

    if target:
        target_matched = [recipe for recipe in recipes if recipe["target_score"] > 0]
        if target_matched:
            recipes = target_matched + [recipe for recipe in recipes if recipe["target_score"] == 0]

    return recipes[:max_recipes]


def get_ingredient_frequency(recipes: list[dict]) -> pd.DataFrame:
    ingredient_frequency = defaultdict(int)

    for recipe in recipes:
        for item in recipe.get("have", []) + recipe.get("missing", []):
            ingredient_frequency[item["name"]] += 1

    if not ingredient_frequency:
        return pd.DataFrame(columns=["Ingredient", "Appears in # recipes"])

    frame = pd.DataFrame(
        ingredient_frequency.items(),
        columns=["Ingredient", "Appears in # recipes"],
    )
    return frame.sort_values("Appears in # recipes", ascending=False).reset_index(drop=True)


def build_rankings_frame(recipes: list[dict]) -> pd.DataFrame:
    rows = []
    for index, recipe in enumerate(recipes, start=1):
        rows.append(
            {
                "Rank": index,
                "Recipe": recipe["name"],
                "Cuisine": recipe["area"],
                "Category": recipe["category"],
                "Completion %": recipe["completion_pct"],
                "Have": len(recipe["have"]),
                "Missing": len(recipe["missing"]),
                "Missing ingredients": ", ".join(item["name"] for item in recipe["missing"][:6]) or "None",
            }
        )

    return pd.DataFrame(rows)


def build_shopping_list(recipes: list[dict]) -> list[dict]:
    shopping: dict[str, dict] = {}

    for recipe in recipes:
        for item in recipe["missing"]:
            key = canonical_ingredient_name(item["name"]) or item["name"]
            entry = shopping.setdefault(
                key,
                {
                    "ingredient": item["name"],
                    "measures": set(),
                    "recipes": set(),
                },
            )
            if item["measure"]:
                entry["measures"].add(item["measure"])
            entry["recipes"].add(recipe["name"])

    compiled = []
    for item in shopping.values():
        compiled.append(
            {
                "Ingredient": item["ingredient"].title(),
                "Quantity / notes": ", ".join(sorted(item["measures"])) or "Check recipe details",
                "Needed for": ", ".join(sorted(item["recipes"])),
                "Recipe count": len(item["recipes"]),
            }
        )

    return sorted(compiled, key=lambda row: (-row["Recipe count"], row["Ingredient"]))


def _dot_id(prefix: str, value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return f"{prefix}_{slug or 'node'}"


def shorten_label(value: str, max_chars: int = 20) -> str:
    value = value.strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def _dot_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_network_dot(recipes: list[dict], fridge: list[str], max_recipes: int = 6, max_ingredients: int = 16) -> str:
    selected_recipes = recipes[:max_recipes]
    fridge_set = set(fridge)
    ingredient_counter: Counter = Counter()

    for recipe in selected_recipes:
        for item in recipe["have"] + recipe["missing"]:
            ingredient_counter[item["name"]] += 1

    top_ingredients = {
        ingredient
        for ingredient, _count in ingredient_counter.most_common(max_ingredients)
    }

    lines = [
        "graph recipe_network {",
        '  rankdir="LR";',
        '  graph [bgcolor="transparent", overlap=false, splines=true];',
        '  node [fontname="Helvetica"];',
    ]

    for ingredient in sorted(top_ingredients):
        in_fridge = any(is_match(ingredient, fridge_item) for fridge_item in fridge_set)
        fill = "#d9f99d" if in_fridge else "#fde68a"
        lines.append(
            f'  "{_dot_id("ing", ingredient)}" [label="{_dot_label(ingredient.title())}", shape=ellipse, style="filled", fillcolor="{fill}", color="#475569"];'
        )

    for recipe in selected_recipes:
        recipe_id = _dot_id("recipe", recipe["name"])
        label = _dot_label(f'{recipe["name"]}\\n{recipe["completion_pct"]}% ready')
        lines.append(
            f'  "{recipe_id}" [label="{label}", shape=box, style="rounded,filled", fillcolor="#bfdbfe", color="#1d4ed8"];'
        )
        for item in recipe["have"] + recipe["missing"]:
            if item["name"] in top_ingredients:
                lines.append(f'  "{_dot_id("ing", item["name"])}" -- "{recipe_id}";')

    lines.append("}")
    return "\n".join(lines)


def build_interactive_network_html(
    recipes: list[dict],
    fridge: list[str],
    selected_recipe_id: str,
    height: int = 720,
) -> str:
    selected_recipe = next(
        (recipe for recipe in recipes if recipe["id"] == selected_recipe_id),
        recipes[0] if recipes else None,
    )
    fridge_items = fridge or []
    selected_ingredient_keys = {
        canonical_ingredient_name(item["name"]) or item["name"]
        for item in (selected_recipe or {}).get("ingredients", [])
    }

    ingredient_nodes: dict[str, dict] = {}
    edge_map: dict[tuple[str, str], dict] = {}

    for recipe in recipes:
        recipe_ingredient_ids = []

        for ingredient in recipe["ingredients"]:
            key = canonical_ingredient_name(ingredient["name"]) or ingredient["name"]
            node = ingredient_nodes.setdefault(
                key,
                {
                    "id": f"ingredient_{_dot_id('ing', key)}",
                    "label": shorten_label(ingredient["name"].title(), 20),
                    "shape": "dot",
                    "count": 0,
                    "selected": False,
                    "in_fridge": False,
                    "recipes": set(),
                },
            )
            node["count"] += 1
            node["selected"] = node["selected"] or key in selected_ingredient_keys
            node["in_fridge"] = node["in_fridge"] or any(
                is_match(ingredient["name"], fridge_item) for fridge_item in fridge_items
            )
            node["recipes"].add(recipe["name"])
            recipe_ingredient_ids.append((key, node["id"]))

        ordered_ids = []
        seen_ids = set()
        for _key, node_id in recipe_ingredient_ids:
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                ordered_ids.append(node_id)

        for left_id, right_id in zip(ordered_ids, ordered_ids[1:]):
            edge = edge_map.setdefault(
                tuple(sorted((left_id, right_id))),
                {
                    "from": left_id,
                    "to": right_id,
                    "count": 0,
                    "selected": False,
                },
            )
            edge["count"] += 1
            if recipe["id"] == selected_recipe_id:
                edge["selected"] = True

    ingredient_node_list = []
    for node in ingredient_nodes.values():
        if node["selected"]:
            background = "#ef4444"
            border = "#b91c1c"
        elif node["in_fridge"]:
            background = "#d9f99d"
            border = "#65a30d"
        else:
            background = "rgba(255,255,255,0.95)"
            border = "#cbd5e1"

        ingredient_node_list.append(
            {
                "id": node["id"],
                "label": node["label"],
                "shape": "dot",
                "size": min(14 + node["count"] * 2.2, 24),
                "font": {
                    "size": 17,
                    "color": "#111111",
                    "face": "Avenir Next, Trebuchet MS, sans-serif",
                    "vadjust": 0,
                },
                "color": {
                    "background": background,
                    "border": border,
                    "highlight": {
                        "background": background,
                        "border": border,
                    },
                },
                "borderWidth": 3,
            }
        )

    edges = []
    for edge in edge_map.values():
        edges.append(
            {
                "from": edge["from"],
                "to": edge["to"],
                "color": "#fca5a5" if edge["selected"] else "rgba(148, 163, 184, 0.22)",
                "width": min(1 + edge["count"] * 0.45, 3.2) if edge["selected"] else min(0.7 + edge["count"] * 0.22, 1.6),
                "selectionWidth": 3,
                "hoverWidth": 2,
                "smooth": False,
            }
        )

    nodes = ingredient_node_list
    options = {
        "autoResize": True,
        "height": f"{height}px",
        "width": "100%",
        "physics": {
            "enabled": True,
            "barnesHut": {
                "gravitationalConstant": -2500,
                "springLength": 150,
                "springConstant": 0.035,
                "damping": 0.22,
            },
            "stabilization": {
                "enabled": True,
                "iterations": 260,
                "updateInterval": 25,
            },
        },
        "interaction": {
            "dragNodes": True,
            "dragView": True,
            "zoomView": True,
            "hover": False,
            "multiselect": False,
        },
        "nodes": {
            "shadow": False,
        },
        "edges": {
            "smooth": False,
            "selectionWidth": 0,
        },
    }

    return f"""
    <div id="recipe-network" style="height:{height}px; width:100%; background:transparent; border-radius:20px;"></div>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script>
      const container = document.getElementById("recipe-network");
      const nodes = new vis.DataSet({json.dumps(nodes)});
      const edges = new vis.DataSet({json.dumps(edges)});
      const data = {{ nodes, edges }};
      const options = {json.dumps(options)};
      new vis.Network(container, data, options);
    </script>
    """


def pct_color(pct: int) -> str:
    if pct >= 80:
        return "🟢"
    if pct >= 60:
        return "🟡"
    if pct >= 40:
        return "🟠"
    return "🔴"
