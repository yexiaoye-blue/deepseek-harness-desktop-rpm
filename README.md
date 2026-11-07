# DeepSeek Harness Desktop RPM

为 [dsh-tauri/deepseek-harness-desktop](https://github.com/dsh-tauri/deepseek-harness-desktop) 提供非官方社区 RPM 包。

## 下载与安装

从本仓库的 [Releases](https://github.com/yexiaoye-blue/deepseek-harness-desktop-rpm/releases) 下载与你的 CPU 匹配的 RPM：

- Intel / AMD 64 位：`x86_64.rpm`
- ARM64：`aarch64.rpm`

```bash
sudo dnf install ./dsh-tauri-*.rpm
```

面向 Fedora 43 及更新版本。每个包在 Ubuntu 22.04 对应架构上从源码构建，检查 GLIBC 依赖不超过 2.35，并在 Fedora 43 容器中验证安装、动态库依赖及 Electron 沙箱权限。容器检查不等于真实桌面 GUI 验收。

下载 `SHA256SUMS` 后可以校验本地下载的文件：

```bash
sha256sum -c SHA256SUMS --ignore-missing
```

这是普通联网安装包，首次启动按上游逻辑下载缺失的运行时和 Harness 内核。应用内自动更新已关闭，请从本仓库下载新 RPM 后使用 `dnf install` 升级。此仓库暂未提供 DNF 软件源。

RPM 打包修订目前为 **2**。例如上游 `v0.30.4` 对应本仓库 `v0.30.4-rpm.2`，安装包版本为 `0.30.4-2.github`，可从先前的 `1.github` 正常升级。Linux 窗口会关联 `DSH Tauri.desktop`，使用上游鲸鱼图标和显示名称。

## 自动跟随上游

- 每 10 分钟检查上游最新已发布的正式版，排除草稿、beta、rc 和 nightly。
- 将正式版标签解析成完整源码 SHA；只构建该提交及其固定的子模块。
- 构建 `x86_64` 与 `aarch64`；两个架构均验证成功后才发布 Release。
- 同一上游版本已经有完整产物时自动跳过；失败和未完成的版本下次会重试。
- 每次 Release 附带 `UPSTREAM.json`，记录源码、上游发布页、打包提交和构建记录。
- 若已发布的上游标签被改到另一个提交，停止覆盖已有 RPM。

可在 Actions → **Follow upstream stable and publish RPM** → **Run workflow** 手动检查。勾选 `force` 可重新构建源码 SHA 未变的最新正式版。

GitHub 定时调度可能延迟；公开仓库长时间无活动时，GitHub 可能停用定时工作流，需要在 Actions 页面重新启用。工作流使用仓库自带的 `GITHUB_TOKEN`，无需个人访问令牌或上游写权限。

## 维护与验证

```bash
python3 -m unittest discover -s tests -v
sh -n packaging/postinstall.sh.in
```

打包工具增加 RPM 元数据、依赖、原始许可文件、安装后的沙箱权限处理，以及 Electron 的 Linux 桌面名称和图标绑定；应用功能代码来自对应的上游正式版。打包依赖和脚本需要在上游构建布局变化时适配，失败时不会发布不完整版本。

## 上游许可与归属

本项目不是上游官方发行渠道。上游应用及随包组件保留各自许可和归属；RPM 内包含上游 `LICENSE`、`LICENSE.details` 及可用的第三方声明。上游还附有商业二次开发限制，具体以对应正式版的原始许可文件为准。
