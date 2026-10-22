# 事件—证据候选关联草稿

`event_evidence_candidate_drafts.jsonl` 一行对应一张金标准事件模板。每行的 `event` 保留
`event_id`、`duration_seconds`、`channel_count` 和 `scope`；每行的三项 `evidence` 以
`evidence_id` 关联 `evidencecard/cards/` 中既有的人工证据卡，并内嵌其正文。

候选 `evidence_id` 由冻结的检索器给出，每张事件保留 Top-3；它们是待人工判断的候选，
**不是**金标准正例。人工标注时：

1. 在各 `evidence[].annotation` 中标记 `direct_support`、`related_but_insufficient` 或
   `not_relevant`；
2. 仅将 `direct_support` 的 `evidence_id` 写入 `gold_action_links`，并关联相应的固定
   `action_id`；
3. 所有候选审阅完成后，才将 `annotation_status` 改为 `confirmed`。

不要在此文件复制证据文本或文献路径；`evidence_id` 已可通过证据卡回溯到来源文献和行号。
