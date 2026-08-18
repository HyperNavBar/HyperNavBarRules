# 小米澎湃 OS4「小白条沉浸」(NBI) 逆向分析报告

> 逆向对象：`miui-services.jar`（system_server 侧，`com.android.nbi` 包，14 个类）+ `miui-framework.jar`（应用进程侧，`com.android.internal.policy` + `android.app`）
>
> 方法：baksmali 2.5.2 反汇编为 smali 后逐类精读（无混淆）
>
> 产出：完整调用链、规则字段语义、与 HyperNavBarRules 仓库文档的差异对照

---

## 目录

1. [全景调用链](#一全景调用链)
2. [服务端（system_server）](#二服务端system_server)
3. [框架侧（应用进程）](#三框架侧应用进程)
4. [与 HyperNavBarRules 仓库字段对照](#四与hypernavbarules仓库字段对照)
5. [关键结论与疑点](#五关键结论与疑点)
6. [常量与调试开关汇总](#六常量与调试开关汇总)
7. [附录：逆向涉及文件清单](#七附录逆向涉及文件清单)

---

## 一、全景调用链

```
┌─ system_server (miui-services.jar) ─────────────────────────────────────┐
│ MiuiNBIManagerService (SystemService, "miui_navigation_bar_immersive") │
│   ├─ $Inner (IMiuiNBI.Stub, Binder 服务端)                              │
│   │    ├─ getSystemNBIRules(pkg) → MiuiNBIController                    │
│   │    ├─ register/unregisterColorSamplingListener → CompositionSampling│
│   │    └─ 云控同步: SettingsCloudData ContentObserver + USER_SWITCHED    │
│   ├─ $Shell (adb shell 命令: list/enable/disable/...)                  │
│   └─ MiuiNBIController → MiuiNBIRule → MiuiParsingNBIRule (JSON/云控)   │
└─────────────────────────────────────────────────────────────────────────┘
        ▲ Binder (IMiuiNBI / MiuiNBIManagerStub)   ▲ SurfaceFlinger 区域采样
┌─ 应用进程 (miui-framework.jar) ─────────────────────────────────────────┐
│ ActivityThreadImpl.init → MiuiNBIManagerStub.init(context)              │
│ DecorViewImmersiveImpl (每 DecorView 一个, 生命周期转发)                  │
│   └─ NavigationBarImmersiveController (每窗口一个, 沉浸决策核心)          │
│        ├─ analyzeViewTree → 找 bottomTabMenuView / largeWebViewAtBottom │
│        ├─ handleCloudCustomRule → dialog/popup/activity 三层规则         │
│        ├─ 画 30×1 位图采样 → getNavZoneDominantColor                     │
│        └─ SF 区域采样 → ColorMathUtils 计算 → 设 PhoneWindow 导航栏颜色   │
└─────────────────────────────────────────────────────────────────────────┘
```

数据流：

```
云控 JSON (/data/system/cloudFeature_navigation_bar_immersive_rules_list.json)
   │ 或 本地 JSON (/system_ext/etc/nbi/navigation_bar_immersive_rules_list.json)
   ▼
MiuiParsingNBIRule 解析 → MiuiNBIRule (含 ActivityRule / ViewRule)
   ▼
MiuiNBIController (system_server 内存规则)
   ▼ Binder: getSystemNBIRules(pkg) → Bundle{enable, versionCode, activityRules JSON}
MiuiNBIManagerImpl (应用进程, 实现 MiuiNBIManagerStub)
   ├─ allowSystemOverride (manifest 属性) / 手势设置缓存 / disableVersionCode 判定
   ▼ getActivityRuleInfo → ActivityRuleInfo (6 张 Map)
NavigationBarImmersiveController (每窗口实例)
   ▼ 视图树分析 + 规则分发 + 颜色采样 (位图 / SF)
DecorViewImmersiveImpl → PhoneWindow.mNavigationBarColor → 渲染
```

---

## 二、服务端（system_server）

### 1. MiuiNBIManagerService

- `SERVICE_NAME = "miui_navigation_bar_immersive"`，标准 `SystemService`。
- 提供静态 `isEnableNBIAllApp()` 全局开关。
- 启动时创建 `$Inner`（Binder 服务端，`IMiuiNBI.Stub`）与 `$Shell`（shell 命令）。

### 2. MiuiNBIManagerService$Inner（IMiuiNBI.Stub，Binder 服务端）

- **`getSystemNBIRules(pkgName)`**：空包名返回 null；否则委托 `MiuiNBIController.getSystemNBIRules(pkg)`；返回的 Bundle 为空也转 null。
- **`registerColorSamplingListener(IBinder listener, int displayId, int[] samplingPixels, SamplingListenerArgs args)`**：直接静态转发 `CompositionSamplingListener.registerPixelColorListener`。
  - **关键结论：SF 区域采样本质是系统合成器（SurfaceFlinger）层能力，NBI 服务只是透传通道。**
- **`unregisterColorSamplingListener(IBinder)`**：转发 `CompositionSamplingListener.unregisterPixelColorListener`。
- **云控同步机制**：
  - 注册 `MiuiSettings.SettingsCloudData.getCloudDataNotifyUri()` 的 ContentObserver（`$Inner$3`，跑在 MiuiBgThread）。
  - 注册 `android.intent.action.USER_SWITCHED` 广播接收器（`$Inner$1`）。
  - 触发后 `applyNewNBIConfig()` → `MiuiNBIController.updateNBIFromCloud()`。
- **内部线程**：`ConfigHandlerThread`（云控加载，`MSG_LOAD_NBI_CLOUD_CONFIG_DATA = 1`）、MiuiBgThread（`MSG_USER_SWITCH = 2`）。
- `onShellCommand` 将 shell 命令转发给 `$Shell`。

### 3. MiuiNBIManagerService$Shell（adb shell 命令）

权限校验：**仅 uid 2000（shell）或 0（root）** 可执行。

| 命令 | 作用 |
|---|---|
| `list [PACKAGE]` | 列出规则状态（空参 = 列出全部） |
| `enable <PACKAGE>` | 开启 NBI（提示重启应用生效） |
| `disable <PACKAGE>` | 关闭 NBI |
| `disableVersionCode <PACKAGE> <version>` | 设置禁用版本阈值 |
| `activityRule <PACKAGE> <rule>` | 设置 Activity 规则（经 `MiuiNBIController.parseActivityRule`） |
| `update <PACKAGE> <RULE::PARAM>` | 更新规则；无参数时 = 重新加载云控 xml |
| `current-version` | 输出当前云控版本 |
| `dump-rule [PACKAGE]` | dump 规则 |
| `help` | 帮助 |

### 4. MiuiNBIController（规则引擎）

- 持有 `mNBIRules`（生效规则）与 `mCloudNBIRules`（云控规则）。
- **`getSystemNBIRules(pkg)`** → `Bundle{ enable, versionCode(=disableVersionCode), activityRules(JSON 字符串) }`。
- `updateNBIFromCloud()` / `loadCloudNBIData()`：云控加载入口。
- `isNBICloudConfigUpdate`：按模块名 `navigation_bar_immersive_application_config_new` 的 dataVersion 与 `mLastCloudConfigVersion` 比较。
- `updateNBIRule(pkg, "RULE::PARAM", pw)`：按 `::` 分割的 shell 更新入口。
- `setEnableNavigationBarImmersive(pkg, Boolean)`、`dumpRule(pw, pkg)`、`currentCloudControlVersion(pw)`、`parseActivityRule(String) → Map`。

### 5. MiuiNBIRule 数据模型（与规则 JSON 一一对应）

```
MiuiNBIRule
├─ mPackageName
├─ mEnableNavigationBarImmersive (默认 false)
├─ mDisableVersionCode (Long)
└─ mActivityRules: Map<String, ActivityRule>   (key = Activity 类名)
   ActivityRule
   ├─ mode / color(Integer) / sfSamplingMode
   ├─ dialogMode (默认 1) / popupMode (默认 1) / appNavColorDisabled (默认 0)
   └─ viewRules: List<ViewRule>  (viewName / id)
```

### 6. MiuiParsingNBIRule（JSON 解析 + 云控/本地选择）

- **云控文件**：`/data/system/cloudFeature_navigation_bar_immersive_rules_list.json`（写入权限 0x1b0 = 660）
- **本地文件**：`/system_ext/etc/nbi/navigation_bar_immersive_rules_list.json`
- **选择逻辑**：`hasCloud && cloudVersion >= localVersion` → 用云控，否则用本地。
- **JSON 键名全集**：`NBIRules / modifyApps / activityRules / modules / dataVersion / iD / enable / enable31 / mode / color / sf_sampling_mode / dialogMode / popupMode / appNavColorDisabled / disableVersionCode / viewRules`。
- **enable 与 enable31 取 OR**（任一为 true 即启用）。
- 控制模块名：`navigation_bar_immersive_application_config_new`。

---

## 三、框架侧（应用进程）

### 7. ActivityThreadImpl（进程初始化入口）

在「Miui Feature Init」中（`handleBindApplication` 流程内）：

```
MiuiNBIManager.IS_NBI_ENABLE == true
&& SystemProperties.getBoolean("persist.navcolor.enable", true)
&& !ActivityThread.isSystem()
&& ComputilityLevel.getComputilityLevel() >= ComputilityLevel.NORMAL
  → MiuiNBIManagerStub.getInstance().init(context)
```

异常被捕获，仅打 W 日志 "NBI preInit failed"。

### 8. MiuiNBIManagerImpl（实现 com.miui.nbi.MiuiNBIManagerStub）

- **`init(context)`**：`MiuiNBIManager.getDefault().getSystemNBIRules(pkgName)`（Binder 到 system_server）→ 解析规则；监听全局设置 `force_fsg_nav_bar` / `hide_gesture_line`（静态缓存：`isFullScreenGestureNavCached()` / `isHideGestureLineCached()` / `refreshGestureStateFromSettings(ContentResolver)`）。
- **`getActivityRuleInfo(context)`** → `ActivityRuleInfo`（含 6 张 Map：ruleType / color / dialog / popup / sf / appNavColorDisabled）→ 传给 NavigationBarImmersiveController 构造函数。
- **`allowSystemOverride`**：读 manifest 属性 `android.window.PROPERTY_NAV_IMMERSIVE_ALLOW_SYSTEM_OVERRIDE`，为 **false 时禁用系统 NBI 覆盖**。
- **disableVersionCode 判定**：`当前版本 <= disableVersionCode` → 禁用 NBI。
- `registerColorSamplingListener` / `unregisterColorSamplingListener` 转发至 `IMiuiNBI`（system_server）。

### 9. NavigationBarImmersiveController（核心引擎，6514 行，已全文精读）

#### 9.1 构造函数

- 接收 `(DecorView, Context, windowType, windowingMode, ActivityRuleInfo)`。
- 从 ActivityRuleInfo 取 6 张 Map 存入字段（见常量表）。
- 创建 **30×1 ARGB_8888 位图 + Canvas**（`BITMAP_SAMPLE_WIDTH=30`、`BITMAP_SAMPLE_HEIGHT=1`、`BITMAP_NAVZONE_OFFSET=2`）。
- 记录 `mBarOriginColor`（窗口原始导航栏颜色）。
- `mCompatScale` 来自 `ActivityThreadStub.get().getMiuiSizeCompatScale(1.0f)`（MIUI 尺寸兼容缩放）。

#### 9.2 规则类型常量（findValueForActivity 的 packed-switch 0..5）

| 值 | 常量 | 对应 Map | 用途 |
|---|---|---|---|
| 0 | `RULE_TYPE_MODE` | mActivityRuleTypeMap | Activity 主模式 |
| 1 | `RULE_TYPE_COLOR` | mActivityRuleColorMap | 自定义导航栏颜色 |
| 2 | `RULE_TYPE_DIALOG` | mDialogRuleTypeMap | 对话框模式 |
| 3 | `RULE_TYPE_POPUP` | mPopupRuleTypeMap | Popup 模式 |
| 4 | `RULE_TYPE_SF` | mSfRuleTypeMap | SF 采样模式 |
| 5 | `RULE_APP_NAV_COLOR_DISABLED` | mAppNavColorDisabledMap | 禁用应用自定义导航栏颜色 |

#### 9.3 取值语义（CLOUD_CUSTOM_* 常量）

**Activity 主模式（mode）**：

| 值 | 常量 | 行为 |
|---|---|---|
| -1 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_DEFAULT` | 无云规则 → 走代码逻辑 |
| 0 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_DISABLE` | 禁用沉浸 |
| 1 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_FILL_NAVIGATION_BAR_COLOR` | 填色（自定义 color 或采样） |
| 2 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_E2E` | 强制沉浸（edge-to-edge） |

**SF 采样模式（sf_sampling_mode）**：

| 值 | 常量 | 行为 |
|---|---|---|
| -1 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_SF_DISABLE_SF_SAMPLING` | 禁用 SF 采样（返回 flag 4） |
| 0 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_SF_DEFAULT` | 默认（无强制） |
| 1 | `CLOUD_CUSTOM_ACTIVITY_RULE_TYPE_SF_FORCE_SF_SAMPLING` | 强制 SF 采样（返回 flag 2） |

**浮动窗口（dialog/popup）模式**：

| 值 | 常量 | 行为 |
|---|---|---|
| 0 | `CLOUD_CUSTOM_FLOATING_RULE_TYPE_DISABLE` | 禁用 |
| 1 | `CLOUD_CUSTOM_FLOATING_RULE_TYPE_DEFAULT` | 默认（位图采样） |
| 2 | `CLOUD_CUSTOM_FLOATING_RULE_TYPE_SF` | SF 采样 |
| 3 | `CLOUD_CUSTOM_FLOATING_RULE_TYPE_DISABLE_FLOATING_DEFAULT` | 禁用浮动默认（走 SF） |
| 4 | `CLOUD_CUSTOM_FLOATING_RULE_TYPE_DISABLE_FLOATING_SF` | 禁用浮动 SF |

**颜色来源（src）**：`1 = COLOR_SRC_VIEW`（视图采样）、`2 = COLOR_SRC_SF`（SF 采样）、`3 = COLOR_SRC_SYSTEM_DEFAULT`。

#### 9.4 主流程 `startFindAndUpdateNavigationBarColor(popupInvoked)`

1. **前置过滤**（任一命中即跳过）：
   - `mWindowingMode != 1`（非全屏）；
   - `!isFullScreenGestureNavCached()`（非手势导航）**或** `isHideGestureLineCached()`（手势线隐藏）；
   - `isNavBarHidden()`：sysUiVisibility 含 0x2（SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION）或 0x200（SYSTEM_UI_FLAG_HIDE_NAVIGATION）、WindowInsetsController requestedVisibleTypes 不含 navigationBars、`mDecorFitsSystemWindows == false`。
2. **`analyzeViewTree()`** → `ViewAnalysisResult`：
   - `mMinBottomViewBottom = 0.9 * decorView.getHeight()`；
   - DFS 遍历视图树，寻找**合法底部视图**（`bottomTabMenuView`，`ApplicationBottomViewCheckUtil.isValidBottomView`）与**底部大 WebView**（`largeWebViewAtBottom`，`isValidWebView`）；
   - 子视图倒序优先，找到即停止。
3. **`handleCloudCustomRule(popupInvoked)`**（仅当 `DEBUG_ENABLE_CLOUD_CONFIG` = `persist.navcolor.cloud` = true）：
   - 查 `appNavColorDisabled`（ruleType 5）→ 设 `mAppNavColorDisabled`；
   - **dialog**：`mWindowType == 2` 时按 dialogMode 处理：
     - dialogMode==0 → 直接跳过；
     - `notNeedDialogImmersive()`（初始导航栏已隐藏或高度为 0）→ 跳过；
     - 非浮窗 → `updateDialogNavBarColor(dialogMode)`；
     - 浮窗且宽度全屏：全屏高 → 直接沉浸；底部对话框 → 按 `SOFT_INPUT_ADJUST_PAN` 情况调整窗口高度（补偿导航栏高度）并 `setDialogImmersive(true)`；
     - `updateDialogNavBarColor`：dialogMode 1/3 → 位图采样；2/4 → SF 采样。
   - **popup**：`popupMode != 0` 且 `mPopupWindow != null` → 延迟 16ms 执行 popup 颜色采样任务（全宽 + 贴底才采样）；
   - **activity**：`handleSfCloudRule(activity)` 优先：
     - sf_sampling_mode==1 → 返回 flag 2（SF 采样）；
     - sf_sampling_mode==-1 → 返回 flag 4（禁 SF）；
     - 否则 mode 分发：0 → DISABLED；1 → `findValueForActivity(RULE_TYPE_COLOR)` 得自定义色，有色则 `updateNavigationBarColor(true, color)`，否则 `updateNavigationBarColor(false, -1)`（采样）；2 → `setNavigationBarForceImmersive()`。
4. 云规则未完全命中（`flag & 1 == 0`）→ **`updateNavigationBarTarget(viewResult, flag)`**：
   - `flag & 2` → `enableSFSampling()`；
   - 有 `bottomTabMenuView`：
     - 关闭 SF 采样；
     - SnackBar → 跳过；
     - 设为 `mBottomViewTarget`；alpha>0 且带背景 → 只画目标视图，否则加 OnLayoutChangeListener 并全树采样；
     - `updateNavigationBarColor(false, -1)`（位图采样）。
   - 无 bottomTabMenuView：
     - 无 WebView → `setNavigationBarForceImmersive()`（E2E）+ 关 SF；
     - 有 WebView 且 `flag & 4 == 0` → `enableSFSampling()`。

#### 9.5 颜色计算与设置

- **`updateNavigationBarColor(hasCustomColor, customColor)`**：
  - hasCustomColor → 用自定义色；
  - 否则 `getNavZoneDominantColor()`：
    - 有 `mBottomViewTarget`（alpha>0 且有背景）→ 只画目标视图；
    - 有 `mLargeWebViewTarget` → 画 WebView（`getBrightness`：透明→白；HSV 亮度 >0.25→白，否则黑）；
    - 否则画 `DecorView.mContentRoot`；
    - 画到 30×1 位图的导航栏行（y 平移 = `-(height-1)+2`），`getDominantColor()` 取 `pixel(0x1d, 0)`；
  - 采样结果为透明（0）且非自定义色：windowType==2 → 用窗口当前导航栏颜色；否则 500ms 后重试一次（`mHasRetriedColorUpdate`），仍失败用 0。
- **`setNavigationBarColorFromImmersive(color, src)`**：
  - `PhoneWindow.addFlags(0x80000000)`（FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS）；
  - 直接写 `PhoneWindow.mNavigationBarColor` 与 `mImmersiveNavigationBarColor`，置 `mHasForcedColor = true`；
  - 浮动 activity → `setDialogImmersive(true)`；
  - 若处于强制沉浸 → 取消 force、`dispatchApplyInsets`、`setNotifyDrawForImmersive(false)`；
  - `WindowInsetsController.setSystemBarsAppearance(0, 0x200)`（清除 APPEARANCE_LIGHT_NAVIGATION_BARS）；
  - `DecorView.updateColorViews(null, false)`。

#### 9.6 SF 区域采样（SurfaceFlinger）

- `enableSFSampling()` → `registerSFSamplingListener()`：
  - 获取 WindowMetrics；无 Activity/ComponentName 则失败返回；
  - 采样点计算：`marginX = SF_SAMPLING_MARGIN_RATIO(默认2) / 1000 * width`；`xInterval = (width - 2*marginX) / (SF_SAMPLING_POINTS_NUM(默认10) - 1)`；`y = height - (SF_SAMPLING_OFFSET_Y + navbarHeight)`；
  - 采样点数组（x,y,x+1,y+1 四元组格式）；
  - `SamplingListenerArgs{ tag="NavBar", prio=300(0x12c), miCompatScale, activityName }`；
  - `MiuiNBIManagerStub.getInstance().registerColorSamplingListener(binder, 0, rectsArr, args)` → system_server → SurfaceFlinger。
- 回调 **`handleSFColorCollected([I agbrColors)`**：
  - 仅全屏窗口（windowingMode==1）接受；
  - ABGR → ARGB（`ColorMathUtils.abgrToArgb`）；
  - `calculateBarColor()`：众数判定 → `recognizeBackground`（首尾相似则简单混合）→ 灰度频率（`MIN_GREY_FREQUENCY_PERCENT` 30%）→ 主色频率（`MIN_FREQUENCY_PERCENT` 70%）→ 方差 < `MAX_BLEND_COLOR_VARIANCE`(2000) 时 `blendColors`，否则分段灰度（`NUM_GREY_SCALE_LEVEL`=3，luma 法）；
  - 与 `mLastSFSampledColor` 相同则丢弃；按 `MIN_REFRESH_COLOR_PERIOD`（默认 10ms）节流；
  - `refreshSampledBarColor()` → `setNavigationBarColorFromImmersive(value, COLOR_SRC_SF=2)`。

#### 9.7 匹配逻辑（findValueForActivity / matchesWildcard）

- 按 ruleType 选 Map；先精确 key 匹配；未命中则遍历 entry 用 `matchesWildcard`（`.` → `\.`，`*` → `.*` 的正则）；仍未命中则查 `"*"` 通配键兜底。

#### 9.8 其他

- `isNavBarHidden()` / `hasLayoutHideNavFlag()`（0x200 HIDE_NAVIGATION）；
- `onDetachedFromWindow`：回收位图、注销 SF 监听、清理 popup 资源；
- `onPopupInvoked`：记录原始颜色、触发 popup 流程；`onPopupDismiss`：恢复原始颜色（非强制沉浸时）；
- UT 接口：`calculateBarColorForUT`、`traverseFindTargetViewsDFSForUT`。

### 10. DecorViewImmersiveImpl（生命周期桥接，948 行已全文精读）

- 实现 `DecorViewImmersiveStub`，每 DecorView 一个实例，字段：`mDialogImmersive`、`mNavigationBarImmersiveController`、`mNotifyDrawForImmersive`。
- **`onAttachedToWindow(decorView, context)` 准入条件链**（任一不满足即跳过）：
  1. `MiuiNBIManagerStub.getInstance().isNBIEnable(context)`；
  2. PhoneWindow 存在；
  3. 父 ViewRootImpl 存在；
  4. 主线程；
  5. `!PhoneWindow.mEdgeToEdgeEnforced`（**应用自设强制 E2E 则跳过**）；
  6. `isThirdPartApp(info)`：uid appId >= 10000 且非 FLAG_SYSTEM（系统应用跳过，仅打日志不阻止）；
  7. `!isVirtualDisplay(context)`：显示名不在黑名单 `com.miui.carlink / com.baidu.BaiduMap / com.xiaomi.mirror / com.xiaomi.ucar.minimap / com.miui.car.launcher`（车机/投屏场景）；
  8. `windowType ∈ [1, 99]` 且 ≠ 3；
  9. 满足 → `MiuiNBIManagerImpl.refreshGestureStateFromSettings()` + `new NavigationBarImmersiveController(decorView, context, windowType, windowingMode, getActivityRuleInfo(context))`。
- 其余方法全部转发：`onPreDraw / onLayout / onActive / onApplyWindowInsets / onWindowFocusChanged / onConfigurationChanged / onDetachedFromWindow（回收位图 + 注销 SF + 清 popup + 置空控制器）/ onPopupInvoked / onPopupDismiss / setForceImmersiveNavBar / getNavigationBarColor / isForceImmersive / isAppNavColorDisabled（= mAppNavColorDisabled || mSFSamplingRegistered || mHasForcedColor）/ isDialogImmersive / setDialogImmersive / setNotifyDrawForImmersive / shouldNotifyDrawForImmersive`。

---

## 四、与 HyperNavBarRules 仓库字段对照

| 规则 JSON 字段 | 逆向语义 | 仓库 document.md | 一致性 |
|---|---|---|---|
| `mode` | 0=禁用、1=填色/采样、2=强制沉浸 | 一致 | ✅ |
| `color` | mode=1 时的固定导航栏颜色（Integer，缺省走采样） | — | ✅ |
| `sf_sampling_mode` | -1=禁 SF 采样、0=默认、1=强制 SF 采样 | — | ✅ |
| `dialogMode` / `popupMode` | 0=禁用、1=默认、2=SF、3/4=浮动变体 | — | ✅ |
| `appNavColorDisabled` | 1=禁用应用自定义导航栏颜色 | — | ✅ |
| `viewRules` | 视图名/id 白名单（本版 Controller 主流程未直接消费，供底部视图识别） | — | ⚠️ |
| `enable` / `enable31` | **取 OR** | 文档若写 AND 则不符 | ⚠️ 待核 |
| **`disableVersionCode`** | **当前版本 ≤ 阈值 → 禁用 NBI**（即"旧版本禁用、新版本放开"） | 文档写"版本 ≥ 此值时禁用" | ❌ **方向相反** |

---

## 五、关键结论与疑点

1. **disableVersionCode 语义与仓库文档相反**：
   - 代码：`应用版本 <= disableVersionCode` → 禁用 NBI（意味着规则是"对低版本生效，高版本自动放开"）。
   - 文档：`应用版本号 >= disableVersionCode` 时禁用规则。
   - **若按文档生成规则会导致反生效，社区规则生成逻辑必须修正。**
2. **NBI 的硬前置条件**：
   - 手势导航开启（`force_fsg_nav_bar` = true）且手势线未隐藏（`hide_gesture_line` = false）；
   - 全屏窗口（windowingMode == 1）；
   - 三键导航 / 隐藏手势线 / 分屏窗口下 NBI 全部跳过。
3. **应用可自禁**：
   - manifest 属性 `android.window.PROPERTY_NAV_IMMERSIVE_ALLOW_SYSTEM_OVERRIDE = false`；
   - 应用自设 edge-to-edge（`mEdgeToEdgeEnforced`）。
4. **SF 采样是"系统合成器级"能力**：经 `CompositionSamplingListener` 注册到 SurfaceFlinger，按 10 个采样点周期回传颜色——这是"跟随内容变色"（视频/WebView 底部）的实现基础；本地位图采样（30×1 位图）是兜底路径。
5. **`com.miui.nbi` 接口包不在两个 jar 中**（`MiuiNBIManagerStub`、`IMiuiNBI`、`MiuiNBIManager` 属独立 API 构件，本报告契约均从使用侧推导，签名可靠）。
6. **云控优先**：`/data/system/cloudFeature_...json` 与本地 `/system_ext/etc/nbi/...json` 按版本比较择优加载；shell `update` 命令可强制刷新。
7. **规则数据在进程内缓存**：`getSystemNBIRules` 仅在应用进程初始化（ActivityThreadImpl Miui Feature Init）时拉取一次；shell enable/disable 提示"重启应用生效"与此一致。

---

## 六、常量与调试开关汇总

### 6.1 系统属性（persist.navcolor.*，全部可在运行时调节）

| 属性 | 默认值 | 作用 |
|---|---|---|
| `persist.navcolor.enable` | true | NBI 总开关（框架层） |
| `persist.navcolor.cloud` | true | 云规则开关 |
| `persist.navcolor.sf_sampling` | true | SF 采样开关 |
| `persist.navcolor.sf_sampling_points_num` | 10 | SF 采样点数 |
| `persist.navcolor.sf_sampling_margin` | 2 | 采样边距比例（‰） |
| `persist.navcolor.sf_sampling_offset_y` | 2 | 采样行偏移（px） |
| `persist.navcolor.min_sf_sampling_period` | 10 | SF 采样最小周期（ms） |
| `persist.navcolor.min_refresh_color_period` | 10 | 颜色刷新最小周期（ms） |
| `persist.navcolor.min_frequency_percent` | 70 | 主色判定频率阈值（%） |
| `persist.navcolor.min_grey_frequency_percent` | 30 | 灰度判定频率阈值（%） |
| `persist.navcolor.max_blend_color_variance` | 2000 | 混合色方差阈值 |
| `persist.navcolor.grey_scale_method` | "luma" | 灰度计算方法 |
| `persist.navcolor.num_grey_scale_level` | 3 | 灰度分段数 |
| `persist.navcolor.trace` / `viewcheck` / `viewfind` / `debug.draw_view_tree` / `sf_color` | false | 调试日志开关 |

### 6.2 位图采样常量

| 常量 | 值 | 含义 |
|---|---|---|
| `BITMAP_SAMPLE_WIDTH` | 30 | 采样位图宽（px） |
| `BITMAP_SAMPLE_HEIGHT` | 1 | 采样位图高（px） |
| `BITMAP_NAVZONE_OFFSET` | 2 | 导航栏区域偏移（px） |
| `BACKGROUND_COLOR_STATE_NULL` | -1 | 背景色状态：空 |
| `BACKGROUND_COLOR_STATE_TRANSLUCENT` | 0 | 背景色状态：透明 |
| `BACKGROUND_COLOR_STATE_NOT_FOUND` | 1 | 背景色状态：未找到 |

### 6.3 窗口/系统标志

| 值 | 含义 |
|---|---|
| `0x80000000` | FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS（窗口自绘系统栏背景） |
| `0x200` | SYSTEM_UI_FLAG_HIDE_NAVIGATION / APPEARANCE_LIGHT_NAVIGATION_BARS |
| `0x2` | SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION |

---

## 七、附录：逆向涉及文件清单

### services（system_server，`miui-services.jar` → classes.dex → 6,918 个 smali）

| 文件 | 内容 |
|---|---|
| `com/android/nbi/MiuiNBIManagerService.smali` | SystemService 入口（SERVICE_NAME = "miui_navigation_bar_immersive"） |
| `com/android/nbi/MiuiNBIManagerService$Inner.smali` | Binder 服务端（IMiuiNBI.Stub）：getSystemNBIRules / 采样注册 / 云控同步 |
| `com/android/nbi/MiuiNBIManagerService$Shell.smali` | shell 命令（list/enable/disable/disableVersionCode/activityRule/update/...） |
| `com/android/nbi/MiuiNBIManagerService$Inner$1..3.smali` | 用户切换广播 / 云控 Handler / ContentObserver |
| `com/android/nbi/MiuiNBIController.smali` | 规则引擎（生效/云控规则、Bundle 组装、云控更新） |
| `com/android/nbi/MiuiNBIRule.smali` + `$ActivityRule` + `$ViewRule` | 数据模型 |
| `com/android/nbi/MiuiParsingNBIRule.smali` | JSON 解析、云控/本地选择、写 cloudFeature 文件（660） |
| `com/android/nbi/MiuiNBIServiceStubHeadImpl.smali` | 扩展 `com.android.server.wm.MiuiNBIServiceStubHead`（仅初始化日志） |

### framework（应用进程，`miui-framework.jar` → classes.dex → 4,681 个 smali）

| 文件 | 内容 |
|---|---|
| `com/android/internal/policy/NavigationBarImmersiveController.smali` | **核心引擎（6514 行）**：视图树分析、规则分发、位图/SF 采样、颜色设置 |
| `com/android/internal/policy/DecorViewImmersiveImpl.smali` | DecorView 生命周期桥接（948 行） |
| `com/android/internal/policy/MiuiNBIManagerImpl.smali` | MiuiNBIManagerStub 实现：init / getActivityRuleInfo / allowSystemOverride / 手势设置缓存 |
| `android/app/ActivityThreadImpl.smali` | 进程初始化（NBI preInit 入口，约 1584-1595 行） |

### 未包含

- `com.miui.nbi.*`（`MiuiNBIManagerStub`、`IMiuiNBI`、`MiuiNBIManager`、`ActivityRuleInfo`）—— 独立 API 构件，不在两个 jar 内。
- `CompositionSamplingListener` / `SamplingListenerArgs` / `ColorMathUtils` / `ColorResult` / `ApplicationBottomViewCheckUtil` / `ViewAnalysisResult` —— 位于 framework 其他模块，本报告从调用侧推断其契约。

---

*报告生成：基于 baksmali 2.5.2 反汇编结果逐类精读；所有行号对应 smali 文件。*
