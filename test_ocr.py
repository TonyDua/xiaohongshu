#!/usr/bin/env python3
"""
OCR 功能快速测试脚本
"""

import sys
from pathlib import Path

from src.ocr import ocr_image


def main():
    if len(sys.argv) < 2:
        print("用法: python test_ocr.py <图片路径>")
        print("\n示例:")
        print("  python test_ocr.py output/images/66172550000000001a00d168_1.webp")
        sys.exit(1)
    
    image_path = sys.argv[1]
    
    if not Path(image_path).exists():
        print(f"错误: 图片文件不存在: {image_path}")
        sys.exit(1)
    
    print(f"正在识别图片: {image_path}")
    print("=" * 60)
    
    try:
        # 识别图片
        markdown_text = ocr_image(image_path, save_images=True)
        
        # 输出结果
        print("\n识别结果（Markdown）:")
        print("=" * 60)
        print(markdown_text)
        print("=" * 60)
        
        # 保存结果
        output_file = Path(image_path).with_suffix('.md')
        output_file.write_text(markdown_text, encoding='utf-8')
        print(f"\n✓ 结果已保存到: {output_file}")
        
    except ValueError as e:
        print(f"\n✗ 配置错误: {e}")
        print("\n请配置 API 信息:")
        print("1. 编辑 config/ocr_api.py 填写 API_URL 和 API_TOKEN")
        print("2. 或设置环境变量:")
        print("   $env:PADDLEOCR_API_URL = \"your-api-url\"")
        print("   $env:PADDLEOCR_API_TOKEN = \"your-api-token\"")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

