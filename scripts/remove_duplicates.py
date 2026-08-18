"""
移除社区规则源（rules/immerse_rules.json）中与官方配置源重复的活动规则。

背景：
    社区规则源最初是官方配置源的超集，其中包含大量与官方相同的活动规则。
    现在应用会同时订阅「官方规则源」与「社区规则源」，社区规则源在上（合并时优先），
    官方规则源在下（作为基底），因此社区规则源只需保留与官方不同的自定义规则。

对比逻辑（新格式 style 主参数）：
    - 社区规则源（rules/immerse_rules.json）已是新格式（style 字段），直接读取 NBIRules。
    - 官方快照（backup/*.json）是官方格式（mode 字段），对每个 activity 规则调用
      rule.py 的 ActivityRule.normalize_from_official() 归一化为新格式后再对比。
    - 双方都规整为「新格式规范形」（style + color hex + 高级字段）后比较，
      相等则视为重复并删除。
    - 关键：官方 mode=0 + sf_sampling_mode=1 归一化为 style=sf，与社区规则 style=sf
      行为等价并正确匹配（若反向把 style 展开为官方 mode 会因 mode 不同而漏判）。
    - 只删除 activity 层级的规则，保留应用层级的 name / enable / disableVersionCode 等字段。

用法：
    python3 scripts/remove_duplicates.py [--community rules/immerse_rules.json] [--output rules/immerse_rules.json]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rule import ActivityRule
from utils import argb_int_to_rgba

# 新格式字段默认值（style 主参数）
DEFAULTS = {
    "style": "disabled",
    "color": None,
    "sf_sampling_mode": 0,
    "dialogMode": 1,
    "popupMode": 1,
    "appNavColorDisabled": 0,
}

# 官方快照：旧版本 + 新版本（与 backup.json 内容一致）
OFFICIAL_SNAPSHOTS = [
    os.path.join("backup", "backup_os3.3_260410.json"),
    os.path.join("backup", "backup_os4.0_260624.json"),
]


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def normalize_color(value):
    """将颜色值统一为可比较的规范形式（大写 hex，去 #）。"""
    if value is None:
        return None
    if isinstance(value, int):
        return argb_int_to_rgba(value)
    if isinstance(value, str):
        return value.strip().upper().lstrip("#")
    return value


def normalize_rule(rule):
    """将活动规则规整为新格式规范形（style 主参数 + 高级字段），便于比较。"""
    result = {}
    for key, default in DEFAULTS.items():
        value = rule.get(key, default)
        if key == "color":
            value = normalize_color(value)
        result[key] = value
    # sf_sampling_mode 仅 -1/255 参与比较（其余值等价于默认 0）
    if rule.get("sf_sampling_mode", 0) not in (-1, 255):
        result["sf_sampling_mode"] = 0
    # color 仅在 style=color 时参与比较
    if result["style"] != "color":
        result["color"] = None
    # viewRules 仅当双方都存在时参与比较（若仅一方有则视为不同）
    if "viewRules" in rule:
        result["viewRules"] = rule["viewRules"]
    return result


def load_official_rules(snapshots):
    """加载所有官方快照的 NBIRules，归一化为新格式规范形后返回列表。"""
    official_list = []
    for path in snapshots:
        if not os.path.exists(path):
            print(f"警告：官方快照不存在，跳过: {path}", file=sys.stderr)
            continue
        data = read_json(path)
        normalized = {}
        for package, app_rule in data.get("NBIRules", {}).items():
            if not isinstance(app_rule, dict):
                continue
            activities = app_rule.get("activityRules")
            if not isinstance(activities, dict):
                continue
            normalized[package] = {
                activity: normalize_rule(ActivityRule.normalize_from_official(rule))
                for activity, rule in activities.items()
            }
        official_list.append(normalized)
    return official_list


def remove_duplicates(community_rules, official_list):
    """删除社区规则中与官方重复的活动规则，返回删除数量与受影响应用数。"""
    removed_total = 0
    affected_apps = 0

    for package, app_rule in community_rules.items():
        if not isinstance(app_rule, dict):
            continue
        activity_rules = app_rule.get("activityRules")
        if not isinstance(activity_rules, dict) or not activity_rules:
            continue

        removed = []
        for activity, rule in activity_rules.items():
            normalized = normalize_rule(rule)
            for official in official_list:
                official_activities = official.get(package)
                if not isinstance(official_activities, dict):
                    continue
                if activity in official_activities and official_activities[activity] == normalized:
                    removed.append(activity)
                    break

        if removed:
            for activity in removed:
                del activity_rules[activity]
            removed_total += len(removed)
            affected_apps += 1
            # 活动规则被删空时，移除空的 activityRules 字段（保留应用级字段）
            if not activity_rules:
                del app_rule["activityRules"]

    return removed_total, affected_apps


def main():
    parser = argparse.ArgumentParser(description="移除社区规则源中与官方配置源重复的活动规则")
    parser.add_argument("--community", default=os.path.join("rules", "immerse_rules.json"), help="社区规则源文件路径")
    parser.add_argument("--output", default=None, help="输出文件路径（默认覆盖原文件）")
    args = parser.parse_args()

    community_path = args.community
    output_path = args.output or community_path

    community_data = read_json(community_path)
    community_rules = community_data.get("NBIRules", {})

    official_list = load_official_rules(OFFICIAL_SNAPSHOTS)
    if not official_list:
        print("错误：未找到任何官方快照文件", file=sys.stderr)
        sys.exit(1)

    removed_total, affected_apps = remove_duplicates(community_rules, official_list)

    write_json(output_path, community_data)

    print(f"完成：删除 {removed_total} 条重复活动规则，涉及 {affected_apps} 个应用")
    print(f"输出：{output_path}")


if __name__ == "__main__":
    main()
