# Outlook 号为何被锁/被封 + 防封清单 + 保活用法

## 一、为什么会被锁 / 被封（结论）

新注册的 outlook.com/hotmail.com 号处于**高风控观察期**，触发以下任一都可能被要求二次验证、锁定（需手机验证）或直接封停：

1. **同 IP 批量**：同一出口 IP 短时间注册/登录多个号是最强信号。数据中心/机房 IP、被标记的代理尤甚；住宅/移动 IP 存活率明显更高。
2. **新号立即高频操作**：注册完马上大量 API 调用、登录、发信 —— 新号应有“冷启动”缓冲。
3. **频繁刷新 / 频繁协议登录**：短周期内反复 refresh_token 换 access_token、反复 XOAUTH2 登录，形成机器特征。
4. **协议登录（IMAP/POP/SMTP）触发风控**：新号 IMAP 默认关闭，强行走协议登录（XOAUTH2）会“authenticated but not connected”，反复尝试是风险信号 —— 这也是我们默认走 Graph/REST 而非 IMAP 的原因。
5. **指纹/环境异常**：headless、缺失常见浏览器指纹、UA 与 IP 地区/语言不一致。
6. **收信内容触发**：短期内被判为垃圾/钓鱼相关活动。
7. **完全不用**：注册后长期零活动的号也会被回收（inactivity）。

## 二、可执行防封清单

- **IP（一号一 IP，最重要）**：优先住宅/移动代理，**代理串必须带 `{sid}` 占位符**（如 `host:port:user:pass-US-{sid}`）。批量注册时引擎会为每个账号展开**唯一** `{sid}` → 每号一个独立 sticky 会话 → 出口 IP 互不相同。**缺 `{sid}` 会全批共用同一出口 IP（同 IP 批量=最强封号信号），引擎会在日志里警告。** 注册地区、`--country`、`mkt/lc` 与 IP 地区一致；数据中心/机房代理（如 kookeey `gate.*`）存活率低，尽量换住宅/移动。
- **节奏（启动错峰）**：批量注册相邻账号按 `OUTLOOK_REG_JITTER_MIN/MAX`（默认 **3–8 秒**，CLI `--jitter-min/--jitter-max`）随机间隔启动，避免同一时刻爆发式注册。注册后**不要立刻猛用**（冷启动）；保活**低频**（建议每号每 **2–3 天**一次，不要每小时刷）。
- **并发**：批量注册默认 **2**（1 最稳）；Web 前端按输入值执行、上限 20，但强烈建议 1–2。一 worker/一号独占一条唯一代理会话，单 IP 每天 ≤2 个号。
- **Proofs**：默认 **禁止** cancel 跳过（`OUTLOOK_SKIP_PROOFS=0`）。须配置外部恢复邮箱池（login.exe 同款）：
  ```bash
  export OUTLOOK_EXTERNAL_RECOVERY_POOL_FILE=/path/recovery_pool.txt   # 每行 email----password
  export OUTLOOK_RECOVERY_IMAP_HOST=imap.your-recovery-host.com   # 按你的收码服务商填写
  ```
  成功产出六段式写入 `accounts_recovery.txt`（email----pwd----cid----rt----recovery_email----recovery_pwd）。
- **locale**：`mkt/lc` 随 `--country` 联动（US 代理用 `--country US` → EN-US/1033）。
- **读信走 Graph/REST**，不要对新号强开/强连 IMAP（默认已如此）。
- **刷新克制**：access_token 有效期内复用，不要每次操作都刷 refresh_token。
- **轮换保存**：每次刷新若返回新 refresh_token 就**存回**（本项目 keepalive 已做），避免旧 token 失效后误判为“号废了”。
- **保活动作拟人**：只读 profile + 列 1 封信即可，别每次都全量拉信/发信。
- **失效隔离**：`invalid_grant` / 换不到 token 的号及时标记下线，别继续硬打。
- **分池管理**：注册产出与收码池分开；回补进池前先 `probe_token` 校验 graph=200。

## 三、保活脚本用法（scripts/keepalive.py）

```bash
# 基本：对四段/六段账号文件逐个保活，写到 <file>.refreshed，失效号另存 <file>.dead
python3 scripts/keepalive.py --file accounts/accounts.txt --concurrency 5

# 带代理（host:port:user:pass 或 http://user:pass@host:port）
python3 scripts/keepalive.py --file accounts/accounts.txt --proxy 1.2.3.4:8000:user:pass

# 原地重写（用轮换后的新 refresh_token 覆盖旧行；失效行前加 "# DEAD"）
python3 scripts/keepalive.py --file accounts/accounts.txt --inplace
```

每号做：`refresh_token → access_token` → `GET /me` + 列 1 封信 → 若返回新 refresh_token 则回写。
输出：`[OK] ab***@outlook.com profile=True msg=True rotated=True` / `[DEAD] ...`。
六段行只保活/回写第 4 段（graph_refresh），第 6 段（login_refresh）原样保留。

## 四、收码池回补（scripts/replenish_pool.py）

收码池会被消耗（每次 proofs 用一个老号收 OTT），需持续回补：

```bash
# 把注册产出的 accounts.txt 里 graph=200 的号去重追加进池（默认池 = 1000outlook.txt 或 OUTLOOK_PROOF_POOL_FILE）
python3 scripts/replenish_pool.py --from accounts/accounts.txt

# 指定池文件；或直接补一条
python3 scripts/replenish_pool.py --from accounts/accounts_dual.txt --pool /path/1000outlook.txt
python3 scripts/replenish_pool.py --combo "email----pwd----cid----M.C..."
```

六段来源自动取前四段（graph 部分）入池；追加前按邮箱去重、按 `probe_token` 校验（可 `--no-verify` 跳过）。

> 建议闭环：注册 → `replenish_pool.py` 回补新号入池 → 定期 `keepalive.py` 保活池与产出号，形成自持。
