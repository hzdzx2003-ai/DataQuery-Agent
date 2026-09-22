# 最小本地 UI

Streamlit 单页应用提供三种模式：

1. **已验证 Demo**：默认模式，只读取 Phase 3 去敏 Trace，不联网、不产生模型费用。
2. **本地规则体验**：只运行四路行为判断，展示澄清、披露或拒绝，不生成 SQL。
3. **Live Qwen**：仅在启动进程已经配置私有环境变量，且用户在页面再次确认后调用外部 API。

UI 不直接展示 execute 路由中的内部诊断文案。模型错误、数据库错误和英文异常只保留在开发 Trace；用户层只显示业务化说明。

启动方式：

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

默认访问 `http://localhost:8501`。第一版仅用于本地作品集演示，不部署公网。
