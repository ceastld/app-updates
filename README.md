# app-updates

多产品**版本检查 API**（Cloudflare Workers 静态资源 → `https://update.alinko.cc`）。

客户端当普通 HTTP API 用：`GET` 对应产品的 `version.json` 即可。本仓只放小体积清单；安装包 URL 指向 GitHub Releases、缤纷云或自有服务器。

## 端点

| 产品 | URL |
|------|-----|
| EA Clip / ClipHost | `https://update.alinko.cc/eaclip/version.json` |
| OmniTrigger | `https://update.alinko.cc/omnitrigger/version.json` |
| RaiShot | `https://update.alinko.cc/raishot/version.json` |
| cea.cliphost | `https://update.alinko.cc/cea.cliphost/version.json` |
| cea.cliphost.rust | `https://update.alinko.cc/cea.cliphost.rust/version.json` |
| cea.cliphost.rust.arm64 | `https://update.alinko.cc/cea.cliphost.rust.arm64/version.json` |
| 目录 | `https://update.alinko.cc/index.json` |

响应带 `Access-Control-Allow-Origin: *`，短缓存（约 60s）。检查频率由各客户端自己控制。

## EA Clip 自动同步

正式发版流程在 Release 及附件校验成功后，通过 `release-published` repository dispatch 主动通知 [update-api.yml](.github/workflows/update-api.yml)，随即同步版本清单并部署。没有服务端定时轮询；手动发布的正式 Release 也由发布仓库的 `release: published` 事件通知，支持手动补发失败通知。客户端启动后检查一次，此后每 5 小时检查。

只有正式 x64 便携 ZIP、构建清单、SHA256SUMS 三个附件完整上传，且 ZIP 有 GitHub SHA-256 摘要时，才自动更新 `public/eaclip/version.json` 并提交。清单包含 `sha256`、`size` 和版本说明，客户端正常检查只需一个小 JSON；安装包仍直接从 GitHub 或镜像下载。脚本拒绝倒退版本、草稿、预发布、错误产品地址和同版本包摘要变化。

清单或部署配置变化时自动部署 Workers 静态资源，随后读回正式 API 验证版本、完整正文及 JSON/CORS 响应头。重复或迟到通知读取最新正式版本，清单及服务均未变更时不提交、不部署。失败时重跑该次 Actions，或手动补发通知；不使用定时任务重试。其它产品清单保持手动维护，push `main` 后同样自动部署。

部署须在本仓库 Actions Secrets 中配置 `CLOUDFLARE_API_TOKEN`，授予对应账户的 Workers 部署权限，再将仓库 Actions Variable `UPDATE_API_ENABLED` 设为 `true` 以启用自动任务；账户 ID 已在 `wrangler.toml` 中。未配置凭据时自动任务保持关闭，手动执行仍可检查部署设置。密钥不写入源码。流程参考 [Cloudflare GitHub Actions 文档](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)。

2026-10-30 已配置独立部署凭据并启用自动任务。[首次实际运行](https://github.com/ceastld/app-updates/actions/runs/41110774093)通过清单回归、正式版本同步、Cloudflare 部署与线上 `0.32.5.0` 读回校验。

发布仓库 `ceastld/eaclip` 的 `APP_UPDATES_DISPATCH_TOKEN` Secret 只授予本仓库的 `Contents: write`，用于发送跨仓库通知；内置 `GITHUB_TOKEN` 仅限其所在仓库，不能替代该凭据。发布主工作流显式调用通知，覆盖 `GITHUB_TOKEN` 创建 Release 不触发另一条 `release` 工作流的情形。

推送链路已用现有正式版 `rust-v0.32.5` 实测：[发布仓库主动通知](https://github.com/ceastld/eaclip/actions/runs/41117864943)与[本仓库事件处理](https://github.com/ceastld/app-updates/actions/runs/41117885115)均成功。接收任务通过四项回归并读回线上 `0.32.5.0`；重复通知的清单和 API 均未变化，正确跳过部署。没有创建测试 Release。

## OmniTrigger 发布同步

OmniTrigger 复用同一 Workers 静态资源、域名和部署作业。`scripts/sync_omnitrigger.py` 从官方仓库最近 100 条公开发行中按 SemVer 选择最高版本；包含预发布版，与该产品现有 Windows 预览渠道一致。仅当 ZIP、SHA256SUMS 均上传完整，且 ZIP 有 GitHub SHA-256 摘要时才更新清单；拒绝版本倒退与同版本 ZIP 摘要变化。

清单沿用 `product`、`release`、`version`、`publishedAt`、`downloadUrl`、`sha256SumsUrl`、`sha256`、`size`、`notes` 字段。`release` 为 Cargo SemVer；纯三段数字的 `version` 追加 `.0`，带预发布后缀时保持原 SemVer。客户端正常检查只需一个小 JSON；下载仍使用原始 GitHub 发行包。

公开发行完成后，发布仓库向本仓库发送 `release-published` 通知，载荷为 `product=omnitrigger`、`repository=ceastld/omnitrigger`、`tag=v<版本>`。接收作业校验产品与标签身份，运行两种产品的同步和回归，通过同一 Cloudflare 作业部署并分别读回验证。现有 EA Clip 通知与稳定版本规则保持原样。发布仓库需要配置仅对本仓库具有 Contents: write 权限的 `APP_UPDATES_DISPATCH_TOKEN`，不能使用仅限发布仓库的内置 `GITHUB_TOKEN`。

`scripts/sync_updates.py` 统一运行两种自动同步产品；其他产品清单仍手动维护。不新增服务端轮询、不创建产品 Release。

## 本地验证与部署

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/sync_updates.py
npm ci
npm run deploy
python scripts/sync_updates.py --verify-api --attempts 40
```

本地使用已登录的 Wrangler，或通过环境变量 `CLOUDFLARE_API_TOKEN` 注入部署密钥。不会上传安装包，也不会创建或修改产品 Release。
