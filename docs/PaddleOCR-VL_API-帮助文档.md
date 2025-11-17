## [](#paddleocr-vl-%E6%9C%8D%E5%8A%A1%E5%8C%96%E9%83%A8%E7%BD%B2%E8%B0%83%E7%94%A8%E7%A4%BA%E4%BE%8B%E5%8F%8A-api-%E4%BB%8B%E7%BB%8D%EF%BC%9A)PaddleOCR-VL 服务化部署调用示例及 API 介绍：

## [](#1-%E6%9C%8D%E5%8A%A1%E8%B0%83%E7%94%A8%E7%A4%BA%E4%BE%8B%EF%BC%88python%EF%BC%89)1\. 服务调用示例（python）

```python
# Please make sure the requests library is installed
# pip install requests
import base64
import os
import requests

API_URL = "<your url>"
TOKEN = "<access token>"

file_path = "<local file path>"

with open(file_path, "rb") as file:
    file_bytes = file.read()
    file_data = base64.b64encode(file_bytes).decode("ascii")

headers = {
    "Authorization": f"token {TOKEN}",
    "Content-Type": "application/json"
}

# For PDF documents, set `fileType` to 0; for images, set `fileType` to 1
payload = {
    "file": file_data,
    "fileType": <file type>,
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useChartRecognition": False,
}

response = requests.post(API_URL, json=payload, headers=headers)
print(response.status_code)
assert response.status_code == 200
result = response.json()["result"]

output_dir = "output"
os.makedirs(output_dir, exist_ok=True)

for i, res in enumerate(result["layoutParsingResults"]):
    md_filename = os.path.join(output_dir, f"doc_{i}.md")
    with open(md_filename, "w") as md_file:
        md_file.write(res["markdown"]["text"])
    print(f"Markdown document saved at {md_filename}")
    for img_path, img in res["markdown"]["images"].items():
        full_img_path = os.path.join(output_dir, img_path)
        os.makedirs(os.path.dirname(full_img_path), exist_ok=True)
        img_bytes = requests.get(img).content
        with open(full_img_path, "wb") as img_file:
            img_file.write(img_bytes)
        print(f"Image saved to: {full_img_path}")
    for img_name, img in res["outputImages"].items():
        img_response = requests.get(img)
        if img_response.status_code == 200:
            # Save image to local
            filename = os.path.join(output_dir, f"{img_name}_{i}.jpg")
            with open(filename, "wb") as f:
                f.write(img_response.content)
            print(f"Image saved to: {filename}")
        else:
            print(f"Failed to download image, status code: {img_response.status_code}")
```

对于服务提供的主要操作：

- HTTP请求方法为POST。
- 请求体和响应体均为JSON数据（JSON对象）。
- 当请求处理成功时，响应状态码为`200`，响应体的属性如下：

| 名称        | 类型      | 含义                          |
| ----------- | --------- | ----------------------------- |
| `logId`     | `string`  | 请求的UUID。                  |
| `errorCode` | `integer` | 错误码。固定为`0`。           |
| `errorMsg`  | `string`  | 错误说明。固定为`"Success"`。 |
| `result`    | `object`  | 操作结果。                    |

- 当请求处理未成功时，响应体的属性如下：

| 名称        | 类型      | 含义                       |
| ----------- | --------- | -------------------------- |
| `logId`     | `string`  | 请求的UUID。               |
| `errorCode` | `integer` | 错误码。与响应状态码相同。 |
| `errorMsg`  | `string`  | 错误说明。                 |

服务提供的主要操作如下：

- **`infer`**

进行版面解析。

`POST /layout-parsing`

## [](#2-%E8%AF%B7%E6%B1%82%E5%8F%82%E6%95%B0%E8%AF%B4%E6%98%8E)2\. 请求参数说明

| 名称       | 参数   | 类型     | 含义                                                                                                                            | 是否必填 |
| ---------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------------------------- | -------- |
| `输入文件` | `file` | `string` | 服务器可访问的图像文件或PDF文件的URL，或上述类型文件内容的Base64编码结果。默认对于超过10页的PDF文件，只有前10页的内容会被处理。 |

要解除页数限制，请在产线配置文件中添加以下配置：

```
Serving:
  extra:
    max_num_input_imgs: null
```

| 是 |
| `文件类型` | `fileType` | `integer`｜`null` | 文件类型。`0`表示PDF文件，`1`表示图像文件。若请求体无此属性，则将根据URL推断文件类型。 | 否 |
| `图片方向矫正` | `useDocOrientationClassify` | `boolean` | `null` | 是否在推理时使用文本图像方向矫正模块，开启后，可以自动识别并矫正 0°、90°、180°、270°的图片。 | 否 |
| `图片扭曲矫正` | `useDocUnwarping` | `boolean` | `null` | 是否在推理时使用文本图像矫正模块，开启后，可以自动矫正扭曲图片，例如褶皱、倾斜等情况。 | 否 |
| `版面分析` | `useLayoutDetection` | `boolean` | `null` | 是否在推理时使用版面区域检测排序模块，开启后，可以自动检测文档中不同区域并排序。 | 否 |
| `图表识别` | `useChartRecognition` | `boolean` | `null` | 是否在推理时使用图表解析模块，开启后，可以自动解析文档中的图表（如柱状图、饼图等）并转换为表格形式，方便查看和编辑数据。 | 否 |
| `版面区域过滤强度` | `layoutThreshold` | `number` | `object` | `null` | 版面模型得分阈值。`0-1` 之间的任意浮点数。如果不设置，将使用产线初始化的该参数值，默认初始化为 `0.5`。 | 否 |
| `NMS后处理` | `layoutNms` | `boolean` | `null` | 版面检测是否使用后处理NMS，开启后，会自动移除重复或高度重叠的区域框。 | 否 |
| `扩张系数` | `layoutUnclipRatio` | `number` | `array` | `object` | `null` | 版面区域检测模型检测框的扩张系数。 任意大于 `0` 浮点数。如果不设置，将使用产线初始化的该参数值，默认初始化为 `1.0`。 | 否 |
| `版面区域检测的重叠框过滤方式` | `layoutMergeBboxesMode` | `string` | `object` | `null` |

- **large**，设置为large时，表示在模型输出的检测框中，对于互相重叠包含的检测框，只保留外部最大的框，删除重叠的内部框；
- **small**，设置为small，表示在模型输出的检测框中，对于互相重叠包含的检测框，只保留内部被包含的小框，删除重叠的外部框；
- **union**，不进行框的过滤处理，内外框都保留；

如果不设置，将使用产线初始化的该参数值，默认初始化为`large`。 | 否 |
| `prompt类型设置` | `promptLabel` | `string` | `null` | VL模型的 prompt 类型设置，当且仅当 `useLayoutDetection=False` 时生效。 | 否 |
| `控制重复惩罚` | `repetitionPenalty` | `number` | `null` | 控制模型生成重复内容的惩罚系数。值大于 `1.0` 会降低重复单词或短语出现的概率，值越高，惩罚越强，表格预测出现幻觉时可适当调高。 | 否 |
| `控制随机性` | `temperature` | `number` | `null` | 控制随机性，高值（如 `0.8`）更发散，低值（如 `0.2`）更确定，出现幻觉时可适当调高。 | 否 |
| `核采样阈值` | `topP` | `number` | `null` | 核采样阈值，仅在累计概率达阈值的词集中采样（如 `0.9` 代表只考虑最可能的 `90%`）。 | 否 |
| `动态分辨率下限` | `minPixels` | `number` | `null` | 动态分辨率下限，预处理时若调整后总像素低于此值会放大到不低于该阈值。 | 否 |
| `动态分辨率上限` | `maxPixels` | `number` | `null` | 动态分辨率上限，预处理时若调整后总像素超过此值会缩小到不超过该阈值。 | 否 |
| `公式编号展示` | `showFormulaNumber` | `boolean` | 输出的 Markdown 文本中是否包含公式编号。 | 否 |
| `Markdown 美化` | `prettifyMarkdown` | `boolean` | 是否输出美化后的 Markdown 文本。 | 否 |
| `可视化` | `visualize` | `boolean` | `null` | 是否返回可视化结果图以及处理过程中的中间图像等。

- 传入 `true`：返回图像。
- 传入 `false`：不返回图像。
- 若请求体中未提供该参数或传入 `null`：遵循产线配置文件`Serving.visualize` 的设置。

例如，在产线配置文件中添加如下字段：

```
Serving:
  visualize: False
```

将默认不返回图像，通过请求体中的`visualize`参数可以覆盖默认行为。如果请求体和配置文件中均未设置（或请求体传入`null`、配置文件中未设置），则默认返回图像。 | 否 |

- 请求处理成功时，响应体的`result`具有如下属性：

| 名称                   | 类型     | 含义                                                                                                                                                 |
| ---------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `layoutParsingResults` | `array`  | 版面解析结果。数组长度为1（对于图像输入）或实际处理的文档页数（对于PDF输入）。对于PDF输入，数组中的每个元素依次表示PDF文件中实际处理的每一页的结果。 |
| `dataInfo`             | `object` | 输入数据信息。                                                                                                                                       |

`layoutParsingResults`中的每个元素为一个`object`，具有如下属性：

| 名称           | 类型     | 含义                                                                                                             |
| -------------- | -------- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `prunedResult` | `object` | 对象的 `predict` 方法生成结果的 JSON 表示中 `res` 字段的简化版本，其中去除了 `input_path` 和 `page_index` 字段。 |
| `markdown`     | `object` | Markdown结果。                                                                                                   |
| `outputImages` | `object` | `null`                                                                                                           | 参见预测结果的 `img` 属性说明。图像为JPEG格式，使用Base64编码。 |
| `inputImage`   | `string` | `null`                                                                                                           | 输入图像。图像为JPEG格式，使用Base64编码。                      |

`markdown`为一个`object`，具有如下属性：

| 名称      | 类型      | 含义                                           |
| --------- | --------- | ---------------------------------------------- |
| `text`    | `string`  | Markdown文本。                                 |
| `images`  | `object`  | Markdown图片相对路径和Base64编码图像的键值对。 |
| `isStart` | `boolean` | 当前页面第一个元素是否为段开始。               |
| `isEnd`   | `boolean` | 当前页面最后一个元素是否为段结束。             |

**注**：如果在使用过程中遇到问题，欢迎随时在 [issue](https://github.com/PaddlePaddle/PaddleOCR/issues) 区提交反馈。
