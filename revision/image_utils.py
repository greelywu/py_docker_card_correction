import os
import tempfile
import numpy as np
from PIL import Image
import cv2
import logging

logger = logging.getLogger(__name__)

def numpy_to_temp_file(img_array, format='JPEG'):
    """将numpy数组保存为临时文件"""
    try:
        if isinstance(img_array, np.ndarray):
            # 确保是3通道图像
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                # 反转通道顺序 BGR->RGB
                img_array = img_array[:, :, ::-1]
            
            # 创建临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            pil_image = Image.fromarray(img_array)
            pil_image.save(temp_file.name, format, quality=95)
            temp_file.close()
            return temp_file.name
    except Exception as e:
        logger.error(f"创建临时文件失败: {e}")
    return None

def compress_image(image_path, max_size=(800, 800), quality=85):
    """压缩图片"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 创建临时文件保存压缩后的图片
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            img.save(temp_file.name, 'JPEG', quality=quality, optimize=True)
            temp_file.close()
            
            return temp_file.name
    except Exception as e:
        logger.error(f"压缩图片失败 {image_path}: {e}")
        return image_path

def process_image_format(image_array):
    """处理图像格式，修复反色问题"""
    if isinstance(image_array, np.ndarray):
        # 检查图像是否可能是反色的（黑白颠倒）
        if len(image_array.shape) == 3:
            # 计算图像的平均亮度
            mean_brightness = np.mean(image_array)
            
            # 如果平均亮度很低，可能是反色图像
            if mean_brightness < 50:
                # 反转图像
                image_array = 255 - image_array
                logger.info("检测到反色图像，已自动校正")
        
        return image_array
    return image_array