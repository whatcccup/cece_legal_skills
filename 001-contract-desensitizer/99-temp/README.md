# 99-temp（临时内容，不入库）

放**跑起来才会产生**的东西：服务会话、识别报告、脱敏稿、mapping、测试样本。

| 子目录 | 内容 | 为什么不能入库 |
|---|---|---|
| `sessions/` | Web 服务的上传会话：原始合同、脱敏稿、`*.mapping.json` | **含真实敏感信息**，等同原件 |
| `reports/` | `--out-dir` 产出的识别报告（json / csv / txt / html） | 同样含原文片段 |
| `samples/` | 拿来试的样本合同 | 多为真实合同 |

规则：

- 本目录已在根 `.gitignore` 中整体忽略，**只有这个 README.md 会被提交**
- 需要留证据时，只留**脱敏后**的截图，且先人工确认无残留
- 清理：`rm -rf 001-contract-desensitizer/99-temp/sessions/*`（不是仓库根目录，放心删）
- 真要归档样本，先脱敏，再放到 `01-source/tests/` 或 `docs/`
