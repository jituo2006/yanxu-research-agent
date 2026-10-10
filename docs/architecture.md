# 当前架构与能力边界

研序使用模型决定下一步、受限工具实际执行、工具结果进入下一轮的循环。普通对话不要求每次执行固定流程。后端为 FastAPI/SQLite，前端为 React/TypeScript；后台进程与浏览器请求分离，SSE 展示实际执行。

数据流：公开/上传材料 → 财务事实与来源 → Decimal 计算 → 问题与证据 → 估值情景与研究报告 → 当前稿/审计稿/证据包。

| 层 | 模块 | 责任 |
|---|---|---|
| 原始材料 | documents、ocr、disclosures、public_pdf、web_research | 检索、阅读、页码、日期和来源状态 |
| 事实与计算 | research、finance、valuation | 期间/单位、来源冲突、确定性计算、假设隔离 |
| 研究执行 | agent、deep_research、turn_constraints | 有界决策、用户限制、证据读取、反方审阅 |
| 保存与交付 | store、report_state、exporting、main | 原子版本、报告与估值关联、导出/API |
| 交互 | AgentChat、MemoView、ValuationLab | 研究对话、原文定位、情景与报告 |

当前自动结构化范围是两年年度营业收入、归母净利润与经营现金流；六种估值不等于六种自动完整建模。DCF 为恒定增速加永续终值，FCFF、桥接等尚需输入。引用校验不等于自然语言主张全部正确。

v0.4.0已实施受控比赛模式（competition）、派生事实状态（fact_state）和问题级证据清单（questions）。新字段兼容旧历史；旧材料与报告不自动覆盖。历史设计见 [v0.2](architecture-v0.2.md)，历史实测见 [v0.3.1验收](buy-side-review/acceptance.md)。
