# 小红书用户帖子爬取脚本

将指定小红书用户主页的所有帖子链接抓取下来，或从 CSV 文件读取帖子链接，打开详情页提取标题、正文文本、图片，并生成本地可浏览的 HTML 或 Markdown 文件，同时创建索引页面。

## 功能特性

### 爬虫功能
- ✅ 支持从用户主页或 CSV 文件获取帖子链接
- ✅ 输出 HTML 或 Markdown 两种格式
- ✅ 智能去重和跳过已下载内容（基于 note_id）
- ✅ 关键词筛选功能，优先下载指定内容
- ✅ 自动缓存帖子标题，避免重复请求
- ✅ 增量下载，合并新旧索引
- ✅ 自动下载轮播图片到本地

### OCR 功能（新增）
- ✅ 基于 PaddleOCR-VL API 的图片文字识别
- ✅ 支持图片和 PDF 文件识别
- ✅ 返回 Markdown 格式文本
- ✅ 安全的 API 密钥管理（支持配置文件和环境变量）
- ✅ 批量处理多个图片
- ✅ 详细使用文档和示例代码

## 环境要求
- Python `>=3.11`
- Windows/macOS/Linux 均可

## 安装

### 方式 1：使用 uv（推荐）
```bash
# 安装 uv（如果尚未安装）
pip install uv

# 安装项目依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install
```

### 方式 2：使用 pip
```bash
# 安装项目依赖
pip install .

# 安装 Playwright 浏览器
python -m playwright install
```

2. 可选：准备登录 `cookies`（若目标用户的帖子需要登录才可见）
   - 使用浏览器插件（如 Cookie-Editor）从 `www.xiaohongshu.com` 域导出 cookies 为 JSON 文件。
   - 或在开发者工具中手动导出并保存为 JSON，字段至少包含 `name`、`value`、`domain`、`path`。

## 使用示例

### 基础用法
```bash
# 从用户主页抓取（使用 uv）
uv run python main.py --user <用户ID或URL> --out output --cookies cookies.json

# 从 CSV 文件读取链接
uv run python main.py --csv items.csv --out output --cookies cookies.json

# 若需手动登录（推荐首次使用）
uv run python main.py --user <用户ID> --no-headless --out output
```

### 增量下载与去重
```bash
# 跳过已存在的帖子，支持断点续传
uv run python main.py --csv items.csv --out output --skip-existing --format markdown

# 自动去重：脚本会自动识别重复的 note_id，避免重复下载
```

### 关键词筛选
```bash
# 优先下载包含"句子"的帖子，然后下载其他帖子
uv run python main.py --csv items.csv --out output --note-keyword "句子" --format markdown --skip-existing

# 仅下载包含"外刊"的帖子
uv run python main.py --csv items.csv --out output --note-keyword "外刊" --keyword-only --format markdown

# 关键词匹配不区分大小写，支持中英文
```

### 输出格式
```bash
# 生成 HTML 格式（默认）
uv run python main.py --csv items.csv --out output --format html

# 生成 Markdown 格式
uv run python main.py --csv items.csv --out output --format markdown
```

### 完整示例
```bash
# 综合使用：从 CSV 读取，筛选包含"雅思"的帖子优先下载，输出 Markdown，跳过已存在
uv run python main.py --csv items.csv --out output --cookies cookies.json --note-keyword "雅思" --format markdown --skip-existing --limit 100
```

## 参数说明

### 必选参数（二选一）
- `--user`：用户主页 URL 或用户 ID
- `--csv`：CSV 文件路径（第一列或 `note_link` 列为帖子链接）

### 可选参数
- `--out`：输出目录，默认 `output`
- `--cookies`：登录态 cookies 的 JSON 文件路径
- `--limit`：最多处理的帖子数量，默认不限制
- `--format`：输出格式，可选 `html` 或 `markdown`，默认 `html`
- `--skip-existing`：跳过已存在的文件，支持增量下载和索引合并
- `--note-keyword`：筛选标题中包含指定关键词的帖子
- `--keyword-only`：仅下载关键词匹配的帖子（需配合 `--note-keyword`）
- `--no-headless`：使用有头模式，方便观察或手动登录
- `--timeout`：页面加载超时时间（毫秒），默认 `30000`
- `--user-agent`：自定义 User-Agent 字符串

## 输出结构
```
output/
├── .tmp/
│   └── notes_cache.json          # 帖子标题缓存（自动生成）
├── images/
│   ├── <note_id>_1.webp          # 下载的图片文件
│   ├── <note_id>_2.webp
│   └── ...
├── index.html                     # HTML 格式索引页面
├── index.md                       # Markdown 格式索引（仅当使用 --format markdown 时）
├── <note_id>_<标题>.html         # HTML 格式的帖子文件
└── <note_id>_<标题>.md           # Markdown 格式的帖子文件
```

### 文件说明
- **索引文件**：列出所有已下载的帖子，包含标题和原帖链接
- **帖子文件**：以 `note_id_标题` 命名，包含完整内容和本地图片
- **图片文件**：自动下载的轮播图片，使用相对路径引用
- **缓存文件**：记录已获取的帖子标题，避免重复请求（可安全删除）

## 工作原理

### 智能去重机制
1. **基于 note_id 去重**：从 URL 中提取唯一的 note_id，自动过滤重复链接
2. **检查已下载内容**：启用 `--skip-existing` 时，扫描输出目录识别已下载的帖子
3. **提前过滤**：在打开页面前完成去重和过滤，节省 30-50% 处理时间

### 关键词筛选流程
1. **获取标题**：快速访问每个帖子页面获取标题（优先使用缓存）
2. **缓存机制**：标题存储在 `.tmp/notes_cache.json`，避免重复请求
3. **智能排序**：
   - 不使用 `--keyword-only`：关键词匹配的帖子优先处理，然后处理其他帖子
   - 使用 `--keyword-only`：仅处理关键词匹配的帖子

### 增量下载与索引合并
- 使用 `--skip-existing` 时，新下载的内容会自动合并到现有索引中
- 按 URL 去重，保留最新的条目
- 支持中断后继续，不会重复下载已有内容

## 性能优化建议
- 使用 `--skip-existing` 进行增量下载，避免重复处理
- 使用 `--note-keyword` 优先下载关键内容
- 首次运行会建立缓存，后续运行速度更快
- 对于大量链接（如 500+），建议分批处理或使用 `--limit` 限制

## 注意与合规
- 请遵守小红书平台的服务条款与相关法律法规，仅用于学习/归档等合规用途
- 站点存在反爬机制，若出现空白页或 403：
  - 尝试提供有效登录 `cookies`
  - 使用 `--no-headless` 并在浏览器中完成登录
  - 适当增大 `--timeout` 或减少处理速度
- 建议合理控制请求频率，避免对服务器造成压力

## 常见问题

### 安装相关
- **浏览器未安装**：运行 `uv run playwright install` 或 `python -m playwright install`
- **依赖安装失败**：使用 `uv sync` 重新安装依赖

### 使用相关
- **图片显示问题**：脚本会自动下载轮播图片到 `images/` 目录，使用相对路径引用
- **文本内容不完整**：页面为动态渲染，脚本已优化选择器并尝试展开折叠内容
- **重复下载问题**：使用 `--skip-existing` 参数启用智能跳过机制
- **关键词不生效**：确保标题中包含该关键词，匹配不区分大小写

### 性能相关
- **速度较慢**：首次运行需要获取所有标题，后续运行会使用缓存
- **内存占用高**：处理大量链接时可使用 `--limit` 分批处理
- **缓存文件较大**：`.tmp/notes_cache.json` 可安全删除，会自动重建

## OCR 功能使用

项目新增了基于 PaddleOCR-VL API 的图片文字识别功能，可以将下载的图片转换为 Markdown 文本。

### 快速开始

1. **配置 API**（两种方式任选其一）

   方式 1：编辑配置文件（开发环境）
   ```bash
   # 复制模板文件
   cp config/ocr_api.py.template config/ocr_api.py
   
   # 编辑 config/ocr_api.py，填写 API_URL 和 API_TOKEN
   ```

   方式 2：设置环境变量（生产环境）
   ```bash
   # PowerShell
   $env:PADDLEOCR_API_URL = "https://your-api.com/layout-parsing"
   $env:PADDLEOCR_API_TOKEN = "your-token"
   ```

2. **使用示例**

   ```python
   from src.ocr import ocr_image
   
   # 识别单张图片
   markdown = ocr_image("output/images/post_1.webp")
   print(markdown)
   
   # 批量处理
   from src.ocr import ocr_images_batch
   results = ocr_images_batch(["image1.jpg", "image2.jpg"])
   ```

3. **命令行使用**

   ```bash
   # 快速测试
   python test_ocr.py output/images/your_image.webp
   
   # 完整示例
   python src/ocr/paddle_ocr_client.py image.jpg
   ```

更多详细说明请查看：
- [OCR 模块文档](src/ocr/README.md)
- [使用示例](examples/ocr_example.py)
- [API 文档](docs/PaddleOCR-VL_API-帮助文档.md)

## 更新日志

### v2.1 (2025-11)
- ✨ **新增 OCR 功能模块**（基于 PaddleOCR-VL API）
  - 支持图片和 PDF 文件识别
  - 返回 Markdown 格式文本
  - 批量处理功能
- 🔒 **API 密钥安全管理**
  - 支持配置文件方式（开发环境）
  - 支持环境变量方式（生产环境）
  - 配置文件模板 `.gitignore` 自动保护
- 📝 **完整文档**
  - OCR 模块详细文档
  - 6 个完整使用示例
  - API 调用帮助文档
- 🛡️ 更新 `.gitignore` 保护敏感配置

### v2.0 (2025-11)
- 新增 CSV 文件读取支持
- 新增 Markdown 输出格式
- 新增智能去重和跳过机制（基于 note_id）
- 新增关键词筛选功能
- 新增标题缓存机制
- 新增增量下载和索引合并
- 自动下载轮播图片到本地
- 优化性能，减少 30-50% 重复请求

### v1.0
- 基础爬取功能
- HTML 输出格式
- 用户主页链接采集