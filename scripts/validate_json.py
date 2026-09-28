import sys
import traceback

from rule import *

VALID_MODULES = ("HyperNavBar_config", "navigation_bar_immersive_application_config_new")

# 直接读取原始 JSON 校验 style 值（不依赖 fromData 对非法 style 的回退处理）
raw = read_json_file("rules/immerse_rules.json")

# 1) 根级 modules 合法性
modules = raw.get("modules")
if modules not in VALID_MODULES:
    print(f"错误：modules 非法: {modules!r}（应为 {VALID_MODULES} 之一）", file=sys.stderr)
    sys.exit(1)

# 2) 校验每个 activity 的 style 值合法（新格式 style 主参数；官方格式 activity 含 mode 字段）
bad = []
bad_app = []
for package, app_rule in raw.get("NBIRules", {}).items():
    if not isinstance(app_rule, dict):
        continue
    hook = app_rule.get("hookExcluded")
    # 始终显式写出 hookExcluded（默认 true）：旧版本应用默认值为 false，缺失会导致旧版本仍注入
    if not isinstance(hook, bool):
        bad_app.append((package, hook))
    activities = app_rule.get("activityRules")
    if not isinstance(activities, dict):
        continue
    for activity, rule in activities.items():
        if not isinstance(rule, dict):
            bad.append((package, activity, f"非法规则类型: {rule!r}"))
        elif "mode" not in rule:
            style = rule.get("style")
            if style not in ActivityRule.VALID_STYLES:
                bad.append((package, activity, style))

if bad_app:
    for package, value in bad_app:
        print(f"非法或缺失 hookExcluded：{package} = {value!r}（必须显式写出布尔值）", file=sys.stderr)
    print("错误：每个应用都必须显式声明布尔值 hookExcluded（默认 true）", file=sys.stderr)
    sys.exit(1)

if bad:
    for package, activity, style in bad:
        print(f"非法 style：{package} / {activity} = {style!r}", file=sys.stderr)
    print(f"错误：存在非法 style 值（合法值：{ActivityRule.VALID_STYLES}）", file=sys.stderr)
    sys.exit(1)

# 3) 新格式可成功展开为官方格式（toData("33") 不抛异常）
try:
    Rule.fromData("dict", raw).toData("33")
except:
    traceback.print_exc()
    sys.exit(1)

sys.exit(0)
