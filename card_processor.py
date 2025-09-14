# CardProcessor类
import os
import re
import time
import logging
from urllib.parse import unquote, urlparse
from PIL import Image
import numpy as np
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

from config import CACHE_DIR
from image_utils import process_image_format

logger = logging.getLogger(__name__)

class CardProcessor:
    def __init__(self):
        self.model = None
        self.model_loaded = False
        self.selection_cache = {}  # 缓存用户选择
        self.current_selection_data = {}  # 当前需要选择的数据
        self.processed_images = []  # 存储所有处理后的图片路径
        self.image_info_list = []  # 存储图片信息（正面/背面，行索引）
        self.names_list = []  # 存储姓名信息
        self.timestamp_dir = None  # 时间戳目录
        self.output_image_paths = {}  # 存储输出图片路径映射
    
    def init_model(self):
        """初始化模型"""
        if self.model is not None and self.model_loaded:
            logger.info("模型已加载")
            return True
            
        try:
            logger.info("正在初始化模型...")
            self.model = pipeline(Tasks.card_detection_correction, 
                                model='iic/cv_resnet18_card_correction')
            self.model_loaded = True
            logger.info("模型初始化成功")
            return True
        except Exception as e:
            logger.error(f"模型初始化失败: {e}")
            return False

    def check_cache(self, original_url):
        """检查本地缓存中是否存在已处理的图片"""
        try:
            # 从URL中提取文件路径
            parsed_url = urlparse(original_url)
            file_path = parsed_url.path
            
            # 处理/file/开头的路径
            if file_path.startswith('/file/'):
                file_path = file_path[6:]  # 去掉/file/前缀
            
            # URL解码和清理路径
            file_path = unquote(file_path)
            file_path = re.sub(r'^/', '', file_path)  # 去掉开头的斜杠
            file_path = re.sub(r'[^\w\.\/-]', '_', file_path)  # 替换非法字符
                        
            # 确保文件扩展名为.jpg
            base_name = os.path.basename(file_path)
            
            # 构建缓存路径
            cache_path = os.path.join(CACHE_DIR, file_path)
            
            # 检查缓存文件是否存在
            if os.path.exists(cache_path):
                logger.info(f"找到缓存文件: {cache_path}")
                return cache_path
                
            # 检查目录是否存在，不存在则创建
            cache_dir = os.path.dirname(cache_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            return None
            
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")
            return None

    def save_to_cache(self, image_array, original_url):
        """将处理后的图片保存到缓存"""
        try:
            # 从URL中提取文件路径
            parsed_url = urlparse(original_url)
            file_path = parsed_url.path
            
            # 处理/file/开头的路径
            if file_path.startswith('/file/'):
                file_path = file_path[6:]  # 去掉/file/前缀
            
            # URL解码和清理路径
            file_path = unquote(file_path)
            file_path = re.sub(r'^/', '', file_path)  # 去掉开头的斜杠
            file_path = re.sub(r'[^\w\.\/-]', '_', file_path)  # 替换非法字符
                        
            # 原文件名
            base_name = os.path.basename(file_path)
            
            # 获取文件扩展名
            ext = os.path.splitext(file_path)[1].lower()
            
            # 构建缓存路径
            cache_path = os.path.join(CACHE_DIR, file_path)
            
            # 检查目录是否存在，不存在则创建
            cache_dir = os.path.dirname(cache_path)
            os.makedirs(cache_dir, exist_ok=True)
            
            # 处理图像格式 - 修复反色问题
            img = process_image_format(image_array)
            if img.shape[2] == 3:  # 确保是3通道图像
                img = img[:, :, ::-1]  # 反转通道顺序 BGR->RGB
            
            # 保存为正确格式
            pil_image = Image.fromarray(img)
            try:
                if ext in ['.jpg', '.jpeg']:
                    # JPEG格式 - 需要RGB模式，支持质量参数
                    if pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                    pil_image.save(cache_path, 'JPEG', quality=85)
                    
                elif ext == '.png':
                    # PNG格式 - 支持透明度，不支持质量参数
                    pil_image.save(cache_path, 'PNG')
                    
                elif ext in ['.bmp', '.dib']:
                    # BMP格式
                    pil_image.save(cache_path, 'BMP')
                    
                elif ext in ['.tif', '.tiff']:
                    # TIFF格式
                    pil_image.save(cache_path, 'TIFF')
                    
                elif ext == '.webp':
                    # WebP格式 - 支持质量参数
                    if pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                    pil_image.save(cache_path, 'WEBP', quality=85)
                    
                else:
                    # 其他格式，尝试使用默认保存
                    pil_image.save(cache_path)
            
                logger.info(f"图片已保存到缓存: {cache_path}")
                return cache_path
            
            except Exception as e:
                print(f"保存图片时出错: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"保存到缓存失败: {e}")
            return None

    def save_selection(self, url, card_type, selected_indices):
        """保存用户选择"""
        key = f"{url}_{card_type}"
        self.selection_cache[key] = selected_indices
        logger.info(f"保存选择: {key} -> {selected_indices}")

    def get_selection(self, url, card_type):
        """获取用户选择"""
        key = f"{url}_{card_type}"
        return self.selection_cache.get(key, [0])  # 默认选择第一张

    def set_selection_data(self, data):
        """设置当前需要选择的数据"""
        self.current_selection_data = data

    def get_selection_data(self):
        """获取当前需要选择的数据"""
        return self.current_selection_data

    def add_processed_image(self, image_path, card_type, row_index, name=None):
        """添加处理后的图片"""
        self.processed_images.append(image_path)
        self.image_info_list.append({
            "path": image_path,
            "type": card_type,
            "row_index": row_index
        })
        if name:
            self.names_list.append(name)

    def get_processed_data(self):
        """获取所有处理后的数据"""
        return self.processed_images, self.image_info_list, self.names_list

    def clear_processed_data(self):
        """清空处理数据"""
        self.processed_images = []
        self.image_info_list = []
        self.names_list = []
        
    def init_timestamp_dir(self):
        """初始化时间戳目录"""
        if self.timestamp_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.timestamp_dir = f"/home/{timestamp}"
            os.makedirs(self.timestamp_dir, exist_ok=True)
            os.makedirs(os.path.join(self.timestamp_dir, "file"), exist_ok=True)
            logger.info(f"创建时间戳目录: {self.timestamp_dir}")
        return self.timestamp_dir

# 全局处理器
processor = CardProcessor()