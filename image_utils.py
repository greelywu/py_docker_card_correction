# 图像处理工具函数
import tempfile
import logging
from PIL import Image
import cv2
import numpy as np
import os
import shutil

logger = logging.getLogger(__name__)

def compress_image(input_path, output_path=None, max_width=800, quality=85, max_size_kb=20):
    """
    压缩单张图片，支持调整尺寸和文件大小限制
    
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径（可选，默认为输入路径+'_compressed'）
        max_width: 最大宽度（像素）
        quality: 初始压缩质量（1-100）
        max_size_kb: 文件大小上限（KB，仅对JPEG有效）
    
    Returns:
        bool: 是否成功压缩
    """
    # 设置默认输出路径
    output_path = input_path
    input_file_size_kb = os.path.getsize(input_path) / 1024
    if input_file_size_kb > max_size_kb:
        try:
            with Image.open(input_path) as img:
                # 调整尺寸
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.LANCZOS)
                
                # 获取文件格式
                format = img.format or 'JPEG'
                
                # 确保输出目录存在
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 根据格式选择压缩方式
                if format == 'PNG':
                    # PNG格式处理 - 使用外部工具或PIL
                    try:                    
                        # 尝试使用pngquant压缩
                        subprocess.run([
                            "pngquant",
                            "--force",
                            "--speed", "1",
                            "--quality", f"{max(10, 100 - quality)}-100",
                            "--output", output_path,
                            "--",
                            output_path
                        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # 使用optipng进一步优化
                        subprocess.run([
                            "optipng",
                            "-o5",
                            "-quiet",
                            "-clobber",
                            output_path
                        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        logger.info(f"PNG工具压缩: {input_path} -> {output_path}")
                        
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # 备用方案：使用PIL压缩
                        img.save(output_path, 'PNG', optimize=True)
                        logger.info(f"PNG PIL压缩: {input_path} -> {output_path}")
                
                else:
                    # 对于其他格式，转换为RGB（如果必要）
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    current_quality = quality
                    temp_output = output_path + ".tmp"
                    
                    while current_quality >= 10:  # 最低质量设为10
                        # 保存图片
                        img.save(temp_output, 'JPEG', quality=current_quality, optimize=True)
                        
                        # 检查文件大小
                        file_size_kb = os.path.getsize(temp_output) / 1024
                        
                        if file_size_kb <= max_size_kb or current_quality <= 10:
                            # 满足要求或达到最低质量，移动文件并退出循环
                            shutil.move(temp_output, output_path)
                            logger.info(f"JPEG压缩(质量{current_quality}): {input_path} -> {output_path} ({file_size_kb:.1f}KB)")
                            break
                        
                        # 不满足要求，降低质量继续尝试
                        current_quality -= 5
                        os.remove(temp_output)
                    
                    # 清理临时文件（如果存在）
                    if os.path.exists(temp_output):
                        os.remove(temp_output)
                
                return output_path
                
        except Exception as e:
            logger.error(f"处理图片 {input_path} 时出错: {str(e)}")
            return input_path
    else:
        return input_path

def numpy_to_temp_file(image_array, suffix='.jpg'):
    """将numpy数组保存为临时文件"""
    try:
        if isinstance(image_array, np.ndarray):
            # 确保图像格式正确
            if image_array.dtype != np.uint8:
                if image_array.max() <= 1.0:
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)
            
            # BGR转RGB
            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                image_array = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            
            # 转换为PIL图像并调整大小
            pil_image = Image.fromarray(image_array)
            pil_image.thumbnail((300, 300), Image.Resampling.LANCZOS)
            
            # 保存为临时文件
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            pil_image.save(temp_file.name, "JPEG", quality=85)
            return temp_file.name
            
    except Exception as e:
        logger.error(f"转换图片为临时文件失败: {e}")
    return None

def process_image_format(img):
    """统一处理图像格式"""
    logger.debug(f"处理图像格式: 原始形状 {img.shape}, 类型 {img.dtype}")
    
    # 确保数据类型
    if img.dtype != np.uint8:
        if img.max() <= 1.0:
            img = (img * 255).astype(np.uint8)
        else:
            img = img.astype(np.uint8)
    
    # BGR转RGB
    if len(img.shape) == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    logger.debug(f"处理后的图像格式: 形状 {img.shape}, 类型 {img.dtype}")
    return img