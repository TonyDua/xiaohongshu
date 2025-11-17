"""
PaddleOCR-VL API 客户端
支持图片 OCR 识别，返回 Markdown 格式文本
"""

import base64
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Union

import requests

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from config import ocr_api
except ImportError:
    ocr_api = None
    print("[warn] 无法导入 config.ocr_api，将仅使用环境变量")


class PaddleOCRClient:
    """PaddleOCR-VL API 客户端"""
    
    def __init__(
        self, 
        api_url: Optional[str] = None, 
        api_token: Optional[str] = None,
        config: Optional[Dict] = None
    ):
        """
        初始化 OCR 客户端
        
        Args:
            api_url: API 地址，如不提供则从配置文件或环境变量读取
            api_token: API Token，如不提供则从配置文件或环境变量读取
            config: API 调用配置参数
        """
        self.api_url = self._get_api_url(api_url)
        self.api_token = self._get_api_token(api_token)
        self.config = self._get_config(config)
        
        if not self.api_url or not self.api_token:
            raise ValueError(
                "API URL 和 Token 未配置！\n"
                "请在 config/ocr_api.py 中设置，或设置环境变量：\n"
                "  PADDLEOCR_API_URL\n"
                "  PADDLEOCR_API_TOKEN"
            )
        
        print(f"[info] PaddleOCR 客户端已初始化")
        print(f"[info] API URL: {self.api_url}")
        print(f"[info] Token: {self.api_token[:10]}..." if len(self.api_token) > 10 else f"[info] Token: ***")
    
    def _get_api_url(self, api_url: Optional[str]) -> str:
        """获取 API URL"""
        if api_url:
            return api_url
        
        # 从配置文件读取
        if ocr_api and hasattr(ocr_api, 'API_URL') and ocr_api.API_URL:
            return ocr_api.API_URL
        
        # 从环境变量读取
        env_url = os.environ.get('PADDLEOCR_API_URL', '')
        if env_url:
            return env_url
        
        return ''
    
    def _get_api_token(self, api_token: Optional[str]) -> str:
        """获取 API Token"""
        if api_token:
            return api_token
        
        # 从配置文件读取
        if ocr_api and hasattr(ocr_api, 'API_TOKEN') and ocr_api.API_TOKEN:
            return ocr_api.API_TOKEN
        
        # 从环境变量读取
        env_token = os.environ.get('PADDLEOCR_API_TOKEN', '')
        if env_token:
            return env_token
        
        return ''
    
    def _get_config(self, config: Optional[Dict]) -> Dict:
        """获取 API 配置"""
        if config:
            return config
        
        # 从配置文件读取默认配置
        if ocr_api and hasattr(ocr_api, 'DEFAULT_CONFIG'):
            return ocr_api.DEFAULT_CONFIG.copy()
        
        # 默认配置
        return {
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useLayoutDetection": True,
            "useChartRecognition": False,
            "layoutThreshold": 0.5,
            "prettifyMarkdown": True,
            "showFormulaNumber": False,
            "visualize": False,
        }
    
    def _encode_image(self, image_path: Union[str, Path]) -> str:
        """
        将图片编码为 Base64
        
        Args:
            image_path: 图片路径
            
        Returns:
            Base64 编码的图片数据
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        with open(image_path, "rb") as file:
            file_bytes = file.read()
            return base64.b64encode(file_bytes).decode("ascii")
    
    def ocr(
        self, 
        image_path: Union[str, Path],
        file_type: int = 1,
        **kwargs
    ) -> Dict:
        """
        对图片进行 OCR 识别
        
        Args:
            image_path: 图片路径
            file_type: 文件类型，0=PDF，1=图片（默认）
            **kwargs: 其他 API 参数，会覆盖默认配置
            
        Returns:
            API 返回的完整结果
        """
        # 编码图片
        file_data = self._encode_image(image_path)
        
        # 准备请求头
        headers = {
            "Authorization": f"token {self.api_token}",
            "Content-Type": "application/json"
        }
        
        # 准备请求体
        payload = {
            "file": file_data,
            "fileType": file_type,
            **self.config,
            **kwargs  # 允许覆盖默认配置
        }
        
        # 发送请求
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
            
            if response.status_code != 200:
                error_msg = f"API 请求失败，状态码: {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f"\n错误详情: {error_detail}"
                except:
                    error_msg += f"\n响应内容: {response.text[:200]}"
                raise RuntimeError(error_msg)
            
            return response.json()
        
        except requests.RequestException as e:
            raise RuntimeError(f"API 请求异常: {e}")
    
    def get_markdown(
        self, 
        image_path: Union[str, Path],
        save_images: bool = False,
        output_dir: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> str:
        """
        对图片进行 OCR 识别并返回 Markdown 文本
        
        Args:
            image_path: 图片路径
            save_images: 是否保存 Markdown 中的图片
            output_dir: 图片保存目录（仅当 save_images=True 时有效）
            **kwargs: 其他 API 参数
            
        Returns:
            Markdown 格式的文本
        """
        result = self.ocr(image_path, **kwargs)
        
        # 提取结果
        api_result = result.get("result", {})
        layout_results = api_result.get("layoutParsingResults", [])
        
        if not layout_results:
            raise ValueError("API 返回结果为空")
        
        # 合并所有页面的 Markdown
        markdown_texts = []
        
        for i, page_result in enumerate(layout_results):
            markdown_data = page_result.get("markdown", {})
            text = markdown_data.get("text", "")
            markdown_texts.append(text)
            
            # 保存图片（如果需要）
            if save_images:
                images = markdown_data.get("images", {})
                if images:
                    self._save_markdown_images(
                        images, 
                        output_dir or Path(image_path).parent,
                        page_index=i
                    )
        
        return "\n\n---\n\n".join(markdown_texts)
    
    def _save_markdown_images(
        self, 
        images: Dict[str, str],
        output_dir: Union[str, Path],
        page_index: int = 0
    ):
        """
        保存 Markdown 中的图片
        
        Args:
            images: 图片路径和 URL 的字典
            output_dir: 输出目录
            page_index: 页面索引
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for img_path, img_url in images.items():
            try:
                full_img_path = output_dir / img_path
                full_img_path.parent.mkdir(parents=True, exist_ok=True)
                
                img_bytes = requests.get(img_url).content
                with open(full_img_path, "wb") as img_file:
                    img_file.write(img_bytes)
                
                print(f"[info] 图片已保存: {full_img_path}")
            
            except Exception as e:
                print(f"[warn] 保存图片失败 {img_path}: {e}")
    
    def batch_ocr(
        self,
        image_paths: List[Union[str, Path]],
        **kwargs
    ) -> List[str]:
        """
        批量处理多个图片
        
        Args:
            image_paths: 图片路径列表
            **kwargs: 其他 API 参数
            
        Returns:
            Markdown 文本列表
        """
        results = []
        total = len(image_paths)
        
        for i, image_path in enumerate(image_paths, start=1):
            try:
                print(f"[info] 处理 [{i}/{total}]: {image_path}")
                markdown = self.get_markdown(image_path, **kwargs)
                results.append(markdown)
            except Exception as e:
                print(f"[error] 处理失败 {image_path}: {e}")
                results.append(f"[ERROR] 处理失败: {e}")
        
        return results


# 便捷函数
def ocr_image(
    image_path: Union[str, Path],
    api_url: Optional[str] = None,
    api_token: Optional[str] = None,
    save_images: bool = False,
    output_dir: Optional[Union[str, Path]] = None,
    **kwargs
) -> str:
    """
    对单张图片进行 OCR 识别（便捷函数）
    
    Args:
        image_path: 图片路径
        api_url: API 地址（可选）
        api_token: API Token（可选）
        save_images: 是否保存 Markdown 中的图片
        output_dir: 图片保存目录
        **kwargs: 其他 API 参数
        
    Returns:
        Markdown 格式的文本
    """
    client = PaddleOCRClient(api_url=api_url, api_token=api_token)
    return client.get_markdown(
        image_path, 
        save_images=save_images,
        output_dir=output_dir,
        **kwargs
    )


def ocr_images_batch(
    image_paths: List[Union[str, Path]],
    api_url: Optional[str] = None,
    api_token: Optional[str] = None,
    **kwargs
) -> List[str]:
    """
    批量处理多个图片（便捷函数）
    
    Args:
        image_paths: 图片路径列表
        api_url: API 地址（可选）
        api_token: API Token（可选）
        **kwargs: 其他 API 参数
        
    Returns:
        Markdown 文本列表
    """
    client = PaddleOCRClient(api_url=api_url, api_token=api_token)
    return client.batch_ocr(image_paths, **kwargs)


if __name__ == "__main__":
    # 测试代码
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python paddle_ocr_client.py <图片路径>")
        sys.exit(1)
    
    test_image = sys.argv[1]
    
    try:
        print(f"正在识别图片: {test_image}")
        markdown_text = ocr_image(test_image, save_images=True)
        
        print("\n" + "="*50)
        print("识别结果（Markdown）:")
        print("="*50)
        print(markdown_text)
        
        # 保存结果
        output_file = Path(test_image).with_suffix('.md')
        output_file.write_text(markdown_text, encoding='utf-8')
        print(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

