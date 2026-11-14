# 本地交付工作台

从仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe frontend/server.py --port 8438
```

打开 `http://127.0.0.1:8438/`。真实 Maven 测试需要通过 `--java-home`、`--maven` 指定本机工具链，参数示例见 `server.py`。

- 实时模式：输入运行标识与任务，启动流程，在 G1、发布授权及阻断节点操作。
- 回放模式：选择或拖入导出的证据 JSON，逐事件播放；概览显示交付最终结果，画布显示当前回放事件。
- 点击概览卡片或导航可打开门禁、事件、产物和运行说明。审计面板支持 Escape 关闭、Tab 焦点循环及方向键切换分类；回放进度支持方向键、Home 和 End。
- 浅色/深色主题和当前运行标识保存在浏览器本地；不需要外部字体、图标 CDN 或前端构建工具。

页面结构为 `index.html`，交互为 `workbench.js`，场景与审计基础样式为 `scenes.css`，布局与主题为 `workbench.css`。

当前工作台连接既有 Phase 1 本地演示流程：脚本角色、真实本地测试、模拟发布及演示身份。Phase 3 的真实发布和 Phase 4 的记忆治理尚未接入此界面。

后端门面回归：

```powershell
.\.venv\Scripts\python.exe -m pytest src/agentloop/tests/test_workbench.py -q
node --check frontend/workbench.js
```
