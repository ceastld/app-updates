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

## 发版

改 `public/<产品>/version.json`，push `main` 后在本机用 Workers token 执行：

```bash
export CLOUDFLARE_API_TOKEN=$(tr -d '[:space:]' < /workspace/.cf_workers_token)
npx wrangler deploy
```

（也可之后接 GitHub → Workers Builds 自动发布。）
