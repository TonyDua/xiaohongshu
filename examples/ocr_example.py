"""
OCR 功能使用示例
"""

from pathlib import Path
import sys

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ocr import ocr_image, ocr_images_batch, PaddleOCRClient


def example_1_simple():
    """示例 1：最简单的使用方式"""
    print("=" * 60)
    print("示例 1：简单使用")
    print("=" * 60)
    
    # 替换为你的图片路径
    image_path = "path/to/your/image.jpg"
    
    try:
        # 识别图片，返回 Markdown 文本
        markdown_text = ocr_image(image_path)
        print(markdown_text)
        
        # 保存结果
        output_file = Path(image_path).with_suffix('.md')
        output_file.write_text(markdown_text, encoding='utf-8')
        print(f"\n结果已保存到: {output_file}")
        
    except Exception as e:
        print(f"错误: {e}")


def example_2_with_images():
    """示例 2：保存 Markdown 中的图片"""
    print("\n" + "=" * 60)
    print("示例 2：保存 Markdown 图片")
    print("=" * 60)
    
    image_path = "path/to/your/image.jpg"
    
    try:
        markdown_text = ocr_image(
            image_path,
            save_images=True,        # 保存图片
            output_dir="ocr_output"  # 指定输出目录
        )
        
        print(markdown_text)
        
    except Exception as e:
        print(f"错误: {e}")


def example_3_batch():
    """示例 3：批量处理多个图片"""
    print("\n" + "=" * 60)
    print("示例 3：批量处理")
    print("=" * 60)
    
    # 图片列表
    image_paths = [
        "image1.jpg",
        "image2.png",
        "image3.webp",
    ]
    
    try:
        # 批量处理
        results = ocr_images_batch(image_paths)
        
        # 输出结果
        for i, (image_path, markdown) in enumerate(zip(image_paths, results), start=1):
            print(f"\n--- 图片 {i}: {image_path} ---")
            print(markdown[:200] + "..." if len(markdown) > 200 else markdown)
            
            # 保存结果
            output_file = Path(image_path).with_suffix('.md')
            output_file.write_text(markdown, encoding='utf-8')
            print(f"已保存到: {output_file}")
        
    except Exception as e:
        print(f"错误: {e}")


def example_4_advanced():
    """示例 4：使用客户端类，自定义参数"""
    print("\n" + "=" * 60)
    print("示例 4：高级使用")
    print("=" * 60)
    
    try:
        # 创建客户端，自定义配置
        client = PaddleOCRClient(
            config={
                "useDocOrientationClassify": True,  # 启用方向矫正
                "useDocUnwarping": True,             # 启用扭曲矫正
                "useLayoutDetection": True,          # 启用版面分析
                "useChartRecognition": True,         # 启用图表识别
                "layoutThreshold": 0.6,              # 提高过滤强度
                "prettifyMarkdown": True,            # 美化 Markdown
            }
        )
        
        # 识别图片
        image_path = "path/to/your/image.jpg"
        markdown = client.get_markdown(image_path)
        print(markdown)
        
        # 获取完整的 API 响应
        full_result = client.ocr(image_path)
        print(f"\nAPI 响应状态: {full_result.get('errorMsg')}")
        
    except Exception as e:
        print(f"错误: {e}")


def example_5_pdf():
    """示例 5：处理 PDF 文件"""
    print("\n" + "=" * 60)
    print("示例 5：处理 PDF")
    print("=" * 60)
    
    pdf_path = "path/to/your/document.pdf"
    
    try:
        # 识别 PDF（注意 file_type=0）
        markdown_text = ocr_image(
            pdf_path,
            file_type=0,  # 0 表示 PDF
            save_images=True,
            output_dir="pdf_output"
        )
        
        print(markdown_text)
        
        # 保存结果
        output_file = Path(pdf_path).with_suffix('.md')
        output_file.write_text(markdown_text, encoding='utf-8')
        print(f"\nPDF 转换完成，已保存到: {output_file}")
        
    except Exception as e:
        print(f"错误: {e}")


def example_6_error_handling():
    """示例 6：错误处理"""
    print("\n" + "=" * 60)
    print("示例 6：错误处理")
    print("=" * 60)
    
    image_paths = ["good_image.jpg", "not_exist.jpg", "another_good.jpg"]
    
    results = []
    for image_path in image_paths:
        try:
            print(f"\n处理: {image_path}")
            markdown = ocr_image(image_path)
            results.append((image_path, markdown, None))
            print("✓ 成功")
            
        except FileNotFoundError as e:
            print(f"✗ 文件不存在: {e}")
            results.append((image_path, None, "文件不存在"))
            
        except RuntimeError as e:
            print(f"✗ API 错误: {e}")
            results.append((image_path, None, "API 错误"))
            
        except Exception as e:
            print(f"✗ 未知错误: {e}")
            results.append((image_path, None, str(e)))
    
    # 统计结果
    success = sum(1 for _, md, err in results if err is None)
    print(f"\n处理完成: 成功 {success}/{len(image_paths)}")


if __name__ == "__main__":
    print("OCR 功能使用示例")
    print("请先配置 config/ocr_api.py 或设置环境变量\n")
    
    # 运行示例（根据需要注释/取消注释）
    # example_1_simple()
    # example_2_with_images()
    # example_3_batch()
    # example_4_advanced()
    # example_5_pdf()
    # example_6_error_handling()
    
    print("\n提示：请取消注释上面的示例函数来运行")

