#!/usr/bin/env python3
"""Read-only full-cache audit for the pinned Miao Star Rail damage rules."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import types
from typing import Any, Mapping


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = PLUGIN_ROOT / "user_data" / "player_info"
DEFAULT_MIAO_ROOT = Path("/Users/crazy/PycharmProjects/miao-plugin")
DEFAULT_OUTPUT = Path("/tmp/starrail_miao_damage_audit.json")
EXPECTED_REVISION = "afff386eb6b31bc70a98144c3bbfa884eaf5e621"


def _load_damage_module():
    for name, path in (
        ("starrail_role_info", PLUGIN_ROOT),
        ("starrail_role_info.data_source", PLUGIN_ROOT / "data_source"),
    ):
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    module_name = "starrail_role_info.data_source.sr_damage"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_ROOT / "data_source" / "sr_damage.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载星铁伤害模块")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cache_files(cache_dir: Path) -> list[Path]:
    return sorted(path for path in cache_dir.glob("*.json") if path.is_file())


def _aggregate_hash(files: list[Path], cache_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(cache_dir).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _damage_comparison(
    python_damage: Mapping[str, object],
    javascript_damage: Mapping[str, object],
) -> tuple[list[dict[str, Any]], bool]:
    """Compare damage entries while retaining a title-indexed mapping."""
    rows = []
    equal = True
    for title in dict.fromkeys((*python_damage, *javascript_damage)):
        python_values = python_damage.get(title)
        javascript_values = javascript_damage.get(title)
        numeric_differences: list[float | None] = []
        left = list(python_values) if isinstance(python_values, (list, tuple)) else []
        right = list(javascript_values) if isinstance(javascript_values, (list, tuple)) else []
        for index in range(max(len(left), len(right))):
            try:
                left_number = float(str(left[index]).replace(",", ""))
                right_number = float(str(right[index]).replace(",", ""))
                difference = left_number - right_number
                numeric_differences.append(difference if math.isfinite(difference) else None)
            except (AttributeError, IndexError, TypeError, ValueError):
                numeric_differences.append(None)
        item_equal = left == right
        equal = equal and item_equal
        rows.append(
            {
                "title": title,
                "python": left,
                "javascript": right,
                "mapping": {
                    "title": title,
                    "python": left,
                    "javascript": right,
                },
                "difference": numeric_differences,
                "equal": item_equal,
                "equivalence": "exact_value" if item_equal else "different_value",
            }
        )
    return rows, equal


def _buff_comparison(
    python_buffs: list[str],
    javascript_buffs: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    """Compare Buff text by index and retain additions/removals explicitly."""
    rows = []
    equal = python_buffs == javascript_buffs
    for index in range(max(len(python_buffs), len(javascript_buffs))):
        python_value = python_buffs[index] if index < len(python_buffs) else None
        javascript_value = javascript_buffs[index] if index < len(javascript_buffs) else None
        item_equal = python_value == javascript_value
        rows.append(
            {
                "index": index,
                "python": python_value,
                "javascript": javascript_value,
                "mapping": {
                    "index": index,
                    "python": python_value,
                    "javascript": javascript_value,
                },
                "equal": item_equal,
                "equivalence": "exact_value" if item_equal else "different_value",
            }
        )
    return rows, equal


def _display_equivalence(
    damage_rows: list[dict[str, Any]],
    damage_equal: bool,
    python_buffs: list[str],
    javascript_buffs: list[str],
    buff_equal: bool,
) -> dict[str, Any] | None:
    """Return a narrow, structure-based explanation for harmless display drift.

    The rules intentionally inspect output structure and callback sentinel text,
    never a character name.  A display-only exception is accepted only after
    the other damage values and the applied Buff result have been checked.
    """
    mismatched_damage = [row for row in damage_rows if not row["equal"]]
    matching_damage = [row for row in damage_rows if row["equal"]]

    # A text-only callback can render a zero fallback in Python while the Miao
    # callback exposes a non-finite value as "NaN".  The unit and one-value
    # shape make this narrower than a role-name exception.
    if (
        len(mismatched_damage) == 1
        and all(row["equal"] for row in matching_damage)
        and buff_equal
    ):
        row = mismatched_damage[0]
        if row["python"] == ["0点"] and row["javascript"] == ["NaN点"]:
            return {
                "rule": "nonfinite_text_value_zero_vs_nan",
                "reason": (
                    "单值点数文本回调：Python 的零值与 Miao 的非有限值 NaN 仅造成展示差异；"
                    "其余伤害项和实际 Buff 应用均相等"
                ),
                "evidence": {
                    "title": row["title"],
                    "pythonValue": row["python"],
                    "javascriptValue": row["javascript"],
                    "otherDamageEqual": True,
                    "buffApplicationEqual": True,
                },
            }

    # A non-finite Buff callback is skipped by the runner's data evaluator,
    # leaving its [dmg] placeholder in the title.  Python's zero-value text is
    # equivalent only when the damage result is exactly unchanged and this is
    # the sole Buff difference.
    buff_differences = [
        (index, python_value, javascript_value)
        for index, (python_value, javascript_value) in enumerate(
            zip(python_buffs, javascript_buffs)
        )
        if python_value != javascript_value
    ]
    if damage_equal and len(python_buffs) == len(javascript_buffs) and len(buff_differences) == 1:
        index, python_value, javascript_value = buff_differences[0]
        python_match = re.fullmatch(r"(.*)0%(.*)", python_value)
        javascript_match = re.fullmatch(r"(.*)\[dmg\]%(.*)", javascript_value)
        if (
            python_match
            and javascript_match
            and python_match.group(1) == javascript_match.group(1)
            and python_match.group(2) == javascript_match.group(2)
        ):
            return {
                "rule": "nonfinite_buff_placeholder_zero_vs_token",
                "reason": (
                    "唯一 Buff 回调为非有限值时，Miao 保留 [dmg] 占位符而 Python 展示 0%；"
                    "伤害结果未变且其余 Buff 项相等"
                ),
                "evidence": {
                    "index": index,
                    "pythonValue": python_value,
                    "javascriptValue": javascript_value,
                    "damageApplicationEqual": True,
                    "otherBuffsEqual": True,
                },
            }

    # Buff ordering is presentation-only when the exact multiset and all
    # damage values match.  Keep this structural rule separate from the two
    # non-finite callback rules so it is visible in the audit report.
    if damage_equal and not buff_equal and Counter(python_buffs) == Counter(javascript_buffs):
        return {
            "rule": "buff_order_only",
            "reason": "Buff 文本多重集和伤害结果完全相等，仅输出顺序不同",
            "evidence": {
                "damageApplicationEqual": True,
                "buffMultisetEqual": True,
            },
        }
    return None


def _difference_reason(
    damage_equal: bool,
    buff_equal: bool,
) -> str:
    if not damage_equal and not buff_equal:
        return "damage_and_buff_difference"
    if not damage_equal:
        return "damage_difference"
    if not buff_equal:
        return "buff_difference"
    return "exact"


def _add_cluster(
    clusters: dict[str, dict[str, Any]],
    category: str,
    reason: str,
    item: Mapping[str, object],
    comparison: Mapping[str, object],
) -> None:
    """Collect traceable difference clusters without discarding instances."""
    key = f"{category}:{reason}"
    cluster = clusters.setdefault(
        key,
        {
            "category": category,
            "reason": reason,
            "count": 0,
            "ruleNames": Counter(),
            "titles": Counter(),
            "instances": [],
        },
    )
    cluster["count"] += 1
    rule_name = item.get("ruleName")
    if isinstance(rule_name, str) and rule_name:
        cluster["ruleNames"][rule_name] += 1
    for row in comparison.get("damage", ()):
        if isinstance(row, Mapping) and not row.get("equal"):
            title = row.get("title")
            if isinstance(title, str):
                cluster["titles"][title] += 1
    cluster["instances"].append(
        {
            "file": item.get("file"),
            "cacheName": item.get("cacheName"),
            "ruleName": item.get("ruleName"),
        }
    )


def _finalize_clusters(clusters: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    finalized = []
    for key in sorted(clusters):
        cluster = dict(clusters[key])
        cluster["ruleNames"] = dict(cluster["ruleNames"])
        cluster["titles"] = dict(cluster["titles"])
        finalized.append(cluster)
    return finalized


class JavaScriptOracle:
    def __init__(self, miao_root: Path) -> None:
        environment = os.environ.copy()
        environment["MIAO_PLUGIN_ROOT"] = str(miao_root)
        self.process = subprocess.Popen(
            ["node", str(PLUGIN_ROOT / "tools" / "sr_miao_runner.mjs"), "--ndjson"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    def calculate(self, name: str, profile: Mapping[str, object]) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            return {
                "ok": False,
                "status": "oracle_failed",
                "error": "JavaScript oracle 管道不可用",
            }
        request = json.dumps({"name": name, "profile": profile}, ensure_ascii=False)
        try:
            self.process.stdin.write(request + "\n")
            self.process.stdin.flush()
            response = self.process.stdout.readline()
        except (BrokenPipeError, OSError) as error:
            return {
                "ok": False,
                "status": "oracle_failed",
                "error": f"JavaScript oracle 管道写入失败: {type(error).__name__}: {error}",
            }
        if not response:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            return {
                "ok": False,
                "status": "oracle_failed",
                "error": f"JavaScript oracle 提前退出: {stderr}",
            }
        try:
            value = json.loads(response)
        except (TypeError, ValueError) as error:
            return {
                "ok": False,
                "status": "oracle_failed",
                "error": f"JavaScript oracle 返回非法 JSON: {type(error).__name__}: {error}",
            }
        if not isinstance(value, dict):
            return {
                "ok": False,
                "status": "oracle_failed",
                "error": "JavaScript oracle 返回值不是对象",
            }
        return value

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)


def _miao_revision(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def audit(cache_dir: Path, miao_root: Path) -> dict[str, Any]:
    damage_module = _load_damage_module()
    all_files = _cache_files(cache_dir)
    files = [path for path in all_files if path.name != "qq2uid.json"]
    before_hash = _aggregate_hash(all_files, cache_dir)
    actual_revision = _miao_revision(miao_root)
    if actual_revision != EXPECTED_REVISION:
        raise RuntimeError(
            f"Miao revision 不匹配: 期望 {EXPECTED_REVISION}, 实际 {actual_revision}"
        )

    file_statuses: Counter[str] = Counter()
    instance_statuses: Counter[str] = Counter()
    comparison_statuses: Counter[str] = Counter(
        {
            "damage_equal": 0,
            "buff_equal": 0,
            "display_equivalent": 0,
            "true_difference": 0,
            "oracle_failed": 0,
            "python_failed": 0,
            "no_rule": 0,
            "exact_equal": 0,
        }
    )
    difference_clusters: dict[str, dict[str, Any]] = {}
    instances: list[dict[str, Any]] = []
    oracle = JavaScriptOracle(miao_root)
    try:
        for path in files:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                file_statuses["corrupt"] += 1
                instances.append(
                    {"file": path.name, "status": "corrupt_cache", "error": str(error)}
                )
                continue
            roles = payload.get("角色") if isinstance(payload, Mapping) else None
            if not isinstance(roles, Mapping):
                file_statuses["metadata"] += 1
                continue
            file_statuses["valid"] += 1
            for cache_name, profile in roles.items():
                if not isinstance(profile, Mapping):
                    instance_statuses["corrupt_cache"] += 1
                    instances.append(
                        {"file": path.name, "cacheName": cache_name, "status": "corrupt_cache"}
                    )
                    continue
                python_result = damage_module.get_role_dmg_status(profile)
                status = str(python_result.get("status", "rule_failed"))
                instance_statuses[status] += 1
                item: dict[str, Any] = {
                    "file": path.name,
                    "cacheName": cache_name,
                    "ruleName": python_result.get("name"),
                    "status": status,
                    "python": python_result,
                    "javascript": None,
                }
                rule_name = python_result.get("name")
                if status != "success":
                    category = "no_rule" if status == "no_rule" else "python_failed"
                    comparison_statuses[category] += 1
                    item["comparison"] = {
                        "equal": False,
                        "category": category,
                        "statusEqual": False,
                        "damageEqual": None,
                        "buffEqual": None,
                        "displayEquivalent": False,
                        "trueDifference": False,
                        "equivalenceReason": python_result.get(
                            "error", "Python 未产生可比较结果"
                        ),
                    }
                    _add_cluster(
                        difference_clusters,
                        category,
                        str(item["comparison"]["equivalenceReason"]),
                        item,
                        item["comparison"],
                    )
                    instances.append(item)
                    continue

                if not isinstance(rule_name, str) or not rule_name:
                    comparison_statuses["python_failed"] += 1
                    item["comparison"] = {
                        "equal": False,
                        "category": "python_failed",
                        "statusEqual": False,
                        "damageEqual": None,
                        "buffEqual": None,
                        "displayEquivalent": False,
                        "trueDifference": False,
                        "equivalenceReason": "Python 成功结果缺少规则名称",
                    }
                    _add_cluster(
                        difference_clusters,
                        "python_failed",
                        "missing_rule_name",
                        item,
                        item["comparison"],
                    )
                    instances.append(item)
                    continue

                javascript_result = oracle.calculate(rule_name, profile)
                item["javascript"] = javascript_result
                status_equal = (
                    javascript_result.get("status") == "success"
                    and javascript_result.get("ok") is True
                )
                if not status_equal:
                    comparison_statuses["oracle_failed"] += 1
                    item["comparison"] = {
                        "equal": False,
                        "category": "oracle_failed",
                        "statusEqual": False,
                        "damageEqual": None,
                        "buffEqual": None,
                        "displayEquivalent": False,
                        "trueDifference": False,
                        "pythonStatus": status,
                        "javascriptStatus": javascript_result.get("status"),
                        "equivalenceReason": javascript_result.get(
                            "error", "JavaScript oracle 未产生可比较结果"
                        ),
                    }
                    _add_cluster(
                        difference_clusters,
                        "oracle_failed",
                        str(item["comparison"]["equivalenceReason"]),
                        item,
                        item["comparison"],
                    )
                    instances.append(item)
                    continue

                python_damage = python_result.get("damage")
                javascript_damage = javascript_result.get("damage")
                if not isinstance(python_damage, Mapping) or not isinstance(javascript_damage, Mapping):
                    comparison_statuses["oracle_failed"] += 1
                    item["comparison"] = {
                        "equal": False,
                        "category": "oracle_failed",
                        "statusEqual": True,
                        "damageEqual": None,
                        "buffEqual": None,
                        "displayEquivalent": False,
                        "trueDifference": False,
                        "equivalenceReason": "JavaScript oracle 伤害结果结构错误",
                    }
                    _add_cluster(
                        difference_clusters,
                        "oracle_failed",
                        "invalid_damage_shape",
                        item,
                        item["comparison"],
                    )
                    instances.append(item)
                    continue

                damage_rows, damage_equal = _damage_comparison(
                    python_damage,
                    javascript_damage,
                )
                python_buffs = list(python_result.get("buffs", ()))
                javascript_buffs = javascript_result.get("buffs", [])
                if not isinstance(javascript_buffs, list) or not all(
                    isinstance(value, str) for value in javascript_buffs
                ):
                    comparison_statuses["oracle_failed"] += 1
                    item["comparison"] = {
                        "equal": False,
                        "category": "oracle_failed",
                        "statusEqual": True,
                        "damageEqual": damage_equal,
                        "buffEqual": None,
                        "displayEquivalent": False,
                        "trueDifference": False,
                        "damage": damage_rows,
                        "equivalenceReason": "JavaScript oracle Buff 结果结构错误",
                    }
                    _add_cluster(
                        difference_clusters,
                        "oracle_failed",
                        "invalid_buff_shape",
                        item,
                        item["comparison"],
                    )
                    instances.append(item)
                    continue

                buff_rows, buff_equal = _buff_comparison(python_buffs, javascript_buffs)
                display_info = _display_equivalence(
                    damage_rows,
                    damage_equal,
                    python_buffs,
                    javascript_buffs,
                    buff_equal,
                )
                comparison_equal = damage_equal and buff_equal
                display_equivalent = display_info is not None
                true_difference = not comparison_equal and not display_equivalent
                if damage_equal:
                    comparison_statuses["damage_equal"] += 1
                if buff_equal:
                    comparison_statuses["buff_equal"] += 1
                if comparison_equal:
                    comparison_statuses["exact_equal"] += 1
                elif display_equivalent:
                    comparison_statuses["display_equivalent"] += 1
                elif true_difference:
                    comparison_statuses["true_difference"] += 1
                equivalence_reason = (
                    "exact_value"
                    if comparison_equal
                    else display_info["reason"]
                    if display_info
                    else _difference_reason(damage_equal, buff_equal)
                )
                category = (
                    "exact"
                    if comparison_equal
                    else "display_equivalent"
                    if display_equivalent
                    else "true_difference"
                )
                comparison: dict[str, Any] = {
                    "equal": comparison_equal,
                    "category": category,
                    "statusEqual": status_equal,
                    "damageEqual": damage_equal,
                    "buffEqual": buff_equal,
                    "displayEquivalent": display_equivalent,
                    "trueDifference": true_difference,
                    "damage": damage_rows,
                    "buffs": buff_rows,
                    "pythonBuffs": python_buffs,
                    "javascriptBuffs": javascript_buffs,
                    "equivalenceReason": equivalence_reason,
                }
                if display_info is not None:
                    comparison["displayEquivalence"] = display_info
                item["comparison"] = comparison
                if display_equivalent:
                    _add_cluster(
                        difference_clusters,
                        "display_equivalent",
                        str(display_info["rule"]),
                        item,
                        comparison,
                    )
                elif true_difference:
                    _add_cluster(
                        difference_clusters,
                        "true_difference",
                        _difference_reason(damage_equal, buff_equal),
                        item,
                        comparison,
                    )
                instances.append(item)
    finally:
        oracle.close()

    after_files = _cache_files(cache_dir)
    after_hash = _aggregate_hash(after_files, cache_dir)
    return {
        "schemaVersion": 2,
        "revision": {"expected": EXPECTED_REVISION, "actual": actual_revision},
        "cache": {
            "path": str(cache_dir),
            "fileCount": len(all_files),
            "scannedFileCount": len(files),
            "beforeSha256": before_hash,
            "afterSha256": after_hash,
            "unchanged": before_hash == after_hash and [p.name for p in all_files] == [p.name for p in after_files],
            "fileStatuses": dict(file_statuses),
        },
        "summary": {
            "roleInstanceCount": sum(instance_statuses.values()),
            "instanceStatuses": dict(instance_statuses),
            "comparisons": dict(comparison_statuses),
            "differenceClusters": _finalize_clusters(difference_clusters),
        },
        "instances": instances,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--miao-root", type=Path, default=DEFAULT_MIAO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = audit(args.cache_dir.resolve(), args.miao_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = report["summary"]
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "cache": report["cache"],
                "summary": summary,
            },
            ensure_ascii=False,
        )
    )
    comparisons = report["summary"]["comparisons"]
    return 0 if (
        report["cache"]["unchanged"]
        and comparisons["oracle_failed"] == 0
        and comparisons["python_failed"] == 0
        and comparisons["true_difference"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
