# CardProcessor类
import os
import re
import time
import logging
import shutil
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
        self.temp_files_to_cleanup = []  # 需要清理的临时文件
    
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
            cache_path = self._get_cache_path(original_url)
            
            # 检查缓存文件是否存在
            if os.path.exists(cache_path):
                logger.info(f"找到缓存文件: {cache_path}")
                return cache_path
                
            return None
            
        except Exception as e:
            logger.error(f"检查缓存失败: {e}")
            return None

    def _get_cache_path(self, original_url):
        """根据URL生成缓存路径"""
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
        
        # 构建缓存路径
        cache_path = os.path.join(CACHE_DIR, file_path)
        
        # 检查目录是否存在，不存在则创建
        cache_dir = os.path.dirname(cache_path)
        os.makedirs(cache_dir, exist_ok=True)
        
        return cache_path

    def save_image(self, image_array, original_url):
        """
        保存图片到缓存目录
        返回缓存文件路径
        """
        try:
            cache_path = self._get_cache_path(original_url)
            
            # 处理图像格式 - 修复反色问题
            img = process_image_format(image_array)
            if img.shape[2] == 3:  # 确保是3通道图像
                img = img[:, :, ::-1]  # 反转通道顺序 BGR->RGB
            
            # 根据原始URL的文件扩展名确定保存格式
            parsed_url = urlparse(original_url)
            file_ext = os.path.splitext(parsed_url.path)[1].lower()
            
            if file_ext in ['.jpg', '.jpeg']:
                format = 'JPEG'
            elif file_ext == '.png':
                format = 'PNG'
            else:
                # 默认使用JPEG
                format = 'JPEG'
                cache_path = cache_path + '.jpg'  # 确保有正确的扩展名
            
            # 保存图片
            pil_image = Image.fromarray(img)
            pil_image.save(cache_path, format, quality=95)
            
            logger.info(f"图片已保存到缓存: {cache_path}")
            return cache_path
            
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
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
        
        # 如果不是缓存文件，添加到清理列表
        if not image_path.startswith(CACHE_DIR):
            self.temp_files_to_cleanup.append(image_path)

    def get_processed_data(self):
        """获取所有处理后的数据"""
        return self.processed_images, self.image_info_list, self.names_list

    def clear_processed_data(self):
        """清空处理数据"""
        # 清理临时文件
        for temp_file in self.temp_files_to_cleanup:
            try:
                if os.path.exists(temp_file) and not temp_file.startswith(CACHE_DIR):
                    os.unlink(temp_file)
                    logger.debug(f"清理临时文件: {temp_file}")
            except Exception as e:
                logger.warning(f"清理临时文件失败 {temp_file}: {e}")
        
        self.processed_images = []
        self.image_info_list = []
        self.names_list = []
        self.temp_files_to_cleanup = []
        
    def cleanup_all_temp_files(self):
        """清理所有临时文件（除了缓存目录中的文件）"""
        self.clear_processed_data()
        
        # 清理其他可能的临时目录
        temp_dirs = ['/tmp', '/home/tmp']
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if file.endswith(('.jpg', '.jpeg', '.png', '.pdf')):
                                file_path = os.path.join(root, file)
                                try:
                                    os.unlink(file_path)
                                    logger.debug(f"清理临时文件: {file_path}")
                                except:
                                    pass
                except Exception as e:
                    logger.warning(f"清理临时目录 {temp_dir} 失败: {e}")

# 全局处理器
processor = CardProcessor()