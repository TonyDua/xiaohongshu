# 项目结构说明

```
xiaohongshu/
├── main.py                          # 主爬虫脚本
├── test_ocr.py                      # OCR 功能快速测试脚本
├── pyproject.toml                   # 项目配置文件
├── uv.lock                          # 依赖锁定文件
├── README.md                        # 主说明文档
├── .gitignore                       # Git 忽略配置
│
├── config/                          # 配置文件目录
│   ├── ocr_api.py                   # OCR API 配置（不提交到 Git）
│   └── ocr_api.py.template          # OCR API 配置模板
│
├── src/                             # 源代码目录
│   ├── __init__.py
│   └── ocr/                         # OCR 功能模块
│       ├── __init__.py
│       ├── paddle_ocr_client.py     # PaddleOCR 客户端封装
│       └── README.md                # OCR 模块文档
│
├── examples/                        # 示例代码
│   └── ocr_example.py               # OCR 使用示例（6 个完整示例）
│
├── docs/                            # 文档目录
│   ├── PaddleOCR-VL_API-帮助文档.md # PaddleOCR API 文档
│   └── PROJECT_STRUCTURE.md         # 项目结构说明（本文件）
│
├── output/                          # 爬虫输出目录（自动生成）
│   ├── .tmp/                        # 临时文件和缓存
│   │   └── notes_cache.json         # 帖子标题缓存
│   ├── images/                      # 下载的图片
│   │   └── *.webp                   # 图片文件
│   ├── index.html                   # HTML 格式索引
│   ├── index.md                     # Markdown 格式索引
│   └── *.html / *.md                # 各个帖子文件
│
├── items.csv                        # CSV 文件（可选，用户提供）
└── *.json                           # Cookies 文件（不提交到 Git）
```

## 目录说明

### 核心文件

- **main.py**: 主爬虫脚本，包含所有爬取逻辑
  - 支持从用户主页或 CSV 文件获取帖子链接
  - 智能去重、关键词筛选、增量下载等功能

- **test_ocr.py**: OCR 功能快速测试脚本
  - 用于快速测试图片识别功能
  - 命令行友好的错误提示

### 配置目录（config/）

- **ocr_api.py**: OCR API 配置文件
  - 包含 API_URL 和 API_TOKEN
  - ⚠️ 不会提交到 Git（在 .gitignore 中）
  - 从 `ocr_api.py.template` 复制并填写

- **ocr_api.py.template**: 配置文件模板
  - 提供配置文件结构参考
  - 可以安全提交到 Git

### 源代码目录（src/）

- **src/ocr/**: OCR 功能模块
  - `paddle_ocr_client.py`: PaddleOCR API 客户端封装
    - `PaddleOCRClient`: 主客户端类
    - `ocr_image()`: 便捷函数，识别单张图片
    - `ocr_images_batch()`: 批量处理函数
  - `README.md`: OCR 模块详细文档

### 示例代码（examples/）

- **ocr_example.py**: 完整的 OCR 使用示例
  1. 简单使用
  2. 保存 Markdown 图片
  3. 批量处理
  4. 高级配置
  5. 处理 PDF
  6. 错误处理

### 文档目录（docs/）

- **PaddleOCR-VL_API-帮助文档.md**: PaddleOCR API 官方文档
  - API 调用示例
  - 请求参数说明
  - 响应格式说明

- **PROJECT_STRUCTURE.md**: 项目结构说明（本文件）

### 输出目录（output/）

自动生成的目录，包含爬取和处理的结果：

- `.tmp/`: 临时文件和缓存
  - `notes_cache.json`: 帖子标题缓存，避免重复请求

- `images/`: 下载的图片文件
  - 命名格式：`{note_id}_{序号}.{扩展名}`

- 索引文件：
  - `index.html`: HTML 格式索引
  - `index.md`: Markdown 格式索引

- 帖子文件：
  - 命名格式：`{note_id}_{标题}.{html|md}`

## 功能模块关系

```
main.py (爬虫脚本)
    ↓
  下载图片到 output/images/
    ↓
src/ocr/ (OCR 模块)
    ↓
  识别图片 → 返回 Markdown 文本
```

## 工作流程

### 1. 爬虫工作流程

```
用户输入 (URL/CSV)
    ↓
获取帖子链接
    ↓
去重 + 过滤已存在
    ↓
关键词筛选（可选）
    ↓
逐个处理帖子
    ↓
下载图片到 output/images/
    ↓
生成 HTML/Markdown 文件
    ↓
更新索引文件
```

### 2. OCR 工作流程

```
用户调用 ocr_image(path)
    ↓
加载 API 配置
  (config/ocr_api.py 或环境变量)
    ↓
图片 → Base64 编码
    ↓
调用 PaddleOCR API
    ↓
解析响应
    ↓
返回 Markdown 文本
```

## 环境变量

可以通过环境变量配置 OCR API（优先级低于配置文件）：

```bash
# Windows (PowerShell)
$env:PADDLEOCR_API_URL = "https://your-api.com/layout-parsing"
$env:PADDLEOCR_API_TOKEN = "your-token"

# Linux/macOS
export PADDLEOCR_API_URL="https://your-api.com/layout-parsing"
export PADDLEOCR_API_TOKEN="your-token"
```

## Git 忽略规则

`.gitignore` 会忽略以下敏感文件：

- `config/ocr_api.py` - OCR API 配置
- `*.json` - Cookies 文件
- `output/` - 输出目录
- `.tmp/` - 临时文件

但保留：
- `pyproject.toml` - 项目配置
- `uv.lock` - 依赖锁定文件
- `config/ocr_api.py.template` - 配置模板

## 依赖管理

项目使用 `uv` 管理依赖：

```bash
# 安装依赖
uv sync

# 添加新依赖
uv add package-name

# 安装 Playwright 浏览器
uv run playwright install
```

## 开发建议

1. **配置管理**
   - 开发环境：使用 `config/ocr_api.py`
   - 生产环境：使用环境变量
   - 永远不要提交包含真实 API 密钥的文件

2. **代码组织**
   - 爬虫逻辑：`main.py`
   - OCR 功能：`src/ocr/`
   - 新增功能建议放在 `src/` 下

3. **测试**
   - 爬虫测试：`python main.py --user <用户ID> --limit 5`
   - OCR 测试：`python test_ocr.py <图片路径>`
   - 完整示例：`python examples/ocr_example.py`

4. **文档**
   - 新功能请更新 `README.md`
   - 模块文档放在对应目录下
   - API 文档放在 `docs/` 目录

