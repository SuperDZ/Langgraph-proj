# Agent 模型配置与统一 API Key

控制台入口：`http://127.0.0.1:8439/console/` →「角色与模型」。

## 日常操作

1. 点击任意 Agent 卡片打开配置表单。
2. 选择参数模板，填写提供方实际支持的模型 ID，可设置最大输出 Token、Temperature、思考模式与推理强度、请求超时、重试次数、角色预算、步数、并发和有序后备模型。
3. 保存仅更新该角色的新运行配置，不修改其他角色的共享模型参数，也不修改已有运行的不可变快照。
4. 「恢复继承默认」移除角色层覆盖，保留角色原有 Skills、提示词及权限策略。无其他引用的独立模型条目会被清理。
5. 下方「统一 API Key 管理」集中保存模型凭据。多个 Agent 可使用同一引用；当前在线适配器支持 DeepSeek。

模型 ID 是用户配置，不保证提供方当前支持。思考模式自动使用 `temperature=null`；后备链、凭据、HTTPS 端点和网络白名单仍经服务端有效配置校验。角色预算实际取四级配置的最小上限。

## 本机凭据

- Windows 使用当前用户 DPAPI 加密，保存于该工作台数据目录的 `credentials.dpapi`。数据目录默认位于 Git 忽略的 `.agentloop/` 中。
- 本机服务启动时加载该加密文件到服务进程环境；运行时继续用 `env:..._API_KEY` 引用，不需要把 Key 写入模型 JSON。
- HTTP 响应只含引用、配置状态和来源。明文不写入 SQLite、配置快照、审计或浏览器本地存储。输入框保存成功后清空。
- 可更新或移除本机保存值。移除后恢复服务启动前的环境变量值；如果原环境没有配置，就变为未配置。
- Linux 通过服务环境变量 `AGENTLOOP_CREDENTIAL_KEY_FILE` 指向单独保管的 Fernet 密钥文件。文件必须归服务账户所有，且其他用户无权访问（例如权限 `0600`）。工作台把加密数据写入 `credentials.fernet`；备份时应分开保管密钥与密文。未配置密钥时仍可通过服务环境变量提供 API Key。
- Windows DPAPI 文件绑定保存它的 Windows 用户。迁移时请在目标服务重新配置 API Key。
- 密钥轮换供后续请求使用。界面「已配置」表示存在值；此轮不会自动请求模型接口验证鉴权或消耗 Token。

## 验证

历史专项验证 10 项通过，覆盖角色参数隔离、恢复继承、后备链/思考参数/网络出口校验、旧运行快照、真实 Windows DPAPI 加解密/重开/轮换/移除，以及真实 HTTP 的 CSRF 和明文不落库。原始 JUnit 报告含本机主机名，仅保留在本地。

```powershell
.\.venv\Scripts\python.exe -m pytest src/agentloop/tests/test_model_settings.py src/agentloop/tests/test_phase5_http.py src/agentloop/tests/test_workbench.py -q
```

React 生产构建用 `frontend/console` 内的 `npm run build`。浏览器操作验证另覆盖角色弹窗、参数保存回读、错误提示、思考模式联动和窄屏布局。

实现依据：[Microsoft CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)、[CryptUnprotectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptunprotectdata)。
