import os
from datetime import datetime, timezone, timedelta
from rule import *
from remove_duplicates import OFFICIAL_SNAPSHOTS, load_official_rules, remove_duplicates

# 获取 UTC+8 今天的日期，格式为 YYMMDD
tz_utc8 = timezone(timedelta(hours=8))
today = datetime.now(tz_utc8).strftime("%y%m%d")

merge_path = "rules/merge.json"

# 如果 merge.json 非空，先合并本地规则
if os.path.exists(merge_path) and os.path.getsize(merge_path) > 0:
    data = importFromOS33("rules/immerse_rules.json")
    data.updateFromRule(importFromOS33(merge_path))
    save_file("rules/immerse_rules.json", data.toData("33"))
    save_file(merge_path, "")  # 合并后清空

# 读取规则并更新 dataVersion
data = importFromOS33("rules/immerse_rules.json")
result = json.loads(data.toData("dict"))

# 移除与官方配置源重复的活动规则（社区规则源只保留自定义规则）
official_list = load_official_rules(OFFICIAL_SNAPSHOTS)
if official_list:
    removed_count, affected_apps = remove_duplicates(result["NBIRules"], official_list)
    if removed_count > 0:
        print(f"已移除 {removed_count} 条与官方重复的活动规则（涉及 {affected_apps} 个应用）")

result["dataVersion"] = today

save_file("rules/immerse_rules.json", json.dumps(result, indent=2, ensure_ascii=False))
