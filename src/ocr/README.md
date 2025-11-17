# OCR 模块使用说明

基于 PaddleOCR-VL API 的图片文字识别模块。

## 配置方式

### 方式 1：配置文件（推荐用于开发）

编辑 `config/ocr_api.py`：

```python
API_URL = "https://your-api-endpoint.com/layout-parsing"
API_TOKEN = "your-api-token-here"
```

### 方式 2：环境变量（推荐用于生产）

设置环境变量：

```bash
# Windows (PowerShell)
$env:PADDLEOCR_API_URL = "https://your-api-endpoint.com/layout-parsing"
$env:PADDLEOCR_API_TOKEN = "your-api-token-here"

# Linux/macOS
export PADDLEOCR_API_URL="https://your-api-endpoint.com/layout-parsing"
export PADDLEOCR_API_TOKEN="your-api-token-here"
```

### 优先级

1. 直接传入的参数
2. `config/ocr_api.py` 配置文件
3. 环境变量

## 使用示例

### 1. 快速使用（便捷函数）

```python
from src.ocr import ocr_image

# 识别单张图片
markdown_text = ocr_image("path/to/image.jpg")
print(markdown_text)

# 保存 Markdown 中的图片
markdown_text = ocr_image(
    "path/to/image.jpg",
    save_images=True,
    output_dir="output"
)
```

### 2. 批量处理

```python
from src.ocr import ocr_images_batch

image_paths = [
    "image1.jpg",
    "image2.png",
    "image3.webp"
]

results = ocr_images_batch(image_paths)
for i, markdown in enumerate(results):
    print(f"图片 {i+1} 结果:\n{markdown}\n")
```

### 3. 使用客户端类（更多控制）

```python
from src.ocr import PaddleOCRClient

# 初始化客户端
client = PaddleOCRClient()

# 或者手动指定配置
client = PaddleOCRClient(
    api_url="https://your-api.com/layout-parsing",
    api_token="your-token",
    config={
        "useLayoutDetection": True,
        "prettifyMarkdown": True,
    }
)

# 识别图片
markdown = client.get_markdown("image.jpg")

# 获取完整结果
full_result = client.ocr("image.jpg")
print(full_result)
```

### 4. 自定义参数

```python
from src.ocr import ocr_image

markdown = ocr_image(
    "image.jpg",
    # 启用图片方向矫正
    useDocOrientationClassify=True,
    # 启用扭曲矫正
    useDocUnwarping=True,
    # 启用图表识别
    useChartRecognition=True,
    # 调整版面区域过滤强度
    layoutThreshold=0.6,
)
```

## 命令行使用

```bash
# 基本使用
python src/ocr/paddle_ocr_client.py image.jpg

# 结果会自动保存为 image.md
```

## API 参数说明

常用参数：

- `useDocOrientationClassify`: 图片方向矫正（布尔值）
- `useDocUnwarping`: 图片扭曲矫正（布尔值）
- `useLayoutDetection`: 版面分析（布尔值）
- `useChartRecognition`: 图表识别（布尔值）
- `layoutThreshold`: 版面区域过滤强度（0-1 的浮点数）
- `prettifyMarkdown`: Markdown 美化（布尔值）
- `showFormulaNumber`: 公式编号展示（布尔值）
- `visualize`: 是否返回可视化结果（布尔值）

更多参数请参考 `docs/PaddleOCR-VL_API-帮助文档.md`

## 错误处理

```python
from src.ocr import ocr_image

try:
    markdown = ocr_image("image.jpg")
    print(markdown)
except FileNotFoundError as e:
    print(f"图片文件不存在: {e}")
except ValueError as e:
    print(f"配置错误: {e}")
except RuntimeError as e:
    print(f"API 请求失败: {e}")
```

## 注意事项

1. **API 密钥安全**：
   - 不要将 `config/ocr_api.py` 中的 API Token 提交到 Git
   - 生产环境建议使用环境变量
   - 项目已配置 `.gitignore` 忽略敏感配置

2. **网络要求**：
   - 需要能访问 PaddleOCR API 服务
   - 超时时间默认 60 秒

3. **图片格式**：
   - 支持常见图片格式（JPG, PNG, WEBP 等）
   - 支持 PDF 文件（设置 `file_type=0`）

4. **性能考虑**：
   - 批量处理时会依次处理每张图片
   - 建议控制并发请求数量，避免 API 限流

