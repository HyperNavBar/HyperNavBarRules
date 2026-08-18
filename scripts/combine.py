import json
import os

from rule import *

merge_path = "rules/merge.json"

# 读取现有规则（新格式 style 主参数）
raw = read_json_file("rules/immerse_rules.json")
data = Rule.fromData("dict", raw)

# merge.json 非空时合并；为空时幂等（不改变规则内容）
if os.path.exists(merge_path) and os.path.getsize(merge_path) > 0:
    data.updateFromRule(Rule.fromData("dict", read_json_file(merge_path)))

result = json.loads(data.toData("dict"))
# 还原 dataVersion（Rule.toData("dict") 输出固定为 999999，保留文件原值）
result["dataVersion"] = raw.get("dataVersion", result["dataVersion"])
save_file("rules/immerse_rules.json", json.dumps(result, indent=2, ensure_ascii=False))
