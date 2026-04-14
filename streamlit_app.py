import altair as alt
import streamlit as st
import streamlit.components.v1 as components

import utils


st.set_page_config(
    page_title="FridgeChef",
    page_icon="🍳",
    layout="wide",
)


APP_VIEWS = [
    "Smart Search",
    "Ingredient Network",
    "Recipe Rankings",
    "Shopping Planner",
]


def set_active_view(view: str) -> None:
    st.session_state.active_view = view


def init_state() -> None:
    defaults = {
        "active_view": "Smart Search",
        "fridge_items": [],
        "target_profile": "",
        "network_selected_recipe": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_ingredients(raw_text: str) -> None:
    for item in utils.parse_ingredient_text(raw_text):
        if item not in st.session_state.fridge_items:
            st.session_state.fridge_items.append(item)


def toggle_target(profile: str) -> None:
    current = st.session_state.target_profile
    st.session_state.target_profile = "" if current == profile else profile


def render_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 244, 214, 0.95), transparent 35%),
                linear-gradient(135deg, #fffaf0 0%, #f7efe3 50%, #f4e4c5 100%);
            color: #2f241f;
            font-family: "Avenir Next", "Trebuchet MS", sans-serif;
        }
        .hero-card {
            padding: 1.25rem 1.4rem;
            border-radius: 22px;
            background: rgba(255, 252, 246, 0.9);
            border: 1px solid rgba(120, 73, 43, 0.15);
            box-shadow: 0 16px 40px rgba(120, 73, 43, 0.08);
            margin-bottom: 1rem;
        }
        .small-note {
            color: #6b4f3b;
            font-size: 0.95rem;
        }
        div.stButton > button {
            border-radius: 999px;
            border: 1px solid rgba(120, 73, 43, 0.18);
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 252, 246, 0.82);
            border: 1px solid rgba(120, 73, 43, 0.12);
            border-radius: 18px;
            padding: 0.5rem 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
        st.markdown(
            """
        <div style="text-align: left; padding: 1rem 0;">
            <div style="display: flex; align-items: baseline; justify-content: flex-start; gap: 0px; flex-wrap: wrap;">
                <h1 style="margin: 0; padding: 0; line-height: 1; font-size: 2.5rem;">
                    🧑‍🍳 Fridge<span style="color: #2e7d32;">Chef</span>
                </h1>
                <span style="font-size: 1.1rem; color: #666;">
                    Turn what you have into what you crave
                </span>
            </div>
            <p style="margin-top: 0.8rem; font-size: 1.2rem; color: #444; max-width: 1000px;">
                Turn Fridge Leftovers Into Recipe Ideas, Ingredient Networks,
                Ranked Matches, and a Practical Shopping Plan.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )



def render_nav() -> None:
    cols = st.columns(4)
    for column, view in zip(cols, APP_VIEWS):
        with column:
            st.button(
                view,
                key=f"nav_{view}",
                use_container_width=True,
                type="primary" if st.session_state.active_view == view else "secondary",
                on_click=set_active_view,
                args=(view,),
            )


def render_fridge_input() -> None:
    st.subheader("What's in your fridge?")
    with st.form("ingredient_form", clear_on_submit=True):
        raw_text = st.text_input(
            "Add fridge ingredients",
            placeholder="e.g. chicken, onion, garlic",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Add ingredients")
    if submitted and raw_text.strip():
        add_ingredients(raw_text)

    st.caption("Quick add ingredients")
    columns = st.columns(6)
    for index, ingredient in enumerate(utils.SUGGESTION_INGREDIENTS):
        with columns[index % 6]:
            if st.button(ingredient.title(), key=f"pill_{ingredient}", use_container_width=True):
                add_ingredients(ingredient)

    if st.session_state.fridge_items:
        st.markdown("**Your fridge now**")
        tag_cols = st.columns(6)
        for index, item in enumerate(st.session_state.fridge_items):
            with tag_cols[index % 6]:
                if st.button(f"✕ {item.title()}", key=f"remove_{item}", use_container_width=True):
                    st.session_state.fridge_items.remove(item)
                    st.rerun()
    else:
        st.info("Add at least one ingredient to start matching recipes.")


def render_target_selector() -> None:
    st.markdown("**Target cuisine / flavor**")
    st.caption("Pick one vibe to nudge the search. Click again to clear it.")
    columns = st.columns(4)
    for index, profile in enumerate(utils.TARGET_PROFILES):
        with columns[index % 4]:
            active = st.session_state.target_profile == profile
            if st.button(
                profile,
                key=f"target_{profile}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                toggle_target(profile)

    current = st.session_state.target_profile or "Any"
    st.markdown(f"Current target: `{current}`")


def get_recipe_results() -> list[dict]:
    return utils.discover_recipes(
        st.session_state.fridge_items,
        st.session_state.target_profile,
    )


def render_horizontal_frequency_chart(frequency_data) -> None:
    if frequency_data.empty:
        return

    chart_data = frequency_data.head(8).copy()
    chart = (
        alt.Chart(chart_data)
        .mark_bar(size=18, cornerRadiusEnd=6, color="#c96f3b")
        .encode(
            x=alt.X("Appears in # recipes:Q", title="Recipe count"),
            y=alt.Y(
                "Ingredient:N",
                sort="-x",
                title=None,
                axis=alt.Axis(
                    labelLimit=180,
                    labelFontSize=16
                ),
            ),
            tooltip=["Ingredient", "Appears in # recipes"],
        )
        .properties(
            width=600,
            height=min(450, 36 * len(chart_data)),
            background="rgba(0,0,0,0)",
        )
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False)
    )

    st.altair_chart(chart, use_container_width=False)


def render_recipe_card(recipe: dict) -> None:
    with st.container(border=True):
        image_col, content_col = st.columns([1, 1.8], vertical_alignment="top")
        with image_col:
            if recipe["thumbnail"]:
                st.image(recipe["thumbnail"], use_container_width=True)
        with content_col:
            st.markdown(f"### {recipe['name']}")
            st.caption(f"{recipe['area']} • {recipe['category']}")
            st.markdown(
                f"{utils.pct_color(recipe['completion_pct'])} **{recipe['completion_pct']}% ready**"
            )
            st.markdown(
                f"**You have:** {', '.join(item['name'] for item in recipe['have'][:6]) or 'Nothing matched yet'}"
            )
            st.markdown(
                f"**Still missing:** {', '.join(item['name'] for item in recipe['missing'][:6]) or 'Nothing'}"
            )
            links = []
            if recipe["source"]:
                links.append(f"[Source]({recipe['source']})")
            if recipe["youtube"]:
                links.append(f"[Video]({recipe['youtube']})")
            if links:
                st.markdown(" | ".join(links))


def render_smart_search(recipes: list[dict]) -> None:
    left, right = st.columns([1.4, 0.9], vertical_alignment="top")
    with left:
        render_fridge_input()
        st.divider()
        render_target_selector()
    with right:
        st.subheader("Search Snapshot")
        st.metric("Ingredients in fridge", len(st.session_state.fridge_items))
        st.metric("Target selected", st.session_state.target_profile or "Any")
        st.metric("Recipes matched", len(recipes))
        if st.session_state.target_profile and st.session_state.target_profile not in utils.CUISINES:
            st.caption(
                "Flavor tags work as ranking hints. They work best after you add at least one fridge ingredient."
            )

    st.divider()

    if not st.session_state.fridge_items and not st.session_state.target_profile:
        st.info("Use the input box or quick-add buttons above to start exploring recipes.")
        return

    if not recipes:
        st.warning("No recipes matched this combination yet. Try adding another ingredient or clearing the target.")
        return

    st.subheader("Best Matches")
    card_cols = st.columns(2)
    for index, recipe in enumerate(recipes[:6]):
        with card_cols[index % 2]:
            render_recipe_card(recipe)

    frequency = utils.get_ingredient_frequency(recipes).head(10)
    if not frequency.empty:
        st.subheader("Popular Ingredients Across Matches")
        render_horizontal_frequency_chart(frequency)


def render_ingredient_network(recipes: list[dict]) -> None:
    st.subheader("Ingredient Network")
    st.caption("Drag nodes to rearrange them, or use your mouse wheel to zoom in and out.")

    if not recipes:
        st.info("Add fridge ingredients on Smart Search first, then come back to see the network.")
        return

    recipe_by_id = {recipe["id"]: recipe for recipe in recipes}
    recipe_ids = list(recipe_by_id.keys())
    available_ids = set(recipe_ids)
    if st.session_state.network_selected_recipe not in available_ids:
        st.session_state.network_selected_recipe = recipes[0]["id"]

    selected_recipe_id = st.selectbox(
        "Highlight recipe",
        options=recipe_ids,
        index=recipe_ids.index(st.session_state.network_selected_recipe),
        format_func=lambda recipe_id: recipe_by_id[recipe_id]["name"],
    )
    st.session_state.network_selected_recipe = selected_recipe_id

    info_cols = st.columns(3)
    info_cols[0].markdown("`Red` = ingredients in the selected recipe")
    info_cols[1].markdown("`Green` = ingredients already in your fridge")
    info_cols[2].markdown("`Lines` = ingredients that appear together in a recipe")

    components.html(
        utils.build_interactive_network_html(
            recipes,
            st.session_state.fridge_items,
            st.session_state.network_selected_recipe,
        ),
        height=760,
    )

    frequency = utils.get_ingredient_frequency(recipes).head(12)
    if not frequency.empty:
        st.subheader("Most Connected Ingredients")
        st.dataframe(frequency, use_container_width=True, hide_index=True)


def render_recipe_rankings(recipes: list[dict]) -> None:
    st.subheader("Recipe Rankings")
    st.caption('Recipes are ranked by "completion %" so users can see what they almost have.')

    if not recipes:
        st.info("Start from Smart Search to generate recipe candidates.")
        return

    rankings = utils.build_rankings_frame(recipes)
    st.dataframe(rankings, use_container_width=True, hide_index=True)

    for recipe in recipes[:5]:
        with st.expander(f"{recipe['name']} • {recipe['completion_pct']}% ready"):
            st.markdown(f"**Have:** {', '.join(item['name'] for item in recipe['have']) or 'None'}")
            st.markdown(f"**Missing:** {', '.join(item['name'] for item in recipe['missing']) or 'None'}")
            st.markdown(recipe["instructions"][:320] + ("..." if len(recipe["instructions"]) > 320 else ""))


def render_shopping_planner(recipes: list[dict]) -> None:
    st.subheader("Shopping Planner")
    st.caption("Select one or more target recipes and the app will combine the missing ingredients into one list.")

    if not recipes:
        st.info("Generate a recipe list from Smart Search first, then build a shopping plan here.")
        return

    labels = [f"{recipe['name']} ({recipe['completion_pct']}%)" for recipe in recipes]
    lookup = dict(zip(labels, recipes))
    defaults = labels[:1]

    selected_labels = st.multiselect(
        "Target recipes",
        options=labels,
        default=defaults,
        placeholder="Choose recipes to cook this week",
    )

    selected_recipes = [lookup[label] for label in selected_labels]
    if not selected_recipes:
        st.warning("Pick at least one recipe to generate the missing-ingredient list.")
        return

    shopping_list = utils.build_shopping_list(selected_recipes)
    st.metric("Recipes selected", len(selected_recipes))
    st.metric("Items to buy", len(shopping_list))

    st.dataframe(shopping_list, use_container_width=True, hide_index=True)

    for recipe in selected_recipes:
        st.markdown(
            f"- **{recipe['name']}**: missing {', '.join(item['name'] for item in recipe['missing']) or 'nothing'}"
        )


init_state()
render_styles()
render_header()
render_nav()
st.divider()

recipes = get_recipe_results()

if st.session_state.active_view == "Smart Search":
    render_smart_search(recipes)
elif st.session_state.active_view == "Ingredient Network":
    render_ingredient_network(recipes)
elif st.session_state.active_view == "Recipe Rankings":
    render_recipe_rankings(recipes)
else:
    render_shopping_planner(recipes)
