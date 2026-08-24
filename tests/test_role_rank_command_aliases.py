import ast
import re
from pathlib import Path

import pytest


PLUGIN_ROOT = Path(__file__).parents[1]


def get_role_rank_pattern(module_path: str) -> re.Pattern[str]:
    tree = ast.parse((PLUGIN_ROOT / module_path).read_text(encoding="utf-8"))
    assignment = next(
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "role_rank"
            for target in node.targets
        )
    )
    call = assignment.value
    assert isinstance(call, ast.Call)
    pattern = ast.literal_eval(call.args[0])
    return re.compile(pattern)


@pytest.mark.parametrize(
    "module_path, command, expected_groups",
    [
        (
            "genshin_role_info/__init__.py",
            "胡桃评分排行",
            ("胡桃", "评分", ""),
        ),
        (
            "genshin_role_info/__init__.py",
            "胡桃评分榜单",
            ("胡桃", "评分", ""),
        ),
        (
            "genshin_role_info/__init__.py",
            "胡桃伤害排行5",
            ("胡桃", "伤害", "5"),
        ),
        (
            "genshin_role_info/__init__.py",
            "胡桃伤害榜单5",
            ("胡桃", "伤害", "5"),
        ),
        (
            "starrail_role_info/__init__.py",
            "希儿评分榜单",
            ("希儿", "评分", ""),
        ),
        (
            "starrail_role_info/__init__.py",
            "希儿伤害榜单3",
            ("希儿", "伤害", "3"),
        ),
        (
            "zenlesszonezero_role_info/__init__.py",
            "星见雅评分排行",
            ("星见雅",),
        ),
        (
            "zenlesszonezero_role_info/__init__.py",
            "星见雅评分榜单",
            ("星见雅",),
        ),
    ],
)
def test_role_rank_accepts_rank_and_list_suffixes(
    module_path: str,
    command: str,
    expected_groups: tuple[str, ...],
) -> None:
    match = get_role_rank_pattern(module_path).fullmatch(command)

    assert match is not None
    assert match.groups() == expected_groups


@pytest.mark.parametrize(
    "module_path, command",
    [
        ("genshin_role_info/__init__.py", "胡桃评分榜单额外内容"),
        ("starrail_role_info/__init__.py", "希儿伤害榜单3额外内容"),
        ("zenlesszonezero_role_info/__init__.py", "星见雅伤害榜单"),
    ],
)
def test_role_rank_rejects_unsupported_commands(
    module_path: str,
    command: str,
) -> None:
    assert get_role_rank_pattern(module_path).fullmatch(command) is None
