# V2 消化执行流程

仅现有领域知识库适配执行单卡、批量、重复检查、冲突处理或失败恢复时读取。本文件不定义其他领域的默认目的地；大规模原文覆盖另按 batch-processing.md。

## 单卡

1. 记录来源 ID、可用正文和读取状态。
2. 提取独立主张，标事实/经验/推断/偏好/未知。
3. 按检索场景决定拆卡边界。
4. 用标题、摘要、正文和已知别名做 Q3a；无增量不建卡。
5. 写 V2 候选卡及准确标题、正向、负向查询。
6. 运行 `dict-sync.py --card <路径> --candidate`。
7. 读取机器结果；失败只修首个有证据的问题，再重跑。

## 批量

- 批次大小按来源复杂度、错误成本和人工复核能力决定，不用固定数量作为知识规则。
- 所有草稿先进入 `.digest-staging/<来源>/`；不并发手改现役索引。
- 批内检查重复 ID/标题、矛盾主张、来源支持范围和真实关系。
- 运行 `dict-sync.py --staging <目录> --candidate`；同步器统一构建候选版本和派生产物。
- 中途失败保留已写 staging，报告首个失败路径、错误码和 active version；不删除、不推送、不自动切换。

## Q3a

- `duplicate_no_increment`：现役卡充分覆盖；不新建、不静默改卡。
- `incremental_candidate`：存在独立新增方法、边界、反例或来源支持；建候选并说明差异。
- `needs_review`：证据不足；保留候选/报告，不具备激活资格。

## 冲突和缺口

- 冲突必须写清两种说法、各自来源、适用范围和当前无法裁决的原因。
- 缺口进入报告或候选队列，不凭临场推断自动补成知识。
- “无法自动追溯”只表示追溯状态，不等于内容错误。

## 机器结果

至少检查：

- `status`: `candidate_pass` 或 `candidate_fail`
- `version`
- `changed_cards`
- `derived_artifacts`
- `gates`
- `activation_eligible`
- `active_version`
- `report`

退出非零、字段缺失或 active version 非预期时停止，不手写绕过。
