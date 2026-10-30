# app-updates

多产品**版本检查 API**（Cloudflare Workers 静态资源 → `https://update.alinko.cc`）。

客户端当普通 HTTP API 用：`GET` 对应产品的 `version.json` 即可。本仓只放小体积清单；安装包 URL 指向 GitHub Releases、缤纷云或自有服务器。

## 端点

| 产品 | URL |
|------|-----|
| EA Clip / ClipHost | `https://update.alinko.cc/eaclip/version.json` |
| RaiShot | `https://update.alinko.cc/raishot/version.json` |
| cea.cliphost | `https://update.alinko.cc/cea.cliphost/version.json` |
| cea.cliphost.rust | `https://update.alinko.cc/cea.cliphost.rust/version.json` |
| cea.cliphost.rust.arm64 | `https://update.alinko.cc/cea.cliphost.rust.arm64/version.json` |
| 目录 | `https://update.alinko.cc/index.json` |

响应带 `Access-Control-Allow-Origin: *`，短缓存（约 60s）。检查频率由各客户端自己控制。

## EA Clip 自动同步

GitHub Actions 的 [update-api.yml](.github/workflows/update-api.yml) 每 15 分钟检查 `ceastld/eaclip` 最新正式 Release，也支持手动执行和 `release-published` repository dispatch。GitHub 的定时调度可能延迟；客户端启动后检查一次，此后每 5 小时检查。

只有正式 x64 便携 ZIP、构建清单、SHA256SUMS 三个附件完整上传，且 ZIP 有 GitHub SHA-256 摘要时，才自动更新 `public/eaclip/version.json` 并提交。清单包含 `sha256`、`size` 和版本说明，客户端正常检查只需一个小 JSON；安装包仍直接从 GitHub 或镜像下载。脚本拒绝倒退版本、草稿、预发布、错误产品地址和同版本包摘要变化。

清单或部署配置变化时自动部署 Workers 静态资源，随后读回正式 API 验证版本、完整正文及 JSON/CORS 响应头。未变更的定时检查不提交、不部署；部署失败后，下次发现服务与仓库不一致会重试。其它产品清单保持手动维护，push `main` 后同样自动部署。

部署须在本仓库 Actions Secrets 中配置 `CLOUDFLARE_API_TOKEN`，授予对应账户的 Workers 部署权限，再将仓库 Actions Variable `UPDATE_API_ENABLED` 设为 `true` 以启用自动任务；账户 ID 已在 `wrangler.toml` 中。未配置凭据时自动任务保持关闭，手动执行仍可检查部署设置。密钥不写入源码。流程参考 [Cloudflare GitHub Actions 文档](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)。

## 本地验证与部署

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
python scripts/sync_eaclip.py
npm ci
npm run deploy
python scripts/sync_eaclip.py --verify-api --attempts 40
```

本地使用已登录的 Wrangler，或通过环境变量 `CLOUDFLARE_API_TOKEN` 注入部署密钥。不会上传安装包，也不会创建或修改产品 Release。
