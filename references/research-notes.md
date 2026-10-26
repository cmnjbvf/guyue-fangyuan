# 同类机制与本地取舍

查证日期：2026-10-20。以下链接是设计依据，外部产品的指标不作为本地效果。本 Skill 未自动安装或调用这些框架；明确区分已实现的轻量机制、指令层方法与待选适配器。

| 一手来源 | 借用机制 | 本地落点和限制 |
|---|---|---|
| [DoclingDocument](https://docling-project.github.io/docling/concepts/docling_document/) | 统一表达文本、表格、章节和可用来源定位 | 输入适配规定保留结构与出处；Docling 本体仅为待选解析器，OCR与表格准确性需样本验证 |
| [Unstructured chunking](https://docs.unstructured.io/open-source/core-functionality/chunking) | 先识别文档元素，再按标题/章节分段；表格单独处理 | 指令层要求结构优先和表头回读；辅助脚本只做保真字符分段，不冒充结构解析器 |
| [LlamaIndex IngestionPipeline](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/) | 文档身份、内容哈希、转换缓存与持久化分开 | 本地脚本记录原件/正文哈希、批次配置与收据，支持中断续跑；未接向量库或自动增量缓存 |
| [Anthropic Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval) | 为片段补足文档内定位上下文，缓解孤立块歧义 | 指令层回读父节与邻段；脚本分开返回上下文和证据正文。未实现 contextual embeddings/BM25，也不引用外部提升百分比作为本地收益 |
| [GraphRAG outputs](https://microsoft.github.io/graphrag/index/outputs/) | documents、text units 与知识对象分别建模并关联 | 借用原文→片段→知识项→综合结论映射，不上完整图谱；引用存在不等于关系正确 |
| [FActScore 论文](https://aclanthology.org/2023.emnlp-main.741/) | 将长文本拆成原子命题，评估来源支持 | 蒸馏逐条核对主张；另查关键遗漏、条件和反例。不是调用 FActScore，也不把 factual precision 当完整召回 |

## 已确认的取舍

优先解决来源完整性、精读范围、证据定位、恢复和语义复核。先使用当前可用文档工具；只有真实样本显示解析或召回瓶颈，才比较专用解析器、混合检索、重排或图谱。生成的上下文和综合摘要不进入原始证据字段。

目前没有真实用户大规模异构资料的受控对照；合成与独立任务试用只能证明其测试范围。将来评估解析器时，以扫描多栏、合并表格、脚注、否定和跨段条件为样本，固定人工标注后比较定位、关键知识和条件保留，而不是比较支持格式数量。
