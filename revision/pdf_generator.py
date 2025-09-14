import os
import tempfile
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from PIL import Image
import shutil

logger = logging.getLogger(__name__)

def generate_pdf(image_paths, names_list, output_filename="output.pdf"):
    """生成PDF文件"""
    try:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_filename)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # 创建PDF
        c = canvas.Canvas(output_filename, pagesize=A4)
        page_width, page_height = A4
        
        # 设置边距和图片尺寸
        margin = 20 * mm
        image_width = (page_width - 3 * margin) / 2
        image_height = image_width * 0.63  # 身份证比例
        
        current_y = page_height - margin
        current_x = margin
        page_count = 0
        
        for i, image_path in enumerate(image_paths):
            try:
                # 检查图片是否存在
                if not os.path.exists(image_path):
                    logger.warning(f"图片不存在: {image_path}")
                    continue
                
                # 如果是第一张图片或者当前页已满，创建新页面
                if current_y < margin + image_height:
                    c.showPage()
                    current_y = page_height - margin
                    current_x = margin
                    page_count += 1
                
                # 添加图片
                img = Image.open(image_path)
                c.drawImage(image_path, current_x, current_y - image_height, 
                           width=image_width, height=image_height)
                
                # 添加姓名（如果提供了姓名列表）
                if i < len(names_list) and names_list[i]:
                    name = str(names_list[i])
                    c.setFont("Helvetica", 10)
                    c.drawString(current_x, current_y - image_height - 15, name)
                
                # 更新位置
                current_x += image_width + margin
                if current_x + image_width > page_width - margin:
                    current_x = margin
                    current_y -= image_height + margin + 20
                
            except Exception as e:
                logger.error(f"添加图片到PDF失败 {image_path}: {e}")
                continue
        
        # 保存PDF
        c.save()
        logger.info(f"PDF生成成功: {output_filename}, 共 {page_count + 1} 页")
        return output_filename
        
    except Exception as e:
        logger.error(f"生成PDF失败: {e}")
        return None

def sort_images_by_type(image_paths, image_info_list, names_list):
    """按照每行先正面后背面的顺序排序图片"""
    try:
        # 按行索引分组
        rows = {}
        for i, info in enumerate(image_info_list):
            row_index = info["row_index"]
            if row_index not in rows:
                rows[row_index] = {"正面": [], "背面": [], "names": []}
            
            rows[row_index][info["type"]].append({
                "path": image_paths[i],
                "index": i
            })
            
            # 保存姓名信息
            if i < len(names_list):
                rows[row_index]["names"].append(names_list[i])
        
        # 按行索引排序
        sorted_rows = sorted(rows.items(), key=lambda x: x[0])
        
        # 构建排序后的图片列表和姓名列表
        sorted_images = []
        sorted_names = []
        
        for row_index, row_data in sorted_rows:
            # 先添加正面图片
            for front_img in row_data["正面"]:
                sorted_images.append(front_img["path"])
                if front_img["index"] < len(names_list):
                    sorted_names.append(names_list[front_img["index"]])
            
            # 再添加背面图片
            for back_img in row_data["背面"]:
                sorted_images.append(back_img["path"])
                if back_img["index"] < len(names_list):
                    sorted_names.append(names_list[back_img["index"]])
        
        return sorted_images
    except Exception as e:
        logger.error(f"排序图片失败: {e}")
        return image_paths