# PDF生成功能
import os
import tempfile
import logging
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.colors import black

logger = logging.getLogger(__name__)

def sort_images_by_type(image_paths, image_info_list, names_list):
    """按照每行先正面后背面的顺序排序图片"""
    # 创建映射关系
    path_to_info = {info["path"]: info for info in image_info_list}
    
    # 按行索引分组
    row_groups = {}
    for img_path in image_paths:
        if img_path in path_to_info:
            info = path_to_info[img_path]
            row_index = info["row_index"]
            if row_index not in row_groups:
                row_groups[row_index] = {"正面": [], "背面": []}
            row_groups[row_index][info["type"]].append(img_path)
    
    # 按行索引排序并合并
    sorted_images = []
    for row_index in sorted(row_groups.keys()):
        row_data = row_groups[row_index]
        # 先添加正面图片，再添加背面图片
        sorted_images.extend(row_data["正面"])
        sorted_images.extend(row_data["背面"])
    
    return sorted_images

def generate_pdf(image_paths, names_list, output_name):
    """生成PDF文件，每页4行2列，图片下方添加序号和姓名"""
    logger.info(f"开始生成PDF: {output_name}, 包含 {len(image_paths)} 张图片")
    
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, output_name)
    
    page_width, page_height = portrait(A4)
    margin = 40
    rows_per_page = 4
    cols_per_row = 2
    
    img_width = (page_width - 2 * margin - (cols_per_row-1)*15) / cols_per_row
    img_height = (page_height - 2 * margin - (rows_per_page-1)*15) / rows_per_page
    
    c = canvas.Canvas(pdf_path, pagesize=portrait(A4))
    
    # 设置中文字体函数
    def set_chinese_font():
        """设置中文字体，每页都需要调用"""
        try:
            # 尝试使用系统中文字体
            font_paths = [
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
            ]
            
            chinese_font_registered = False
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        # 检查字体是否已经注册
                        if 'ChineseFont' not in pdfmetrics.getRegisteredFontNames():
                            pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                        c.setFont("ChineseFont", 10)
                        chinese_font_registered = True
                        logger.info(f"使用中文字体: {font_path}")
                        break
                    except Exception as e:
                        logger.warning(f"无法注册字体 {font_path}: {e}")
                        continue
            
            if not chinese_font_registered:
                # 如果没有找到中文字体，使用默认字体
                c.setFont("Helvetica", 10)
                logger.warning("使用默认英文字体，中文可能显示为方块")
                
        except Exception as e:
            c.setFont("Helvetica", 10)
            logger.error(f"设置字体失败: {e}")
    
    # 第一页设置字体
    set_chinese_font()
    
    current_page = 0
    images_per_page = rows_per_page * cols_per_row
    
    # 获取图片信息映射
    from card_processor import processor
    path_to_info = {}
    for info in processor.image_info_list:
        path_to_info[info["path"]] = info
    
    # 创建行索引到姓名的映射 - 修复：确保每个行索引只对应一个姓名
    row_to_name = {}
    for i, name in enumerate(names_list):
        if i < len(processor.image_info_list):
            row_index = processor.image_info_list[i]["row_index"]
            row_to_name[row_index] = name
    
    for page_start in range(0, len(image_paths), images_per_page):
        if page_start > 0:
            c.showPage()
            current_page += 1
            # 每页都需要重新设置字体
            set_chinese_font()
        
        page_images = image_paths[page_start:page_start + images_per_page]
        logger.debug(f"生成第 {current_page + 1} 页，包含 {len(page_images)} 张图片")
        
        for idx, img_path in enumerate(page_images):
            # 计算行和列的位置
            row = idx // cols_per_row
            col = idx % cols_per_row
            
            x = margin + col * (img_width + 15)
            y = page_height - margin - (row + 1) * img_height - row * 15
            
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    ratio = width / height
                    
                    if ratio > img_width / img_height:
                        display_width = img_width
                        display_height = img_width / ratio
                    else:
                        display_height = img_height
                        display_width = img_height * ratio
                
                x_center = x + (img_width - display_width) / 2
                y_center = y + (img_height - display_height) / 2
                
                # 绘制图片
                c.drawImage(img_path, x_center, y_center, display_width, display_height)
                
                # 在图片下方添加序号和姓名
                text_y = y_center - 15
                image_index = page_start + idx
                
                # 获取图片信息
                if img_path in path_to_info:
                    info = path_to_info[img_path]
                    card_type = info["type"]
                    row_index = info["row_index"]
                    
                    # 获取姓名 - 修复：直接从映射中获取，确保每个行索引只对应一个姓名
                    name = row_to_name.get(row_index, "")
                    
                    # 生成标注文本：序号_姓名_正/反面
                    # 修复：使用正确的序号计算方式
                    if name:
                        label_text = f"{row_index + 1}_{name}_{card_type}"
                    else:
                        label_text = f"{row_index + 1}_{card_type}"
                    
                    c.drawString(x_center, text_y, label_text)
                else:
                    # 如果没有找到图片信息，只显示序号
                    c.drawString(x_center, text_y, f"{image_index + 1}")
                
            except Exception as e:
                logger.warning(f"无法将图片 {img_path} 添加到PDF: {e}")
                continue
        
        # 页码 - 使用英文字体确保显示正常
        total_pages = (len(image_paths) + images_per_page - 1) // images_per_page
        c.setFont("Helvetica", 10)
        c.drawCentredString(page_width - 30, 20, f"{current_page + 1}/{total_pages}")
        # 恢复中文字体
        set_chinese_font()
    
    c.save()
    logger.info(f"PDF生成完成: {pdf_path}")
    return pdf_path