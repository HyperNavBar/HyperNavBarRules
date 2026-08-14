"""
移除社区规则源（rules/immerse_rules.json）中与官方配置源重复的活动规则。

背景：
    社区规则源最初是官方配置源的超集，其中包含大量与官方相同的活动规则。
    现在应用会同时订阅「官方规则源」与「社区规则源」，社区规则源在上（合并时优先），
    官方规则源在下（作为基底），因此社区规则源只需保留与官方不同的自定义规则。

对比逻辑：
    - 同时与最近两个官方快照对比（backup_os3.3_260410.json 与 backup_os4.0_260624.json），
      因为部分规则是从旧版本继承而来，仅对比新版本可能遗漏。
    - 仅当活动规则与官方快照中同名活动规则完全一致（规范化后）时，才视为重复并删除。
    - 只删除 activity 层级的规则，保留应用层级的 name / enable / disableVersionCode 等字段。

用法：
    python3 scripts/remove_duplicates.py [--community rules/immerse_rules.json] [--output rules/immerse_rules.json]
"""

import argparse
import json
import os
import sys

DEFAULTS = {
    "mode": -1,
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
    """将颜色值统一为可比较的规范形式。"""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return value.strip().lower()
    return value


def normalize_rule(rule):
    """将活动规则填充默认值并规范化颜色，便于比较。"""
    result = {}
    for key, default in DEFAULTS.items():
        value = rule.get(key, default)
        if key == "color":
            value = normalize_color(value)
        result[key] = value
    # viewRules 仅当双方都存在时参与比较（若仅一方有则视为不同）
    if "viewRules" in rule:
        result["viewRules"] = rule["viewRules"]
    return result


def load_official_rules(snapshots):
    """加载所有官方快照的 NBIRules，返回列表。"""
    official_list = []
    for path in snapshots:
        if not os.path.exists(path):
            print(f"警告：官方快照不存在，跳过: {path}", file=sys.stderr)
            continue
        data = read_json(path)
        official_list.append(data.get("NBIRules", {}))
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
                official_app = official.get(package)
                if not isinstance(official_app, dict):
                    continue
                official_activities = official_app.get("activityRules")
                if not isinstance(official_activities, dict):
                    continue
                if activity in official_activities and normalize_rule(official_activities[activity]) == normalized:
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
