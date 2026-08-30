import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


PLUGIN_PATH = Path(__file__).parents[1] / "zenlesszonezero_role_info"
MODULE_PATH = PLUGIN_PATH / "utils" / "card_utils.py"


def _load_card_utils(monkeypatch):
    package_name = "zenlesszonezero_card_utils_test"
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


def _six_piece_set_data():
    return {
        "Id": 1011,
        "Level": 1,
        "PromotionLevel": 1,
        "CoreSkillEnhancement": 0,
        "SkillLevelList": [],
        "TalentLevel": 0,
        "Weapon": None,
        "EquippedList": [
            {
                "Slot": slot,
                "Equipment": {
                    "Id": 31020 + slot,
                    "Level": 0,
                    "MainPropertyList": [{"PropertyId": 11101, "PropertyValue": 0}],
                    "RandomPropertyList": [],
                },
            }
            for slot in range(1, 7)
        ],
    }


def test_six_piece_set_bonus_is_applied_once(monkeypatch) -> None:
    card_utils = _load_card_utils(monkeypatch)
    player = card_utils.PlayerInfo.__new__(card_utils.PlayerInfo)
    player.roles = {}

    player.set_role(_six_piece_set_data())

    properties = player.roles["安比"]["属性"]
    assert properties["额外暴击率"] == pytest.approx(800)
