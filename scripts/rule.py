import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import *


class ActivityRule:
    VALID_STYLES = ("default", "view", "sf", "color", "floating", "disabled")

    def __init__(self, name: str, style: str = "disabled", color: str = None, sf_sampling_mode: int = None, dialogMode: int = 1, popupMode: int = 1, appNavColorDisabled: int = 0, viewRules: list = None, **args):
        self.name = name
        self.style = style if style in self.VALID_STYLES else "disabled"
        self.color = self._normalize_color(color)
        self.sf_sampling_mode = sf_sampling_mode
        self.dialogMode = dialogMode
        self.popupMode = popupMode
        self.appNavColorDisabled = appNavColorDisabled
        self.viewRules = viewRules

    @staticmethod
    def _normalize_color(color):
        """统一内部颜色为 RGBA 序 hex 字符串（#RRGGBBAA）；1（跟随系统）与 None 保持 None"""
        if isinstance(color, str) and is_number(color):
            color = int(color)
        if isinstance(color, int) and color == 1:
            return None
        if isinstance(color, int):
            return argb_int_to_rgba(color)
        return color

    def _expand_to_official(self):
        """style 主参数 → 官方 OS33 字段展开"""
        if self.style == "default":
            return {"mode": -1, "color": None, "sf_sampling_mode": 0}
        if self.style == "view":
            return {"mode": 1, "color": 1, "sf_sampling_mode": 0}
        if self.style == "sf":
            return {"mode": 1, "color": None, "sf_sampling_mode": 1}
        if self.style == "color":
            color = rgba_to_argb_int(self.color) if isinstance(self.color, str) else self.color
            return {"mode": 1, "color": color, "sf_sampling_mode": 0}
        if self.style == "floating":
            return {"mode": 2, "color": None, "sf_sampling_mode": 0}
        return {"mode": 0, "color": None, "sf_sampling_mode": 0}  # disabled

    def toData(self, mode: str = "dict"):
        if mode == "dict":
            result = {"style": self.style}
            if self.style == "color" and self.color is not None:
                result["color"] = self.color
            if self.sf_sampling_mode in (-1, 255):
                result["sf_sampling_mode"] = self.sf_sampling_mode
            if self.dialogMode is not None and self.dialogMode != 1:
                result["dialogMode"] = self.dialogMode
            if self.popupMode is not None and self.popupMode != 1:
                result["popupMode"] = self.popupMode
            if self.appNavColorDisabled is not None and self.appNavColorDisabled != 0:
                result["appNavColorDisabled"] = self.appNavColorDisabled
            if self.viewRules:
                result["viewRules"] = self.viewRules
            return result
        if mode == "33":
            result = self._expand_to_official()
            if self.sf_sampling_mode in (-1, 255):
                result["sf_sampling_mode"] = self.sf_sampling_mode
            result["dialogMode"] = self.dialogMode if self.dialogMode is not None else 1
            result["popupMode"] = self.popupMode if self.popupMode is not None else 1
            result["appNavColorDisabled"] = self.appNavColorDisabled if self.appNavColorDisabled is not None else 0
            if self.viewRules:
                result["viewRules"] = self.viewRules
            return result
        if mode == "30":
            expanded = self._expand_to_official()
            result = {"mode": expanded["mode"], "color": expanded["color"]}
            if self.viewRules:
                result["viewRules"] = self.viewRules
            return result
        if mode == "22":
            expanded = self._expand_to_official()
            name = str(self.name)
            m = str(expanded["mode"])
            if expanded["mode"] == 1 and expanded["color"] is not None and expanded["color"] != 1:
                return ":".join([name, m, str(expanded["color"])])
            return ":".join([name, m])

    @classmethod
    def normalize_from_official(cls, data):
        """官方格式 → 新格式（style 主参数 + 高级字段），优先级从高到低"""
        result = {}
        sf = data.get("sf_sampling_mode")
        mode = data.get("mode")
        color = data.get("color")
        if isinstance(mode, str) and is_number(mode):
            mode = int(mode)
        if isinstance(color, str) and is_number(color):
            color = int(color)

        if sf == 1:
            result["style"] = "sf"
        else:
            if sf in (-1, 255):
                result["sf_sampling_mode"] = sf
            if mode == 1 and isinstance(color, int) and color != 1:
                result["style"] = "color"
                result["color"] = argb_int_to_rgba(color)
            elif mode == 1:
                result["style"] = "view"
            elif mode == 0:
                result["style"] = "disabled"
            elif mode == 2:
                result["style"] = "floating"
            else:
                result["style"] = "default"

        for field in ("dialogMode", "popupMode", "appNavColorDisabled", "viewRules"):
            if field in data and data[field] is not None:
                result[field] = data[field]
        return result

    @classmethod
    def fromData(cls, mode: str, name: str, data):
        if mode in ["dict", "33", "30"]:
            if "style" in data:
                return cls(name=name, **data)
            return cls(name=name, **cls.normalize_from_official(data))
        elif mode == "22":
            parts = data.split(":")
            official = {"mode": int(parts[1])}
            if len(parts) == 3:
                official["color"] = int(parts[2])
            return cls(name=parts[0], **cls.normalize_from_official(official))

    def updateFromDict(self, data):
        if "style" in data:
            self.style = data["style"] if data["style"] in self.VALID_STYLES else "disabled"
            if "color" in data:
                self.color = self._normalize_color(data["color"])
            if "sf_sampling_mode" in data:
                self.sf_sampling_mode = data["sf_sampling_mode"]
        elif "mode" in data:
            normalized = self.normalize_from_official(data)
            self.style = normalized.get("style", self.style)
            if "color" in normalized:
                self.color = normalized["color"]
            if "sf_sampling_mode" in normalized:
                self.sf_sampling_mode = normalized["sf_sampling_mode"]
        if "dialogMode" in data:
            self.dialogMode = data["dialogMode"]
        if "popupMode" in data:
            self.popupMode = data["popupMode"]
        if "appNavColorDisabled" in data:
            self.appNavColorDisabled = data["appNavColorDisabled"]
        if "viewRules" in data:
            self.viewRules = data["viewRules"]
        return self

    def updateFromRule(self, rule):
        self.updateFromDict(rule.toData())
        return self


class AppRule:
    def __init__(self, mode: str, package_name: str, name: str = "", enable: bool = True, disableVersionCode: int = None, activityRules: dict | str = None, **args):
        self.package_name = package_name
        self.name = name
        self.enable = enable
        self.disableVersionCode = disableVersionCode

        if mode == "22":
            self.activityRules = {data[0]: ActivityRule.fromData(mode, data.split(":")[0], data) for data in activityRules.split(",")} if activityRules else {}
        else:
            self.activityRules = {name: ActivityRule.fromData(mode, name, data) for name, data in activityRules.items()} if activityRules else {}

    def toData(self, mode: str = "dict"):
        if mode in ["dict", "33", "30"]:
            result = {"name": self.name, "enable": self.enable}
            if self.disableVersionCode is not None:
                result["disableVersionCode"] = self.disableVersionCode
            sorted_activity_rules = sorted(self.activityRules.items(), key=lambda x: x[0])
            result["activityRules"] = {name: rule.toData(mode) for name, rule in sorted_activity_rules}
            return result
        elif mode == "22":
            sorted_activities = sorted(self.activityRules.values(), key=lambda x: x.name)
            activity_rules_str = ",".join([i.toData(mode) for i in sorted_activities]) if sorted_activities else ""
            result = {"@name": self.package_name, "@enable": self.enable, "@activityRule": activity_rules_str}
            return result

    @classmethod
    def fromData(cls, mode: str, package_name: str, data):
        if mode == "22":
            return cls(mode=mode, package_name=package_name, name="", enable=data.get("@enable", False), activityRules=data.get("@activityRule", ""))
        if mode == "33":
            data["enable"] = data.get("enable", False) or data.get("enable31", False)
        return cls(mode=mode, package_name=package_name, **data)

    def updateFromDict(self, data):
        if not self.name and data.get("name"):
            self.name = data["name"]
        if "activityRules" in data:
            for name, rule in data["activityRules"].items():
                if name in self.activityRules:
                    self.activityRules[name].updateFromDict(rule)
                else:
                    self.activityRules[name] = ActivityRule.fromData("dict", name, rule)
        if "enable" in data:
            self.enable = data["enable"]
        return self

    def updateFromRule(self, rule):
        self.updateFromDict(rule.toData())
        return self


class Rule:
    def __init__(self, mode: str, name: str = "", NBIRules: dict | list = None, **args):
        self.name = name
        if mode in "22":
            self.NBIRules = {data["@name"]: AppRule.fromData(mode, data["@name"], data) for data in NBIRules} if NBIRules else {}
        else:
            self.NBIRules = {package_name: AppRule.fromData(mode, package_name, data) for package_name, data in NBIRules.items()} if NBIRules else {}

    def toDict(self, mode: str = "dict"):
        if mode in ["dict", "33", "30"]:
            sorted_rules = sorted(self.NBIRules.items(), key=lambda x: x[0])
            result = {}
            if self.name:
                result["name"] = self.name
            result["dataVersion"] = "999999"
            result["modules"] = "HyperNavBar_config" if mode == "dict" else "navigation_bar_immersive_application_config_new"
            result["modifyApps"] = "modifyApps"
            if self.NBIRules:
                result["NBIRules"] = {package_name: rule.toData(mode) for package_name, rule in sorted_rules}
            return result
        elif mode == "22":
            sorted_rules = sorted(self.NBIRules.values(), key=lambda x: x.package_name)
            result = {
                "NBIRules": {
                    '@xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                    "package": [i.toData(mode) for i in sorted_rules]
                }
            }
            return xmltodict.unparse(result, pretty=True, encoding="utf-8", short_empty_elements=True)

    def toData(self, mode: str = "dict"):
        if mode == "22":
            return self.toDict("22")
        return json.dumps(self.toDict(mode), indent=2, ensure_ascii=False)

    @classmethod
    def fromData(cls, mode: str, data):
        if mode in ["dict", "33", "30"]:
            return cls(mode=mode, **data)
        elif mode == "22":
            return cls(mode=mode, NBIRules=data.get("NBIRules", {}).get("package", []))

    def updateFromDict(self, data):
        if "NBIRules" in data:
            for package_name, rule in data["NBIRules"].items():
                if package_name in self.NBIRules:
                    self.NBIRules[package_name].updateFromDict(rule)
                else:
                    self.NBIRules[package_name] = AppRule.fromData("dict", package_name, rule)
        return self

    def updateFromRule(self, rule):
        self.updateFromDict(rule.toDict())
        return self


def importFromOS33(path: str):
    return Rule.fromData("33", read_json_file(path))


def importFromOS30(path: str):
    return Rule.fromData("30", read_json_file(path))


def importFromOS22(path: str):
    return Rule.fromData("22", read_xml_file(path))