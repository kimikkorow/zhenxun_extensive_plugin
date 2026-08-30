from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest


RECOMMEND_PATH = (
    Path(__file__).parents[1]
    / "genshin_role_info"
    / "data_source"
    / "damage"
    / "recommend.py"
)


def _load_recommend_module():
    package_name = "genshin_damage_recommend_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(RECOMMEND_PATH.parent)]
    sys.modules[package_name] = package
    module_name = f"{package_name}.recommend"
    spec = importlib.util.spec_from_file_location(module_name, RECOMMEND_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _TextValues(tuple):
    def __new__(cls, values):
        instance = super().__new__(cls, values)
        instance.is_text = True
        return instance


def test_get_damage_target_rejects_marked_text_rows(monkeypatch) -> None:
    recommend = _load_recommend_module()
    monkeypatch.setattr(
        recommend,
        "get_role_dmg",
        lambda _data: {"说明": _TextValues(("11.7%",))},
    )

    with pytest.raises(recommend.DamageTargetError, match="不是数值伤害"):
        recommend.get_damage_target({}, 1)
