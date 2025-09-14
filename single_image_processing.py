# 单张图片处理功能
import tempfile
import logging
from PIL import Image
import numpy as np

from card_processor import processor
from image_utils import process_image_format

logger = logging.getLogger(__name__)

def process_single_image(image, output_format="png"):
    """处理单张图片"""
    logger.info(f"开始处理单张图片，输出格式: {output_format}")
    
    if not processor.init_model():
        error_msg = "模型初始化失败"
        logger.error(error_msg)
        return error_msg, [], None, None
    
    if image is None:
        error_msg = "请先上传图片"
        logger.warning(error_msg)
        return error_msg, [], None, None
    
    try:
        logger.info("调用模型处理图片...")
        # 处理图片
        result = processor.model(image)
        logger.info(f"模型返回结果: {type(result)}")
        
        if not result or "output_imgs" not in result or not result["output_imgs"]:
            warning_msg = "未检测到证卡"
            logger.warning(warning_msg)
        else:
            output_imgs = result["output_imgs"]
            progress_info = f"检测到 {len(output_imgs)} 张证卡\n"
            processed_cards = []
            
            logger.info(f"处理 {len(output_imgs)} 张输出图片")
            for i, img in enumerate(output_imgs):
                try:
                    if isinstance(img, np.ndarray):
                        # 处理图像格式
                        img = process_image_format(img)
                        
                        # 保存临时文件用于显示
                        with tempfile.NamedTemporaryFile(suffix=f'.{output_format}', delete=False) as tmp:
                            Image.fromarray(img).save(tmp.name)
                            processed_cards.append(tmp.name)
                            logger.info(f"保存临时文件: {tmp.name}")
                        
                        progress_info += f"✓ 证卡 {i+1} 处理成功\n"
                    else:
                        progress_info += f"✗ 证卡 {i+1} 格式不支持\n"
                        logger.warning(f"图片 {i+1} 格式不支持: {type(img)}")
                except Exception as e:
                    error_msg = f"✗ 证卡 {i+1} 处理失败: {str(e)}"
                    progress_info += error_msg + "\n"
                    logger.error(error_msg)
            
            success_msg = f"处理完成，成功处理 {len(processed_cards)} 张证卡"
            logger.info(success_msg)
            return progress_info, processed_cards, processed_cards[0] if processed_cards else None
        
        return warning_msg, [], None, None
        
    except Exception as e:
        error_msg = f"处理失败: {str(e)}"
        logger.exception(error_msg)
        return error_msg, [], None, None