<div align="center">

# HyperNavBar Rules

### HyperNavBar 规则列表

[文档](document.md) | [适配教程](docs/tutorial.md) | [更新日志](changelog.md) | [Telegram 群组](https://t.me/HyperNavBar)

[![GitHub License](https://img.shields.io/github/license/HyperNavBar/HyperNavBar)](LICENSE)
[![GitHub Issues](https://img.shields.io/github/issues/HyperNavBar/HyperNavBar)](https://github.com/HyperNavBar/HyperNavBar/issues)
[![GitHub PRs](https://img.shields.io/github/issues-pr/HyperNavBar/HyperNavBar)](https://github.com/HyperNavBar/HyperNavBar/pulls)

</div>

**HyperNavBar Rules** 是 [HyperNavBar](https://github.com/HyperNavBar/HyperNavBar)的维护规则列表，用于管理第三方应用的导航栏沉浸优化规则。

<br>

# 交流 & 反馈群组

[![tg_badge]][tg_url]

加入我们所创建的群组以反馈问题，或了解最新情况

<br>

# 如何使用

### 规则源

使用 HyperNavBar 应用时，需要**同时应用两个规则源**：

- **官方规则源**（`official.json`）- 系统原始配置，由小米官方维护，作为基础规则
- **社区规则源**（`custom.json`）- 自定义优化规则，由本项目社区维护，包含对官方规则的补充和修正

> **顺序说明**：在应用的订阅列表中，请将**社区规则源放在上方**、**官方规则源放在下方**。社区规则源优先级更高，会覆盖官方规则源中相同应用的规则；官方规则源作为基底提供系统默认规则。

> 社区规则源只包含与官方不同的自定义规则，因此必须与官方规则源配合使用，单独使用社区规则源会导致大量应用无法适配。

### 使用方式

1. 安装 [HyperNavBar](https://github.com/HyperNavBar/HyperNavBar) 应用
2. 在「规则」页中添加订阅，或从预设列表获取：
   - **社区规则源**（在上）
   - **官方规则源**（在下）
3. 应用规则即可生效

> 新版本应用首次启动时会自动添加以上两个默认订阅，无需手动配置。

<br>

# 如何贡献

### 相关信息

[点击此处](document.md) 查看完整适配说明  
[点击此处](docs/tutorial.md) 查看适配教程  
[点击此处](changelog.md) 查看规则更新日志  
[前往 Telegram 群组](https://t.me/HyperNavBar) 与其他贡献者交流

### 遇到问题？

[前往 Issue](https://github.com/HyperNavBar/HyperNavBar/issues) 或 [Telegram 群组](https://t.me/HyperNavBar) 提出适配应用要求

## 我想贡献！

[提交 Pull Request](https://github.com/HyperNavBar/HyperNavBar/pulls) 参与仓库贡献  
[前往 Discussions](https://github.com/HyperNavBar/HyperNavBar/discussions) 查看其它适配经验分享，或分享你的经验

<br>

# Star History

[![Star History Chart](https://api.star-history.com/svg?repos=HyperNavBar/HyperNavBarRules&type=Date)](https://www.star-history.com/#HyperNavBar/HyperNavBarRules&Date)

[tg_badge]: https://img.shields.io/badge/TG-群组-4991D3?logo=telegram

[tg_url]: https://t.me/HyperNavBar
