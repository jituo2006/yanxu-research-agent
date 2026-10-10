# 受控比赛模式

应用层策略在进程启动时冻结，并传给后台进程。必须使用独立 `RESEARCH_DATA_DIR`；默认不许可任何网络。它限制应用的研究材料读取和网络入口，不是操作系统沙箱。

Windows：

```powershell
powershell -File scripts/start-competition.ps1 -Workspace .\var-competition -Policy .\examples\competition-policy.json
```

策略分别配置 `model_origins` 与 `retrieval_origins`，按协议、域名和端口精确匹配，无通配符。示例只许可DeepSeek模型接口，不许可资料联网。模型连接和凭据仍通过连接设置/环境变量配置；许可不意味着已配置可用模型。更换策略或工作区必须停止原服务并重启。

页面“比赛工作区”显示当前模式、许可与目录；导入JSON/CSV，选择已上传PDF，建立指定材料任务，下载提交包。PDF仍通过资料库上传。

JSON为行数组或 `{"rows":[...]}`，CSV为相同字段：metric、year、value、unit、currency、scope、period_type、announced_date。目前支持三项核心年度指标，单位元/千元/万元，CNY、consolidated、annual；每行公告日不晚于截止日。缺公告日的行保留缺口，不合入事实；未知指标不并入现有计算。导入数据属于单源材料，不自动升级为独立双源核验。

[示例CSV](../../examples/competition-financials.csv)是合成数字，只用于流程测试，不能当作美的或其他真实公司财务。

CLI也可处理固定任务（PDF扫描OCR仍有Windows限制）：

```sh
python scripts/run_competition.py --workspace var-competition --ticker 000333.SZ --year 2025 --as-of 2026-09-28 --material examples/competition-financials.csv
```

默认不调用模型，加 `--model --policy examples/competition-policy.json` 才运行真实深度研究；无凭据或失败会以非零退出，不能冒充真实LLM成功。

材料索引和读取记录路径、SHA-256；网络许可逐跳检查，模型请求/响应、工具参数/结果、研究快照和计算保存在competition-audit.sqlite3。提交ZIP包括材料、报告、计算、工作区审计、源码/依赖标识和哈希；不包含connections.json、.env、worker日志及密钥请求头。审计覆盖工作区所有任务，给第三方前应选择独立比赛目录。

固定目录仅包含应用DATA和内置examples中的研究材料，阻止目录逃逸和符号链接逃逸。配置和源代码的启动读取为可信运行资源，不作为Agent资料接口开放。网络阻止的实际隔离仍应由比赛机器/防火墙提供。
