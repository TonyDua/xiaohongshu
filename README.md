# 小红书用户帖子爬取脚本

将指定小红书用户主页的所有帖子链接抓取下来，打开详情页提取标题、正文文本、图片/视频地址，并生成本地可浏览的 HTML 文件，同时创建 `index.html` 索引页面。

## 环境要求
- Python `>=3.11`
- Windows/macOS/Linux 均可（当前目录为 Windows）

## 安装
1. 安装依赖：
   - 使用 `pip` 安装项目依赖：
     ```bash
     pip install .
     ```
   - 安装 Playwright 浏览器：
     ```bash
     python -m playwright install
     ```

2. 可选：准备登录 `cookies`（若目标用户的帖子需要登录才可见）
   - 使用浏览器插件（如 Cookie-Editor）从 `www.xiaohongshu.com` 域导出 cookies 为 JSON 文件。
   - 或在开发者工具中手动导出并保存为 JSON，字段至少包含 `name`、`value`、`domain`、`path`。

## 使用示例
```bash
# 通过用户ID
python main.py --user 5d5cfae6cbe3d90001xxxxxx --out output --cookies cookies.json --limit 100

# 通过用户主页URL
python main.py --user https://www.xiaohongshu.com/user/profile/5d5cfae6cbe3d90001xxxxxx --out output

# 若需手动登录以加载帖子（推荐首次使用）
python main.py --user https://www.xiaohongshu.com/user/profile/<用户ID> --no-headless --out output
```

主要参数说明：
- `--user`：用户主页 URL 或用户 ID。
- `--out`：输出目录（默认 `output`）。
- `--cookies`：可选，登录态 cookies 的 JSON 文件路径。
- `--limit`：最多抓取的帖子数，默认抓取所有可见帖子。
- `--no-headless`：使用有头模式（方便观察或手动登录）。
- `--timeout`：页面加载超时毫秒数（默认 `30000`）。

## 输出结构
- `output/index.html`：索引页面，列出所有生成的帖子 HTML。
- `output/*.html`：每个帖子一个独立的 HTML 文件，包含标题、正文和图片/视频链接。

## 注意与合规
- 请遵守小红书平台的服务条款与相关法律法规，仅用于学习/归档等合规用途。
- 站点存在反爬机制，若出现空白页或 403：
  - 尝试提供有效登录 `cookies`；
  - 使用 `--no-headless` 并在浏览器中完成登录；
  - 适当增大 `--timeout` 或减少 `--limit`。

## 常见问题
- 浏览器未安装：运行 `python -m playwright install` 安装。
- 图片/视频未显示：为远程地址，需联网访问；如需离线，请自行下载并改写资源路径。
- 文本内容不完整：页面为动态渲染，脚本已做通用选择器抓取，具体帖子结构可能不同，可根据需要微调选择器。