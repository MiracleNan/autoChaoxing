<p align="center">
  <a href="https://www.springing.top" target="blank">
    <img src="images/logo.png" alt="Logo" width="156" height="156">
  </a>
  <h2 align="center" style="font-weight: 600">autoChaoxing / SuperStar Local</h2>
  <p align="center">
    超星学习通本地自动化工具，支持 WebUI 和命令行两种使用方式
  </p>
</p>

这是一个本地运行版本，不再通过 GitHub Actions 执行。账号、密码、cookies、配置和日志都只保存在本机，避免 fork 公开仓库后泄露明文凭据。

> 请只在自己的账号和课程范围内使用，遵守学校、课程平台和相关服务条款。

![项目截图](images/star-banner.png)

## 当前能力

- 本地 Flask WebUI：登录、退出、课程列表、章节读取、课程 URL 参数解析。
- WebUI 任务控制：选择课程后启动/停止任务，并通过 SSE 实时展示进度。
- Web 配置页：编辑 `[common]`、`[tiku]`、`[notification]` 配置，支持题库和通知相关字段。
- 命令行模式：继续支持 `python main.py -c config.ini` 的原始运行方式。
- 题库支持：言溪、LIKE、TikuAdapter、AI/OpenAI 兼容接口、SiliconFlow、TikuGo 等。
- 通知支持：Server 酱、Qmsg、Bark、Telegram。

## 用前必读

不要把 `config.ini`、`cookies.txt`、`cache.json`、`chaoxing.log`、`.webui.env`、`superstar_web.log` 等本地文件提交到仓库。当前 `.gitignore` 已经忽略这些文件，但提交前仍建议先运行：

```bash
git status --short
```

如果你之前已经把账号、密码、cookies 或题库 token 提交到 GitHub Actions 或公开仓库，建议立即修改密码并撤销相关 token。

## 快速开始

项目依赖 Python 3.13：

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config_template.ini config.ini
```

然后编辑本地的 `config.ini`，按需填写账号、密码、课程 ID、题库和通知配置。

### 本地 WebUI

推荐使用脚本启动，脚本会自动创建虚拟环境并安装依赖：

```bash
./scripts/run_web.sh
```

浏览器打开 `http://127.0.0.1:5050`。登录成功后会自动保存本机 `cookies.txt`，页面会列出当前账号可访问的课程，可以查看课程章节，也可以粘贴课程页面 URL 提取 `courseId`、`clazzId` 和 `cpi`。

可以通过环境变量调整监听地址和端口：

```bash
SUPERSTAR_HOST=0.0.0.0 SUPERSTAR_PORT=5050 ./scripts/run_web.sh
```

WebUI 默认读取当前目录的 `config.ini`。如果要使用其他配置文件：

```bash
SUPERSTAR_CONFIG=/path/to/config.ini ./scripts/run_web.sh
```

### 命令行

运行：

```bash
python main.py -c config.ini
```

也可以使用 cookies 登录：先准备本地 `cookies.txt`，再在 `config.ini` 中设置：

```ini
use_cookies=true
```

常用命令行参数：

```bash
python main.py -u 手机号 -p 密码 -l 课程ID1,课程ID2 -s 1.0 -j 4
```

其中 `-s` 是视频倍速，最大为 2；`-j` 是并行章节数。

### Docker

Docker 镜像默认运行命令行模式，并从 `/config/config.ini` 读取配置：

```bash
docker build -t autochaoxing .
docker run --rm -v "$PWD/config.ini:/config/config.ini" autochaoxing
```

## 本地安全说明

- 仓库已移除 GitHub Actions workflow，不会在 push 后自动执行。
- 敏感配置只放在本机 `config.ini` 或 `cookies.txt`。
- 不建议通过命令行参数直接传密码，因为 shell 历史记录可能保存命令。
- 如果需要备份代码，先确认没有本地配置文件被加入 git 暂存区。
- WebUI 仅建议监听 `127.0.0.1`；如果改成 `0.0.0.0`，请自行做好访问控制。

## 项目结构

```text
app.py                  本地 Flask WebUI 入口
main.py                 命令行入口
api/                    超星接口、题库、通知、配置和任务管理逻辑
templates/              WebUI 页面和 htmx 局部模板
scripts/run_web.sh      本地 WebUI 启动脚本
tests/                  WebUI、配置 API 和课程 URL 解析测试
config_template.ini     本地配置模板
```

## 测试

```bash
python -m unittest discover -s tests
```

<a href="https://github.com/Samueli924/chaoxing" target="blank">灵感来源</a>

## Star History
<a href="https://www.star-history.com/?repos=MiracleNan%2FautoChaoxing&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=MiracleNan/autoChaoxing&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=MiracleNan/autoChaoxing&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=MiracleNan/autoChaoxing&type=date&legend=top-left" />
 </picture>
</a>

## 赞助
>如果觉着代码对你有帮助，可以赞赏一下开发者

![微信支付收款码](/images/reward.png)
