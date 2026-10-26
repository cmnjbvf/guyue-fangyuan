# V2 候选卡合同

仅现有领域知识库适配生成、审查或迁移 V2 候选卡时读取本文件。通用领域按目标项目合同，不强制 V1 兼容字段或领域分类。

## 基础字段

每张候选卡至少包含：

- `schema_version: 2`
- `id`：稳定、唯一、可读的机器 ID。
- `title`：准确表达可调用知识，不用来源名冒充知识名。
- `summary`：一句话说明卡片能解决什么问题。
- `knowledge_kind`：知识性质；按实际内容使用 `rule`、`workflow`、`prompt`、`reference_stub` 或经接口冻结的其他值。
- `category`、`secondary_categories`
- `topics`、`aliases`
- `positive_triggers`、`negative_triggers`
- `when_to_use`、`when_not_to_use`
- `example_queries`
- `status`
- `source_id`、`source_summary`

兼容期同时保留 V1 消费者需要的 `type`、`tags`、`priority` 和 `source_group`。兼容字段不得与 V2 字段表达相反含义。

## 来源和高风险主张

普通方法卡保留稳定来源身份即可。以下主张按高风险处理：平台规则、法律合规、行业或收入数据、模型能力、带精确数字的时敏结论。

高风险卡追加：

- `claim_kind`
- `source_ref` 或稳定证据 ID
- `observed_at`
- `scope`
- `review_due`
- `evidence_state`

没有可靠证据时，来源仍可进入萃取，但卡片必须标 `experimental`、`quarantined` 或接口冻结后的等价状态；不得作为 verified 事实激活。不得凭空补 URL、日期、平台或数字。

## 索引桩

只有标题目录、少量样例或外部索引而没有完整正文时使用 `knowledge_kind: reference_stub`。summary、`when_to_use` 和 `when_not_to_use` 必须说明实际持有范围，禁止把“300+”“5000+”标题写成已拥有完整内容。

## 关系

只写有来源证据或明确人工判断的 `depends_on`、`conflicts_with`、`alternatives`、`see_also`。当前同步器没有消费关系时允许为空；不得用同目录前几张卡自动填充关系。

## 正文质量

正文只保留可调用知识：适用条件、操作方法、边界/反例和可检查结果。来源原文只做必要短引或转述，不搬运大段受版权保护内容，不在正文堆 URL 或本地绝对路径。
