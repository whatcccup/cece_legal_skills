# cece_legal_skills

合同脱敏工具 **v1.2.1**：提供 Mac 和 Windows ZIP 包；安装依赖后在本机离线运行，不需要 AI 客户端、模型账号或 API Key。

## 下载与安装

- [官网介绍与安装说明](https://legaltechcc.com/workflows/contract-desensitizer/#install)
- [下载 Mac 版](https://legaltechcc.com/assets/downloads/contract-desensitizer-mac-1.2.1.zip)
- [下载 Windows 版](https://legaltechcc.com/assets/downloads/contract-desensitizer-windows-1.2.1.zip)
- [源码、手动安装与测试](001-contract-desensitizer/01-source/README.md)
- [给普通用户和 AI Agent 的安装说明](001-contract-desensitizer/01-source/开始使用.md)

先完整解压 ZIP，不要在压缩包内直接启动。Mac 双击外层“合同脱敏工具.app”。Windows 双击文件夹里的 `Start.vbs`；不要单独移动或删除 `Start.vbs`、`Start.bat` 和 `_support`，需要换位置时把整个文件夹一起移动。首次需要 Python 3.9+ 和联网安装依赖；Windows 启动器已静态检查，尚未完成实机验证。

macOS 若提示无法验证开发者，请先尝试打开，再到“系统设置 → 隐私与安全性 → 安全性 → 仍要打开”确认。启动失败与端口占用的排查见[安装说明](001-contract-desensitizer/01-source/开始使用.md)。

## 使用与保密

支持 Word、文字型 PDF、TXT、Markdown，识别结果需人工复核。默认导出“对外脱敏稿”，不附带原文映射；“内部可逆稿”仅用于 Word，内嵌原文映射，应按原合同等级保管，不能直接对外发送。扫描件需要先 OCR。

官网 ZIP 附带同版本源码与测试；官网同名 JSON 记录源码提交及 SHA-256。唯一源码入口为 `001-contract-desensitizer/01-source`。SkillHub v1.2.1 已上线，核心代码、依赖与规则已与官网逐文件核对。[查看与安装](https://skillhub.cn/skills/user_dd9a2596/contract-desensitizer-offline)。

公众号兼容入口：[contract_desentizier](contract_desentizier/README.md)、[contract_desensitizer](contract_desensitizer/README.md)；旧仓库链接继续保留导航用途。

## 仓库目录

- `001-contract-desensitizer/01-source/`：源码、启动器、规则、安装说明和测试。
- `001-contract-desensitizer/02-github/`：变更记录、发布清单。
- `001-contract-desensitizer/03-skillhub/`：SkillHub 发布形态，需另行构建和上架。
- `001-contract-desensitizer/90-build/`：构建脚本。
- `templates/`：其他技能的文档模板。

<details>
<summary><b>维护者专区</b>（目录规范 / README 规范 / 发版流程 / 上架硬约束）—— 普通使用者不用展开</summary>

### 目录规范

一个技能 = 一个编号文件夹。编号从 `001` 起，**只增不复用、不重排**；已发布的技能即使改名也保留原号。

| 目录 | 性质 | 装什么 | 是否入库 |
|---|---|---|---|
| `01-source/` | 定稿·**唯一真源** | 完整可运行工程：源码、规则、启动器、截图、测试、完整教程 | ✅ |
| `02-github/` | 定稿·发布物料 | `CHANGELOG.md`、`RELEASE-CHECKLIST.md` 等只在 GitHub 侧用的物料 | ✅ |
| `03-skillhub/` | 定稿·发布形态 | `SKILL.md` + `scripts/` + `references/` + `tests/` | ✅ |
| `90-build/` | 构建产物 | 构建 / 发布脚本 + 生成的 zip | 脚本 ✅，产物 ❌ |
| `99-temp/` | 临时 | 运行会话、识别报告、脱敏稿、mapping、测试样本 | ❌（含敏感信息） |

**关联与边界**

- 源码只有一个真源 `01-source/`；`03-skillhub/scripts/` 由 `build.sh` 同步，**禁止手改**，否则下次构建被覆盖。
- 技能包里手写的只有两样：`SKILL.md`、`scripts/launcher/start.py`（`.bat`/`.vbs`/`.sh` 会被上架拦截，只能用 `.py`）。
- GitHub 发布内容 = `README.md` + `01-source/` + `02-github/`；SkillHub 发布内容 = `03-skillhub/`。
- `.gitignore` 里带斜杠的模式只匹配仓库根，多技能必须写 `**/90-build/*.zip`、`**/99-temp/*`。

### SkillHub 上架硬约束（踩过坑）

- 技能包里**不能出现** `.bat` / `.vbs` / `.sh` / `.exe`，否则报 `400 不允许的文件类型`。
- `SKILL.md` frontmatter 必须有：`slug`（kebab-case，全网唯一）、`version`（三段 SemVer）、`displayName`。
- 同一 skillId 可重复 publish 新版本号，`tags.latest` 会自动跟到新版，不需要先撤销旧版。
- 推送 GitHub 若报 `CONNECT tunnel failed 502`，是本机代理挂了，绕开代理即可：
  `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy -u ALL_PROXY -u all_proxy git push origin HEAD`

### README 规范

每个技能必须有 `README.md`（技能卡片），六段，**顺序与小标题固定**，缺失写「待补」不要删：

| 段 | 标题 | 写什么 |
|---|---|---|
| 1 | 一句话定位 | 用户角色 + 场景 + 结果，两行以内 |
| 2 | 快速开始 | 推荐安装方式的一句话 Prompt（可直接复制）+ 一条手动命令 |
| 3 | 能力边界 | 支持 / 不支持 / 已知限制 / 合规红线，用表格 |
| 4 | 目录地图 | 本技能五个目录各装什么 |
| 5 | 维护说明 | 改哪里、怎么自检、怎么发两个版本、什么是禁止操作 |
| 6 | 许可与来源 | 许可、仓库地址、SkillHub 地址 |

模板：[templates/skill-README.md](templates/skill-README.md)

### 发版流程

```bash
# 1) 改代码：只动 01-source/
# 2) 一键同步 + 自检 + 打包 + 预检
bash 001-contract-desensitizer/90-build/build.sh

# 3) 发 GitHub 版（本仓库即 GitHub 仓库）
git add -A && git commit -m "..." && git push

# 4) 发 SkillHub 版：先改 03-skillhub/SKILL.md 的 version（SemVer），再发布
skillhub publish 001-contract-desensitizer/03-skillhub --changelog "..."
```

发版前按 `001-contract-desensitizer/02-github/RELEASE-CHECKLIST.md` 逐条打勾。

</details>

---

## 许可

[MIT](LICENSE) © 2026 whatcccup
