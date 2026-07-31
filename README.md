# 服装设计专家 Agent

这是一个完全自包含的服装设计专家包。它内置服装设计 Skill、十阶段专业工作流、交付模板和质量检查清单，并以 YM30 Remote Capability Provider（RCP）Protocol 1.1 的 HTTPS 服务形式运行。

## 能力

- 季节、胶囊系列、品类和 SKU 企划
- 单款服装开发
- 参考款分析与差异化延展
- 效果图、技术款式图和展板的文字 brief 与提示词
- 样衣评审与可验证的修改意见
- 产品故事、特征、升级点与有证据约束的卖点

首版不直接生成图片或二进制文件，也不申请 YM30 Data API 权限。

## 环境要求

- Python 3.11 或更高版本
- 豆包火山方舟 API Key 和可调用的模型名或 Endpoint ID
- 可选的 DeepSeek API Key，用于豆包暂时不可用时降级
- YM30 Provider 的 Key ID 和一次性 Signing Secret
- 生产环境建议使用 Redis

## 本地启动

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

把 `.env` 中的值配置到当前 shell 或部署平台的 Secret Manager。不要把 `.env` 提交到 Git。

如果模型密钥曾经粘贴到聊天、工单或其他非 Secret Manager 环境，正式部署前先在对应控制台轮换密钥。

豆包默认使用：

```text
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
```

`DOUBAO_API_KEY` 是调用密钥，`DOUBAO_MODEL` 是模型名或推理 Endpoint ID，两者不是同一个值。

DeepSeek 默认使用：

```text
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

加载环境变量后启动：

```bash
uvicorn app.main:app --reload --port 8000
curl http://127.0.0.1:8000/health
```

健康检查应返回：

```json
{"ok": true}
```

本地签名联调：

```bash
python tests/sign_test.py --base-url http://127.0.0.1:8000
```

签名基于 HTTP 原始 body bytes。服务拒绝超过 5 分钟的请求，并将 nonce 保留至少 10 分钟以防止重放。

## Docker

```bash
docker build -t fashion-design-expert:1.0.0 .
docker run --rm -p 8000:8000 --env-file .env fashion-design-expert:1.0.0
```

生产环境不要把 `.env` 烘焙进镜像。通过部署平台的 Secret Manager 注入密钥。

## 提交到 YM30

1. 在开发者门户创建远程能力提供方。
2. namespace 与 `manifest/ym30-manifest.json` 的 `name` 保持一致。示例值是 `ym30.fashion-design-expert`；若门户使用其他 namespace，提交前修改 Manifest。
3. 保存只展示一次的 Provider Signing Secret。
4. 将服务部署到公网 HTTPS：
   - 有效 DNS 与证书
   - 443 端口
   - endpoint 只填写 origin 根地址
   - 不包含路径、query、fragment、用户名或密码
   - 不依赖 301/302 重定向
5. 在 Provider 页面提交 `manifest/ym30-manifest.json`，版本号填写 `1.0.0`，执行模式选择 `sync`，对话上下文选择 `none`。
6. 等待版本审核。
7. 请平台对接人为目标 tenant 完成授权。只有审核和 tenant grant 都完成后，YM30 对话才会调用该能力。

## 生产检查

- 使用 Redis 实现跨实例 nonce 原子 claim 和 execution ID 幂等结果。
- 服务器开启 NTP，保持时钟准确。
- 轮换 YM30 Signing Secret 时，先准备新部署配置；旧 Secret 会立即失效。
- 日志只记录 trace ID、execution ID、capability ID、提供方、延迟和错误类别。
- 日志不得记录密钥、签名、完整请求正文或用户参考资料。
- 仅申请能力真正需要的最小权限；当前 Manifest 不申请任何 data 或 tool scope。

## 测试

```bash
python -m pytest -v
```

专家知识位于 `expert/`，YM30 适配层位于 `app/`。迁移到其他 Agent 平台时，可保留 `expert/` 并替换传输适配层。
