# 现有领域知识库适配

仅在用户明确要求进入现有领域知识库、或当前已确认任务是维护该库时完整读取。本分支保留旧行为；其他领域和指定目标不得继承它的路径、分类与外发授权。

## 运行前

核对本次来源、Git 差异、暂存目录和当前 `知识卡片/_system/active-index.json`。实际指针决定现役版本，不使用历史“V1现役/V2候选”说明替代现场。

核对 `scripts/dict-sync.py`、`scripts/dict-evaluate-v2.py` 与 active pointer。候选命令会写派生产物，不称只读基线；只有当前已获授权的候选构建才运行。接口缺失可保留草稿和通用分析，停止依赖该接口的入库分支，不手写多套索引。

## 入库链

1. 来源精读与蒸馏按主入口进行；新卡先放 `.digest-staging/<来源>/`，不直接覆盖现役卡。
2. 完整读取 [card-contract-v2.md](card-contract-v2.md)、[digest-workflow-v2.md](digest-workflow-v2.md)；仅本分支保留 V1 兼容字段、Q3a 和既有分类合同。
3. 运行 `scripts\run-python-utf8.ps1 scripts\dict-sync.py --staging .digest-staging\<来源> --candidate`；单卡可用 `--card`，明确已改卡可用 `--changed`。读取 JSON 和退出码，核对 `status/version/changed_cards/derived_artifacts/gates/activation_eligible/active_version/report`。
4. 运行开发行为门 `scripts\run-python-utf8.ps1 scripts\dict-evaluate-v2.py`；新卡另测准确标题、正向、负向和高风险误用。候选门不会自动替新卡生成独立语义验收。
5. 接续 `dict-update` 做现有候选收尾；正式切换只在有效授权及认证、影子、回退门完成后进行。候选失败保留 staging 和报告，active 不变。
6. 分别报告新增、重复、失败、冲突、未追溯、高风险阻断、候选版本、门禁及资格。机械检查、语义采用与用户效果分开。

## 消化完成后的云端备份


用户已授权：在 `<工作区>` 完成一次知识字典消化且全部门禁通过后，将该批次追加备份到私人仓库 `https://github.com/cmnjbvf/ai-`。这是消化批次专用目标，不改变项目日常 `origin`，也不把授权扩展到其他任务或仓库。

1. 推送前回读确认 Git root、当前分支、HEAD、工作区和暂存区；再确认目标仍为 `cmnjbvf/ai-` 且 `isPrivate=true`。任一项不符就停止备份。
2. 只暂存本批新增或修改的候选卡、派生产物、批次报告和直接关联的字典文件。不得混入既有未提交差异、临时文件、日志、凭据或无关项目文件。
3. 相关门禁全部通过且 staged diff 已复核后，创建普通新 commit。没有文件变化时不制造空提交，并在报告中说明本批无新增备份内容。
4. 每次使用从未存在过的唯一远端分支 `digest-backup/YYYYMMDD-HHMMSS-<shortsha>`。推送前用 `git ls-remote` 确认分支不存在；若重名，生成新的时间后缀，禁止更新旧备份分支。
5. 不修改或新增 remote，直接使用普通非强制 push：

   ```powershell
   git push https://github.com/cmnjbvf/ai- HEAD:refs/heads/<唯一备份分支>
   ```

6. 禁止 amend、rebase、reset、`--no-verify`、force push、删除或重建远端分支、覆盖 tag、改写远端 `main`，以及任何覆盖历史的操作。
7. 推送后用 `git ls-remote` 回读新分支 SHA；只有远端 SHA 与本地 commit SHA 一致，才报告“已完成云端备份”。失败时保留本地安全结果并明确报告，不得换仓库或强推。


## 保留边界

知识卡正文和 frontmatter 是维护真相；索引、计数、搜索文档、版本和候选报告只由既有同步器派生。无增量重复不建卡、不静默改现役卡；关系只写有证据的依赖/冲突/替代，不自动填 siblings。不删除旧卡，不创建第二套字典或平行 Skill。真实 API、媒体与观众验证仍需各自证据。
