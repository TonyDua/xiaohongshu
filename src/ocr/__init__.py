"""OCR 模块 - 基于 PaddleOCR-VL API"""

from .paddle_ocr_client import PaddleOCRClient, ocr_image, ocr_images_batch

__all__ = ['PaddleOCRClient', 'ocr_image', 'ocr_images_batch']

