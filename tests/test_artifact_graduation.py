import ast
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "module_path",
    [
        "starrail_role_info/data_source/draw_role_card.py",
        "zenlesszonezero_role_info/data_source/draw_role_card.py",
    ],
)
def test_big_graduation_includes_ace_star(module_path: str) -> None:
    tree = ast.parse((PLUGIN_ROOT / module_path).read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "BIG_GRADUATION_RANKS"
            for target in node.targets
        )
    )

    assert ast.literal_eval(assignment.value) == {"ACE", "ACE*"}

    draw_role_card = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "draw_role_card"
    )
    assert any(
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "artifact_score"
        and any(isinstance(operator, ast.In) for operator in node.ops)
        and any(
            isinstance(comparator, ast.Name)
            and comparator.id == "BIG_GRADUATION_RANKS"
            for comparator in node.comparators
        )
        for node in ast.walk(draw_role_card)
    )


def test_genshin_uses_ace_star_as_big_graduation() -> None:
    module_path = PLUGIN_ROOT / "genshin_role_info/data_source/draw_role_card.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    draw_role_card = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "draw_role_card"
    )
    conditions = {
        ast.unparse(node.test)
        for node in ast.walk(draw_role_card)
        if isinstance(node, ast.IfExp)
    }

    assert "artifact_score == 'ACE*'" in conditions
    assert "artifact_score == 'ACE'" in conditions
