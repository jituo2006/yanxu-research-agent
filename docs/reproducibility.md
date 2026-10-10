# 运行与复现

正式支持环境：Windows、Python 3.12、Node.js 22.12+。

在仓库根目录运行：

```powershell
powershell -File scripts/setup.ps1
powershell -File scripts/start.ps1
```

打开 http://127.0.0.1:8920/，检查页面与 `/api/health` 的版本。连接设置中填写模型与财务数据凭据，勿放入研究对话。停止前在页面取消任务，待请求返回，再运行 `powershell -File scripts/stop.ps1`。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
cd web
npm run build
```

默认数据在var中；`RESEARCH_DATA_DIR` 可指定独立目录。密钥文件不得进入提交包。Windows DPAPI及扫描OCR有平台限制；非Windows环境可验证无密钥/无OCR路径，不代表全部能力跨平台验收。

样例材料和金标准见 [examples](../examples/README.md)。离线样例是确定性回放；真实智能体运行需可用模型。当前研究导出与完整审计导出分开，ZIP包含原材料及哈希；外部网页链接不保证离线可访问。
