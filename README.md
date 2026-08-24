# outlook-auto-register

基于 Microsoft Outlook Fluent Web API 协议的账号注册工具。纯协议实现（HTTP 请求 + PerimeterX 打码），无浏览器依赖。

## 注册流程

```
OAuth 登录页 (PKCE)
  → signup.live.com/signup (解析 ServerData)
  → CheckAvailableSigninName
  → risk/initialize (空 continuationToken)
  → humanSensorUrl + PX collector 预加载
  → risk/verify #1 (px metadata + msaRiskVerifySignature)
  → [riskChallengeRequired] captcha.run press/silent
  → risk/verify #2 (challengeSolution + px metadata)
  → CreateAccount
  → oauth20_authorize.srf (slt 登录)
  → [proofs] 外部恢复邮箱 / 收码池 / (OUTLOOK_SKIP_PROOFS=1 时 cancel 跳过)
  → [可选] 跳过 Passkey / 获取邮件 OAuth refresh_token
```

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# 必填：CAPTCHA_RUN_API_KEY、HTTP_PROXY（住宅代理）
# 真实注册 proofs：OUTLOOK_EXTERNAL_RECOVERY_POOL_FILE + OUTLOOK_RECOVERY_IMAP_HOST
```

### CLI 注册

```bash
# 默认 graph 令牌（注册完即用 Graph 读信，推荐）
python main.py --proxy http://user:pass@host:port -v

# 指定后缀 / 国家（建议与代理地区一致）
python main.py --prefix myname2026 --domain @outlook.com --country US

# 仅注册，不完成 OAuth 登录（无 refresh_token）
python main.py --skip-login

# 注册但不换 refresh_token
python main.py --no-mail-token

# 批量（引擎并发）
python main.py --count 5 --concurrency 3
```

### 邮件令牌模式（环境变量 `OUTLOOK_MAIL_TOKEN_MODE`）

| 模式 | 说明 |
|---|---|
| `graph` | **默认**。Graph API 读信，注册完即用 |
| `outlook_rest` | Outlook REST API 读信，同样绕开 IMAP 开关 |
| `imap` | 传统 IMAP scope（仅老号 / 已开 IMAP 的号） |
| `dual` | 双令牌：Graph 收码 + 登录授权 SSO，产出 6 段 combo |

Web 控制台可在「Token 模式」下拉切换；选 `dual` 时运行期会设置 `DUAL_TOKEN=True` 并走 token#2 流程。

### 恢复邮箱 / proofs（真实注册必读）

```bash
# .env 示例（第三方 IMAP 恢复邮箱池，每行 email----password）
OUTLOOK_EXTERNAL_RECOVERY_POOL_FILE=/path/recovery_pool.txt
OUTLOOK_RECOVERY_IMAP_HOST=imap.your-recovery-host.com
OUTLOOK_RECOVERY_IMAP_PORT=993   # 可选，默认 993
```

成功绑定恢复邮箱后，账号 json 含 `combo_recovery`（6 段：email----pwd----cid----rt----recovery_email----recovery_pwd），并追加到 `accounts_recovery.txt`。

**禁止**用 cancel 跳过 proofs（批量 skip 是 abuse 主因）。仅调试时可显式开启：

```bash
OUTLOOK_SKIP_PROOFS=1   # 默认 0，未配置恢复池时不会自动 skip
```

### Web 控制台

```bash
.venv/bin/uvicorn webapp.server:app --host 0.0.0.0 --port 8890
```

打开 `http://127.0.0.1:8890`。**干跑默认开启**，取消勾选后才会真实注册。

### 打码平台自检

```bash
python scripts/ez_selftest.py
python scripts/captcha_run_selftest.py
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `CAPTCHA_RUN_API_KEY` | **推荐** captcha.run Bearer key（press/silent） |
| `CAPTCHA_RUN_API_BASE` | 默认 `https://apicn.captcha.run` |
| `HTTP_PROXY` | 住宅代理，`http://user:pass@host:port` 或 `host:port:user:pass` |
| `OUTLOOK_MAIL_TOKEN_MODE` | `graph` / `outlook_rest` / `imap` / `dual`（默认 graph） |
| `OUTLOOK_EXTERNAL_RECOVERY_POOL_FILE` | 外部恢复邮箱池文件（proofs 必填） |
| `OUTLOOK_RECOVERY_IMAP_HOST` | 恢复邮箱 IMAP 主机（proofs 必填） |
| `OUTLOOK_SKIP_PROOFS` | `1` 才允许 cancel 跳过 proofs（默认 `0`） |
| `OUTLOOK_LOGIN_CLIENT_ID` | dual 模式 token#2 客户端（默认同 Thunderbird） |
| `OUTLOOK_LOGIN_SCOPE` | dual 模式 token#2 scope |

完整变量见 `.env.example`。

## 项目结构

```
outlook-auto-register/
├── main.py                     # CLI 入口
├── outlook_api_reg/
│   ├── register.py             # 主编排
│   ├── bootstrap.py             # OAuth + PX 预加载
│   ├── api.py                   # API + msaRiskVerifySignature
│   ├── risk.py                  # 两步 risk/verify
│   ├── captcha.py               # captcha.run / CapSolver / EzCaptcha
│   ├── post_register.py         # slt + proofs + Passkey + 邮件 OAuth
│   ├── external_recovery_pool.py # IMAP 恢复邮箱池
│   ├── cf_domain_mail.py        # Cloudflare 域名 catch-all 收码后端
│   ├── database.py              # SQLite 统一存储
│   ├── proxy_pool.py            # 代理池管理
│   ├── proxy_utils.py           # 代理解析
│   ├── graph_mail.py            # Graph API 读信
│   ├── models.py                # 数据模型
│   └── constants.py             # 协议常量
├── px_solver/                   # PerimeterX 打码模块
│   ├── bit_px_solver.py         # 纯协议 PX solver
│   ├── ss_register.py           # SwiftShader 注册
│   ├── ss_post.py               # SwiftShader 后注册
│   └── docker/                  # Docker 批量环境
├── webapp/
│   ├── server.py                # FastAPI 控制台
│   └── static/index.html
├── scripts/                     # 辅助脚本
│   ├── backup_db.py
│   ├── keepalive.py
│   ├── rescue_login.py          # 账密重登换 token
│   └── ...
├── docs/
│   └── DATABASE.md              # SQLite 表结构说明
└── accounts/                    # 生成的账号数据（gitignored）
```

## 输出格式

| 格式 | 字段 |
|---|---|
| 四段（graph） | `email----password----client_id----refresh_token` |
| 六段（dual） | `…----login_client_id----login_refresh_token` |
| 六段（recovery） | `…----recovery_email----recovery_password` |

## 注意事项

1. **住宅代理必须**，且 **country 需与代理地区一致**（US 代理用 `--country US`）
2. **每个 session 不要反复压测**，易触发 `AADSTS7005106 riskBlock`
3. **PX 模式**仅 `solver`（纯协议 captcha.run，已移除浏览器/auto 方案）
4. 默认 **graph** 令牌；需要 IMAP scope 请设 `OUTLOOK_MAIL_TOKEN_MODE=imap`
5. 真实注册前配置 **恢复邮箱池**，否则 proofs 会失败（除非 `OUTLOOK_SKIP_PROOFS=1`）

## 防封策略

详见 `scripts/ANTIBAN.md`。

## License

GPL-3.0