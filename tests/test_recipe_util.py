"""Offline tests for recipe id parsing and Markdown."""

from ica_cli.recipe_util import recipe_to_markdown, resolve_recipe_id


def test_resolve_numeric() -> None:
    assert resolve_recipe_id("712859") == 712859


def test_resolve_slug() -> None:
    assert resolve_recipe_id("busenkel-broccolisoppa-712859") == 712859


def test_resolve_url() -> None:
    url = "https://www.ica.se/recept/busenkel-broccolisoppa-712859/"
    assert resolve_recipe_id(url) == 712859


def test_recipe_markdown_minimal() -> None:
    md = recipe_to_markdown(
        {
            "Title": "Test",
            "Portions": 4,
            "PreambleHTML": "<p>Hello</p>",
            "IngredientGroups": [
                {"GroupName": "A", "Ingredients": "<ul><li>x</li></ul>"},
            ],
        }
    )
    assert "# Test" in md
    assert "Hello" in md
    assert "A" in md
