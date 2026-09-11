# cece_legal_skills

法务 / 法律场景的**离线小工具**集合。每个技能一个文件夹、互不依赖，可单独发布。

共同原则：

- **完全离线** —— 不调用大模型、不上传文件、不产生外联流量；
- **结果可复现** —— 依靠格式规则与国标校验位，而不是语义猜测，同样的输入永远得到同样的输出；
- **不折腾就能用** —— 每个技能既提供可一键安装的 AI Skill，也提供双击启动器，不做技术的人也能用。

---

## 技能索引

| 编号 | 技能 | 一句话定位 | GitHub | SkillHub |
|---|---|---|---|---|
| [001](001-contract-desensitizer/) | 合同脱敏 / 还原 | 把合同敏感信息换成可逆占位符，需要时一键还原 | ✅ | [contract-desensitizer-offline](https://skillhub.cn/skills/user_47430f88/contract-desensitizer-offline) |

新增技能：复制 `templates/skill-README.md` → 建 `NNN-<name>/` → 按下面两套规范填满。

---

## 目录规范

一个技能 = 一个编号文件夹。编号从 `001` 起，**只增不复用、不重排**；已发布的技能即使改名也保留原号。

```
cece_legal_skills/
├── README.md                     ← 本文件：总览 + 规范 + 索引
├── LICENSE
├── .gitignore
├── templates/
│   └── skill-README.md           ← 新技能 README 模板
└── NNN-<skill-name>/             ← 一个技能一个文件夹，三位数字排序
    ├── README.md                 ← 技能卡片（必须，按《README 规范》六段写）
    ├── 01-source/                ← 【定稿】唯一真源
    ├── 02-github/                ← 【定稿】GitHub 发布物料
    ├── 03-skillhub/              ← 【定稿】SkillHub 发布形态
    ├── 90-build/                 ← 【构建产物】脚本 + zip（zip 不入库）
    └── 99-temp/                  ← 【临时】会话 / 报告 / 样本（不入库）
```

### 五个目录的分工

| 目录 | 性质 | 装什么 | 是否入库 |
|---|---|---|---|
| `01-source/` | 定稿·**唯一真源** | 完整可运行工程：源码、规则、启动器、截图、测试、完整教程 | ✅ |
| `02-github/` | 定稿·发布物料 | `CHANGELOG.md`、`RELEASE-CHECKLIST.md` 等只在 GitHub 侧用的物料 | ✅ |
| `03-skillhub/` | 定稿·发布形态 | `SKILL.md` + `scripts/` + `references/` + `tests/`，即上传 SkillHub 的那份 | ✅ |
| `90-build/` | 构建产物 | 构建 / 发布脚本 + 生成的 zip | 脚本 ✅，产物 ❌ |
| `99-temp/` | 临时 | 运行会话、识别报告、脱敏稿、mapping、测试样本 | ❌（含敏感信息） |

### 关联与边界（重要）

- **源码只有一个真源**：`01-source/`。`03-skillhub/scripts/` 下的源码由 `90-build/build.sh` 从真源同步，**禁止手改**，否则下次构建被覆盖。
- **技能包里手写的只有两样**：`SKILL.md`、`scripts/launcher/` 里的跨平台启动器（`.bat`/`.vbs`/`.sh` 会被上架拦截，只能用 `.py`）。
  `scripts/` 下的引擎与 `references/` 下的文档全部由 `build.sh` 从真源同步。
- **GitHub 发布内容** = `README.md` + `01-source/` + `02-github/`（源码与物料都在这，GitHub 用户拿完整版）。
- **SkillHub 发布内容** = `03-skillhub/`（轻量化：不含 `.app` 二进制、不含截图，通常只有一百多 KB）。
- **两个发布形态不能手抄**：`build.sh` 负责同步，人负责写文档。

### SkillHub 上架硬约束（踩过坑）

- 技能包里**不能出现** `.bat` / `.vbs` / `.sh` / `.exe` 等可执行文件，否则报
  `400 不允许的文件类型`；跨平台启动一律用 `.py`。
- `SKILL.md` frontmatter 必须有：`slug`（kebab-case，全网唯一）、`version`（三段 SemVer）、
  `displayName`；建议带 `description_zh` / `description_en` / `license` / `homepage`。

---

## README 规范

### 每个技能必须有 `README.md`（技能卡片）

六段，**顺序与小标题固定**，缺失的段落写「待补」，不要删：

| 段 | 标题 | 写什么 |
|---|---|---|
| 1 | 一句话定位 | 用户角色 + 场景 + 结果，两行以内 |
| 2 | 快速开始 | 推荐安装方式的**一句话 Prompt**（可直接复制发给 AI Agent），再给一条手动命令 |
| 3 | 能力边界 | 支持 / 不支持 / 已知限制 / 合规红线，用表格 |
| 4 | 目录地图 | 本技能五个目录各装什么 |
| 5 | 维护说明 | 改哪里、怎么自检、怎么发 GitHub 版与 SkillHub 版、什么是禁止操作 |
| 6 | 许可与来源 | 许可、仓库地址、SkillHub 地址 |

模板：[templates/skill-README.md](templates/skill-README.md)

### 仓库根 `README.md`（本文件）必须维护

1. 共同原则（为什么这些技能长这样）
2. **技能索引表**：编号 / 名称 / 一句话定位 / 发布状态 —— 新增技能必须同步
3. 目录规范与 README 规范
4. 发版流程

---

## 发版流程

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

---

## 许可

[MIT](LICENSE) © 2026 whatcccup
