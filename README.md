# FridgeChef
FridgeChef is a Streamlit project that uses the free [TheMealDB](https://www.themealdb.com/api.php) recipe API to help users decide what to cook from the ingredients already in their fridge.

## Project idea

The app treats cooking like a small ingredient-recipe network:

- Nodes: ingredients and recipes
- Edges: an ingredient connects to the recipes that use it

This makes it easy to answer questions such as:

- What can I cook right now?
- Which recipes am I closest to completing?
- Which missing ingredients matter most?
- What should I buy for one or more target dishes?

## Four modes of interaction

1. Smart Search
   Enter fridge ingredients, click suggested ingredient pills, and choose a target cuisine or flavor profile.
2. Ingredient Network
   Visualize how ingredient nodes connect to top recipe matches.
3. Recipe Rankings
   Rank recipes by completion percentage and inspect missing ingredients.
4. Shopping Planner
   Select target recipes and generate a combined shopping list of missing ingredients.

## Data source

- API: TheMealDB
- Access: free and beginner-friendly
- Data used: recipe names, cuisines, categories, ingredients, instructions, and media links

## How to run

1. Install dependencies

```bash
pip install -r requirements.txt
```

2. Start the Streamlit app

```bash
streamlit run streamlit_app.py
```

## Notes

- The app pulls live data from TheMealDB, so it needs internet access when running.
- Flavor targets such as `Spicy` or `Creamy` are treated as ranking hints on top of the recipe and ingredient data returned by the API.
>>>>>>> c369f3a (Initial commit for FridgeChef)
