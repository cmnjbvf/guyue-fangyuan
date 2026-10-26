# 工具登记册

只登记**本机实际验证过**的东西。没装的不写用法，只写"为什么没装"。

## 已装并实测通过

| 工具 | 位置 | 用途 | 实测 |
|---|---|---|---|
| **MarkItDown 0.1.8** | `C:\Users\<user>\.workbuddy\binaries\python\envs\default\Scripts\markitdown.exe` | PDF / Word / PPT / Excel → Markdown | 11 页 PDF → 11,819 字，中文正常 |
| **Repomix 1.18.1** | `D:\tools\repomix` | 代码仓库 → 单文件 XML | 11 文件 → 17,277 tokens / 70KB，密钥扫描通过 |
| **REA** | MCP 已注册 | 二进制 / APK / ASAR / .NET 取证 | 无 Ghidra / IDA，原生反编译不可用 |
| **darwin-skill 2.1** | `~/.workbuddy/skills/darwin-skill` | 本技能的自我优化（9 维评分 + 独立盲评 + git 棘轮） | MIT，519 行，需 git 仓库回滚 |
| **crawl4ai** | `skills/crawl4ai-site-to-md` | 整站抓取 → Markdown | 已有 skill |

## 自优化：用达尔文跑一轮

本技能目录**已是 git 仓库**，基线 commit `cf38c36`。**不要删 `.git`** —— 达尔文的棘轮回滚靠它。

触发：说"用达尔文优化古月方源"或"给这个 skill 打分"。

它的实际流程（照抄它的 SKILL.md，不是猜的）：

1. **Phase 0**：`git rev-parse` 确认在仓库里，建分支 `auto-optimize/YYYYMMDD-HHMM`
2. **Phase 0.5**：设计 2–3 个测试提示（`test-prompts.json` 里有样例）
3. **Phase 1**：起独立 judge 按 9 维打分（结构 59 + 效果 35 + meta 6），记基线
4. **Phase 2**：**一轮只改分数最低的那一个维度**，改完 `git commit`，重新盲评；涨了保留，跌了 `git revert HEAD`（同-judge 配对比较，奇数评委多数决）
5. **Phase 3**：出报告 + 分数变化

三条纪律：

- **一轮只动一个维度**。多维度一起改，涨了也不知道是哪个改动起的作用
- **回滚用 `git revert`，不用 `git reset --hard`**（后者会丢未提交改动）
- 优化报告落在 skill 目录，**不要塞进 references** —— 那里是运行时读的，不是训练日志

## 调用要点

**本文件不写命令。** 命令只在各区手册里出现一次：

- MarkItDown 的调用 → `DOCUMENT.md` 取料一节
- Repomix 的调用 → `CODE.md` 取料一节
- REA 的调用 → `SOFTWARE.md` 按目标类型选工具一节

这样做的原因：命令写两处，改一处忘一处，就会静默漂移——执行时按老命令跑，报错还得排查半天。**单一真相源，别开第二份。**

## 没装，但知道为什么

| 工具 | 为什么不装 |
|---|---|
| **MinerU** | **已决定不装**（2026-10-21 用户拍板）。扫描件改走「页面截图 → 多模态模型直读」，零依赖且够用。仅当将来要**精确提取**复杂表格/公式、且反复遇到时才重新评估 |
| **Docling** | 表格最强（TEDS 0.97），但要拉模型权重。等真遇到复杂表格再装 |
| **code2prompt** | Rust 单二进制，模板化打包。功能与 Repomix 重叠，暂不装 |
| **Gitingest** | 零安装网页版，无压缩、单文件 50KB 截断。被 Repomix 覆盖 |
| **jadx** | APK → Java。等真拆 APK 时再装 |
| **Ghidra** | 9 万星，但安装包大。装了才能补上 REA 的原生反编译能力 |
| **LightRAG** | 抽实体关系建知识图谱（无 GPU）。适合"把一堆资料建成可查询的图"，不是单次炼化必需 |
| **Mem0** | 对话→事实的抽取管线，**其 ADD/UPDATE/DELETE 裁决思想已借鉴进 CONVERSATION.md**，不整装 |

## 已消失，别再找

| 项目 | 状态 |
|---|---|
| `sjzar/chatlog` | 2025-10 作者收到微信官方函件后删库，任何依赖它的方案都不成立 |

## 本机能力边界

**反编译引擎：没有。** `GHIDRA_INSTALL_DIR` 未设置，IDA 未安装。所以：

- 能用：包清单、JS/Electron、APK 结构、.NET 程序集、PE 资源、ELF 布局、core dump
- 不能用：把 exe / so 变成伪代码

补上它的两个选项：装 Ghidra 并配 `GHIDRA_INSTALL_DIR`；或者走黑盒路线（字符串 + 资源 + 包清单 + 网络行为），能回答"它大概怎么工作"，回答不了"具体哪一行"。

## 安装纪律

1. **装软件一律放 D 盘**，独立目录，删目录即卸载
2. **pip 补装用 `--no-deps --no-cache-dir`**：本机 pip 卸载包会被安全策略拦截（日志 `[safe-delete] SAFE_DELETE_FAIL_CLOSED`），卡在 `Uninstalling` 十几分钟不动。**这时不要强杀**——强杀会导致包被卸掉而新版没装上
3. **`markitdown[all]` 装不上**：它拉 Azure SDK，`azure-core` 本机无可用发行版。只装 `[pdf,docx,pptx,xlsx]`
4. 新增依赖必须说明理由，不为"万一用到"而装
