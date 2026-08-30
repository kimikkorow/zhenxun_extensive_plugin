import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


PLUGIN_PATH = Path(__file__).parents[1] / "starrail_role_info"
MODULE_PATH = PLUGIN_PATH / "utils" / "card_utils.py"


def _load_card_utils(monkeypatch):
    package_name = "starrail_card_utils_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(PLUGIN_PATH)]
    utils_package = types.ModuleType(f"{package_name}.utils")
    utils_package.__path__ = [str(PLUGIN_PATH / "utils")]
    json_utils = types.ModuleType(f"{package_name}.utils.json_utils")

    def load_json(path, encoding="utf-8"):
        return json.loads(Path(path).read_text(encoding=encoding))

    json_utils.load_json = load_json
    json_utils.save_json = lambda data, path=None, encoding="utf-8": None
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setitem(sys.modules, utils_package.__name__, utils_package)
    monkeypatch.setitem(sys.modules, json_utils.__name__, json_utils)

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.utils.card_utils", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rin_data():
    return {
        "avatarId": 1508,
        "level": 80,
        "promotion": 6,
        "rank": 0,
        "equipment": {"tid": 23061, "level": 80, "promotion": 6, "rank": 1},
        "skillTreeList": [
            {"pointId": 1508001, "level": 6},
            {"pointId": 1508002, "level": 10},
            {"pointId": 1508003, "level": 10},
            {"pointId": 1508004, "level": 10},
        ],
        "relicList": [
            {
                "tid": 61221,
                "level": 15,
                "mainAffixId": 1,
                "subAffixList": [
                    {"affixId": 4, "cnt": 1},
                    {"affixId": 8, "cnt": 4, "step": 4},
                    {"affixId": 9, "cnt": 2, "step": 3},
                    {"affixId": 10, "cnt": 1, "step": 2},
                ],
            },
            {
                "tid": 61222,
                "level": 15,
                "mainAffixId": 1,
                "subAffixList": [
                    {"affixId": 4, "cnt": 2, "step": 3},
                    {"affixId": 7, "cnt": 3, "step": 1},
                    {"affixId": 8, "cnt": 1},
                    {"affixId": 9, "cnt": 2, "step": 2},
                ],
            },
            {
                "tid": 61203,
                "level": 15,
                "mainAffixId": 4,
                "subAffixList": [
                    {"affixId": 1, "cnt": 1},
                    {"affixId": 5, "cnt": 5, "step": 3},
                    {"affixId": 7, "cnt": 1, "step": 1},
                    {"affixId": 9, "cnt": 2, "step": 3},
                ],
            },
            {
                "tid": 61204,
                "level": 15,
                "mainAffixId": 2,
                "subAffixList": [
                    {"affixId": 5, "cnt": 4, "step": 3},
                    {"affixId": 8, "cnt": 1, "step": 1},
                    {"affixId": 9, "cnt": 2, "step": 3},
                    {"affixId": 11, "cnt": 1},
                ],
            },
            {
                "tid": 63095,
                "level": 15,
                "mainAffixId": 9,
                "subAffixList": [
                    {"affixId": 5, "cnt": 2, "step": 4},
                    {"affixId": 6, "cnt": 1},
                    {"affixId": 7, "cnt": 3, "step": 1},
                    {"affixId": 8, "cnt": 2, "step": 1},
                ],
            },
            {
                "tid": 63096,
                "level": 15,
                "mainAffixId": 4,
                "subAffixList": [
                    {"affixId": 4, "cnt": 3, "step": 4},
                    {"affixId": 6, "cnt": 1},
                    {"affixId": 8, "cnt": 2, "step": 3},
                    {"affixId": 9, "cnt": 2},
                ],
            },
        ],
    }


def test_two_piece_set_does_not_apply_four_piece_crit_rate(monkeypatch) -> None:
    card_utils = _load_card_utils(monkeypatch)
    player = card_utils.PlayerInfo.__new__(card_utils.PlayerInfo)
    player.roles = {}

    assert player.set_role(_rin_data())

    properties = player.roles["远坂凛"]["属性"]
    assert properties["暴击率"] == pytest.approx(0.95236)
    assert properties["基础暴击率"] + properties["暴击率"] == pytest.approx(1.00236)
