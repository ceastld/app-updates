# app-updates

多产品版本检查 API（静态 JSON），经 Cloudflare 发布到 `https://update.alinko.cc`。

客户端只做 GET，例如：

- `https://update.alinko.cc/eaclip/version.json`
- `https://update.alinko.cc/raishot/version.json`
- `https://update.alinko.cc/cea.cliphost.rust/version.json`

本仓库**只放小体积清单**；安装包请指向 GitHub Releases、缤纷云或自有服务器，不要把 zip 提交进来。

发版：改对应产品目录下的 `version.json`，push 到 `main` 即可。检查频率由各客户端自行控制。
