"""一次性迁移脚本：官方格式（mode 主参数）→ 新格式（style 主参数）

将 rules/immerse_rules.json 从官方 OS33 格式（mode/color/sf_sampling_mode 组合）
转换为新格式（style 主参数）。归一化由 rule.py 的 ActivityRule.normalize_from_official
完成，本脚本只负责批量解析、统计并写回。

用法:
    python scripts/migrate_to_style.py [--input PATH] [--output PATH]

默认 --input 与 --output 均为 rules/immerse_rules.json（原地覆盖迁移）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rule import *
from utils import *


def count_activities(nbi: dict) -> int:
    """统计全部应用的 activity 键总数（activityRules 为空的 app 计 0）"""
    return sum(len(app.get("activityRules") or {}) for app in nbi.values())


def collect_style_distribution(nbi: dict) -> dict:
    """遍历每个 app 的 activityRules，统计各 style 出现次数（空 app 不计入）"""
    distribution = {}
    for app in nbi.values():
        for rule in (app.get("activityRules") or {}).values():
            style = rule.get("style")
            distribution[style] = distribution.get(style, 0) + 1
    return distribution


def main():
    parser = argparse.ArgumentParser(description="官方格式 → 新格式（style 主参数）一次性迁移")
    parser.add_argument("--input", default="rules/immerse_rules.json", help="源文件（官方格式）")
    parser.add_argument("--output", default="rules/immerse_rules.json", help="输出文件（新格式）")
    args = parser.parse_args()

    # 1. 读入官方格式源数据
    data = read_json_file(args.input)
    assert data.get("modules") == "navigation_bar_immersive_application_config_new", (
        f"源文件 modules 不是官方格式: {data.get('modules')}"
    )

    # 迁移前统计
    before_apps = len(data["NBIRules"])
    before_activities = count_activities(data["NBIRules"])

    # 保留原始根级元数据（Rule.toDict 硬编码 dataVersion="999999"、modifyApps="modifyApps"，
    # 迁移不应重置发布流程写入的真实值；name 已由 Rule.toDict 的 `if self.name` 保留）
    original_meta = {k: data[k] for k in ("dataVersion", "modifyApps") if k in data}

    # 2. 经 Rule.fromData("33") 解析，归一化为新格式 style
    rule = Rule.fromData("33", data)

    # 3. 输出新格式 JSON（toData("dict") 自动写 modules == "HyperNavBar_config"），
    #    回填原始根级元数据，末尾换行
    output = json.loads(rule.toData("dict"))
    output.update(original_meta)
    save_file(args.output, json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    # 5. 迁移后统计
    migrated = read_json_file(args.output)
    after_apps = len(migrated["NBIRules"])
    after_activities = count_activities(migrated["NBIRules"])
    styles = collect_style_distribution(migrated["NBIRules"])

    print("=" * 48)
    print(f"迁移完成: {args.input} -> {args.output}")
    print(f"迁移前应用数: {before_apps}")
    print(f"迁移后应用数: {after_apps}")
    print(f"迁移前 activity 总数: {before_activities}")
    print(f"迁移后 activity 总数: {after_activities}")
    print(f"style 分布: {styles}")
    print("=" * 48)

    # 一致性校验
    assert after_apps == before_apps, f"应用数不一致: {before_apps} -> {after_apps}"
    assert after_activities == before_activities, (
        f"activity 总数不一致: {before_activities} -> {after_activities}"
    )
    assert migrated["modules"] == "HyperNavBar_config", migrated["modules"]
    leftover = [
        (pkg, act)
        for pkg, app in migrated["NBIRules"].items()
        for act, r in (app.get("activityRules") or {}).items()
        if "mode" in r or "style" not in r
    ]
    assert not leftover, f"存在残留 mode 或缺 style 的条目: {leftover}"
    print("OK 迁移校验通过：应用数/activity 数不变，无 mode 残留")


if __name__ == "__main__":
    main()
