# ModelScope 证卡处理工具 - 部署使用说明（模型下载到本地）

## 环境搭建

### 1. 启动Docker容器
```bash
# 下载官方镜像
docker pull modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-py311-torch2.3.1-1.29.0

# 运行容器（将/path/to/your/workspace替换为实际工作目录）
docker run -it --volume=/path/to/your/workspace:/home -p 8080:8080 --name modelscope-container modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-py311-torch2.3.1-1.29.0 /bin/bash
```

### 2. 进入Docker容器
如果容器已在后台运行，使用以下命令进入：
```bash
# 查看运行中的容器
docker ps

# 进入容器（使用容器名称或ID）
docker exec -it modelscope-container /bin/bash
```

### 3. 安装依赖和下载模型
在Docker容器内执行：
```bash
# 安装所需依赖包
pip install modelscope gradio opencv-python pillow pandas reportlab numpy

# 下载证卡校正模型（重要步骤）
modelscope download --model iic/cv_resnet18_card_correction
```

## 代码使用

### 1. 放置代码文件
将Python代码文件（如`grcard.py`）放置在Docker容器映射的工作目录中

### 2. 运行程序
在Docker容器内执行：
```bash
# 进入工作目录
cd /home

# 运行证卡处理工具
python grcard.py
```

### 3. 访问应用
程序启动后，通过浏览器访问：
```
http://localhost:8080
```

## 使用指南

### 单张图片处理
1. 选择"单张处理"标签页上传图片
2. 选择输出格式后点击"处理图片"
3. 查看提取的证卡结果

### 批量处理
1. 准备CSV文件（格式：姓名,正面URL,背面URL）
2. 选择"批量处理"标签页上传CSV
3. 点击"批量处理"并按要求选择多卡证图片（图片下方标示"序号_ 姓名_ 正面/反面")
4. 下载生成的PDF文件

## 重要提示
- **必须执行模型下载命令**：`modelscope download --model iic/cv_resnet18_card_correction`
- 首次运行需要下载模型，请确保网络连接正常
- 模型下载只需执行一次，后续运行会自动使用已下载的模型

## 完整代码

grcard.py :

```python
import cv2
import numpy as np
import pandas as pd
from PIL import Image
import gradio as gr
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.colors import black
import tempfile
import os
import logging
import json
import base64
from io import BytesIO

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

# 全局处理器
processor = CardProcessor()

def compress_image(image_path, max_size=(800, 800), quality=85):
    """压缩图片以减小文件大小"""
    try:
        with Image.open(image_path) as img:
            # 调整图片尺寸
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 创建临时文件保存压缩后的图片
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            img.save(temp_file.name, 'JPEG', quality=quality, optimize=True)
            return temp_file.name
    except Exception as e:
        logger.error(f"图片压缩失败: {e}")
        return image_path  # 如果压缩失败，返回原文件

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

def process_batch_images(csv_file, output_name="output.pdf"):
    """批量处理CSV文件"""
    logger.info(f"开始批量处理，输出文件: {output_name}")
    
    if not processor.init_model():
        error_msg = "模型初始化失败"
        logger.error(error_msg)
        yield error_msg, None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        return
    
    if csv_file is None:
        error_msg = "请先上传CSV文件"
        logger.warning(error_msg)
        yield error_msg, None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        return
    
    try:
        # 清空之前的数据
        processor.clear_processed_data()
        
        # 读取CSV
        logger.info(f"读取CSV文件: {csv_file.name}")
        df = pd.read_csv(csv_file.name, header=None)
        total_rows = len(df)
        logger.info(f"CSV文件包含 {total_rows} 行数据")
        
        progress_info = [f"开始处理，共 {total_rows} 行数据"]
        yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        
        selection_items = []
        
        # 处理每一行
        for i in range(total_rows):
            row_info = f"\n处理第 {i+1}/{total_rows} 行"
            progress_info.append(row_info)
            logger.info(row_info.strip())
            yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
            
            # 获取姓名（第一列）
            name = str(df.iloc[i, 0]).strip() if len(df.iloc[i]) > 0 else f"未知_{i+1}"
            
            # 处理正面和背面URL
            urls_to_process = []
            if len(df.iloc[i]) > 1:
                front_url = str(df.iloc[i, 1]).strip()
                if front_url and front_url != 'nan' and front_url != 'None':
                    urls_to_process.append(("正面", front_url, name))
            
            if len(df.iloc[i]) > 2:
                back_url = str(df.iloc[i, 2]).strip()
                if back_url and back_url != 'nan' and back_url != 'None':
                    urls_to_process.append(("背面", back_url, name))
            
            logger.info(f"第 {i+1} 行需要处理 {len(urls_to_process)} 个URL")
            
            for card_type, url, name in urls_to_process:
                try:
                    logger.info(f"处理 {card_type} URL: {url}")
                    result = processor.model(url)
                    
                    if result and result.get("output_imgs"):
                        cards_count = len(result["output_imgs"])
                        
                        # 检查是否需要用户选择
                        if cards_count > 1:
                            # 准备选择数据
                            selection_key = f"{url}_{card_type}"
                            temp_files = []
                            
                            for j, img in enumerate(result["output_imgs"]):
                                if isinstance(img, np.ndarray):
                                    temp_file = numpy_to_temp_file(img)
                                    if temp_file:
                                        temp_files.append(temp_file)
                            
                            if temp_files:
                                selection_items.append({
                                    "key": selection_key,
                                    "url": url,
                                    "card_type": card_type,
                                    "temp_files": temp_files,
                                    "row_index": i,
                                    "name": name,
                                    "selected_indices": processor.get_selection(url, card_type)
                                })
                            
                            progress_info.append(f"  ⚠ {card_type}: 检测到 {cards_count} 张卡证，需要选择")
                            logger.info(f"  ⚠ {card_type}: 检测到 {cards_count} 张卡证，需要选择")
                        else:
                            # 只有一张卡证，直接处理
                            for img in result["output_imgs"]:
                                if isinstance(img, np.ndarray):
                                    img = process_image_format(img)
                                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                                        Image.fromarray(img).save(tmp.name)
                                        # 压缩图片
                                        compressed_img_path = compress_image(tmp.name)
                                        processor.add_processed_image(compressed_img_path, card_type, i, name)
                                        logger.info(f"保存压缩图片: {compressed_img_path}")
                            
                            progress_info.append(f"  ✓ {card_type}: 1 张证卡")
                            logger.info(f"  ✓ {card_type}: 1 张证卡")
                    
                    else:
                        progress_info.append(f"  ✗ {card_type}: 未检测到证卡")
                        logger.warning(f"  ✗ {card_type}: 未检测到证卡")
                    
                    yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
                    
                except Exception as e:
                    error_msg = f"  ✗ {card_type}: 处理失败 - {str(e)}"
                    progress_info.append(error_msg)
                    logger.error(error_msg)
                    yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        
        # 如果有需要选择的卡证，提示用户
        if selection_items:
            processor.set_selection_data(selection_items)
            progress_info.append(f"\n⚠ 需要选择 {len(selection_items)} 组卡证")
            
            # 显示第一组需要选择的卡证
            first_item = selection_items[0]
            selected_indices = first_item["selected_indices"]
            checkbox_values = [f"第 {i+1} 张" for i in selected_indices]
            
            yield (
                "\n".join(progress_info), 
                None, 
                gr.update(visible=True), 
                gr.update(visible=True, value=first_item["temp_files"]),
                gr.update(choices=[f"第 {i+1} 张" for i in range(len(first_item["temp_files"]))], 
                         value=checkbox_values),
                gr.update(value=f"当前选择: {first_item['card_type']} - {first_item['url']} - {first_item['name']}")
            )
            return
        
        # 如果没有需要选择的卡证，直接生成PDF
        processed_images, image_info_list, names_list = processor.get_processed_data()
        if processed_images:
            logger.info(f"生成PDF，包含 {len(processed_images)} 张图片")
            # 按照每行先正面后背面的顺序排序
            sorted_images = sort_images_by_type(processed_images, image_info_list, names_list)
            pdf_path = generate_pdf(sorted_images, names_list, output_name)
            progress_info.append(f"\n处理完成！共处理 {len(processed_images)} 张证卡")
            logger.info(f"批量处理完成！共处理 {len(processed_images)} 张证卡，PDF保存至: {pdf_path}")
            
            yield "\n".join(progress_info), pdf_path, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        else:
            warning_msg = "\n没有成功处理的证卡"
            progress_info.append(warning_msg)
            logger.warning(warning_msg)
            yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
            
    except Exception as e:
        error_msg = f"处理失败: {str(e)}"
        logger.exception(error_msg)
        yield error_msg, None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)

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

def handle_card_selection(selected_checkboxes, current_index):
    """处理卡证选择"""
    try:
        selection_items = processor.get_selection_data()
        if not selection_items or current_index >= len(selection_items):
            return gr.update(), gr.update(), gr.update(), gr.update(), current_index
        
        current_item = selection_items[current_index]
        
        # 获取选中的索引
        selected_indices = []
        for checkbox in selected_checkboxes:
            if checkbox.startswith("第 ") and checkbox.endswith(" 张"):
                try:
                    index = int(checkbox.split(" ")[1]) - 1
                    selected_indices.append(index)
                except (ValueError, IndexError):
                    continue
        
        # 保存选择
        processor.save_selection(current_item["url"], current_item["card_type"], selected_indices)
        
        # 处理下一组
        next_index = current_index + 1
        if next_index < len(selection_items):
            next_item = selection_items[next_index]
            next_selected_indices = next_item["selected_indices"]
            next_checkbox_values = [f"第 {i+1} 张" for i in next_selected_indices]
            
            return (
                gr.update(value=next_item["temp_files"]),
                gr.update(choices=[f"第 {i+1} 张" for i in range(len(next_item["temp_files"]))], 
                         value=next_checkbox_values),
                gr.update(value=f"当前选择: {next_item['card_type']} - {next_item['url']} - {next_item['name']}"),
                gr.update(),
                next_index
            )
        else:
            # 所有选择完成，开始生成PDF
            return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(visible=True), next_index
            
    except Exception as e:
        logger.error(f"处理卡证选择失败: {e}")
        return gr.update(), gr.update(), gr.update(), gr.update(), current_index

def generate_final_pdf(output_name="output.pdf"):
    """生成最终的PDF文件"""
    try:
        selection_items = processor.get_selection_data()
        processed_images, image_info_list, names_list = processor.get_processed_data()
        
        # 处理需要选择的卡证
        for item in selection_items:
            url = item["url"]
            card_type = item["card_type"]
            name = item["name"]
            selected_indices = processor.get_selection(url, card_type)
            
            # 重新处理URL获取选择的卡证
            result = processor.model(url)
            if result and result.get("output_imgs"):
                for selected_index in selected_indices:
                    if selected_index < len(result["output_imgs"]):
                        img = result["output_imgs"][selected_index]
                        if isinstance(img, np.ndarray):
                            img = process_image_format(img)
                            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                                Image.fromarray(img).save(tmp.name)
                                compressed_img_path = compress_image(tmp.name)
                                processor.add_processed_image(compressed_img_path, card_type, item["row_index"], name)
        
        # 重新获取所有处理后的数据
        processed_images, image_info_list, names_list = processor.get_processed_data()
        
        if not processed_images:
            return "没有需要处理的卡证", None
        
        # 生成PDF
        # 按照每行先正面后背面的顺序排序
        sorted_images = sort_images_by_type(processed_images, image_info_list, names_list)
        pdf_path = generate_pdf(sorted_images, names_list, output_name)
        
        # 清理临时文件
        for img_path in processed_images:
            try:
                os.unlink(img_path)
            except:
                pass
        
        return f"处理完成！共生成 {len(processed_images)} 张卡证", pdf_path
            
    except Exception as e:
        logger.error(f"生成最终PDF失败: {e}")
        return f"处理失败: {str(e)}", None

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
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/PingFang.ttc",  # macOS
                "C:/Windows/Fonts/simhei.ttf",  # Windows
                "C:/Windows/Fonts/msyh.ttf"     # Windows
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

# 剩余的界面创建和主函数代码保持不变...

def create_interface():
    """创建Gradio界面"""
    logger.info("创建Gradio界面")
    
    custom_head = '''
    <meta property="og:type" content="https://id.sunrev.com.cn">
    <meta property="og:title" content="证卡处理工具">
    <meta property="og:description" content="一键提取图片中的卡证，矫正透视畸变，并调整方向为水平。">
    <meta property="og:image" content="https://www.sunrev.com.cn/idlogo.png">
    <link rel="shortcut icon" href="https://www.sunrev.com.cn/idlogo.png">
    '''
    
    with gr.Blocks(title="证卡处理工具", head=custom_head, theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📄 证卡图片处理工具")
        
        # 添加状态显示
        status_text = "✅ 模型已就绪" if processor.init_model() else "❌ 模型初始化失败"
        status_display = gr.Markdown(f"**系统状态:** {status_text}")
        
        # 隐藏的状态变量
        current_selection_index = gr.State(0)
        
        with gr.Tabs():
            # 单张处理
            with gr.Tab("📷 单张处理"):
                with gr.Row():
                    # 左侧：输入
                    with gr.Column(scale=1):
                        gr.Markdown("### 上传图片")
                        image_input = gr.Image(
                            label="点击或拖拽上传图片",
                            type="filepath",
                            height=300
                        )
                        format_select = gr.Radio(
                            choices=["png", "jpg"],
                            value="png",
                            label="输出格式"
                        )
                        process_btn = gr.Button("处理图片", variant="primary")
                    
                    # 右侧：输出
                    with gr.Column(scale=1):
                        gr.Markdown("### 处理结果")
                        progress_output = gr.Textbox(
                            label="处理状态",
                            lines=4
                        )
                        gallery = gr.Gallery(
                            label="提取的证卡",
                            columns=3,
                            height=300,
                            object_fit="contain"
                        )
            
            # 批量处理
            with gr.Tab("📊 批量处理"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 上传CSV")
                        csv_input = gr.File(
                            label="CSV文件",
                            file_types=[".csv"]
                        )
                        pdf_name = gr.Textbox(
                            label="PDF文件名",
                            value="cards_output.pdf"
                        )
                        batch_btn = gr.Button("批量处理", variant="primary")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("### 处理进度")
                        batch_progress = gr.Textbox(
                            label="状态",
                            lines=10
                        )
                        pdf_output = gr.File(
                            label="下载PDF",
                            file_count="single"
                        )
                
                # 卡证选择界面（初始隐藏）
                with gr.Row(visible=False) as selection_row:
                    with gr.Column():
                        gr.Markdown("### 🎯 请选择卡证")
                        selection_info = gr.Markdown("")
                        selection_gallery = gr.Gallery(
                            label="检测到的卡证（点击可查看大图）",
                            columns=4,
                            height=200
                        )
                        selection_checkbox = gr.CheckboxGroup(
                            choices=[],
                            label="选择要使用的卡证（可多选）"
                        )
                        confirm_selection_btn = gr.Button("确认选择", variant="primary")
                
                # 生成PDF按钮（初始隐藏）
                with gr.Row(visible=False) as generate_pdf_row:
                    with gr.Column():
                        generate_pdf_btn = gr.Button("生成PDF", variant="primary")
            
            # 使用说明
            with gr.Accordion("📋 使用说明", open=False):
                gr.Markdown("""
                **单张处理：** 上传图片，自动检测并提取所有证卡  
                **批量处理：** CSV格式：姓名,正面URL,背面URL  
                **注意：** 
                - 处理过程中请勿关闭页面
                - 如果一张图片中包含多张卡证，系统会提示您选择要使用的卡证
                - 您的选择会被缓存，下次处理相同URL时会自动使用之前的选择
                - PDF输出将在每张图片下方显示序号和姓名
                """)
        
        # 事件绑定
        process_btn.click(
            fn=process_single_image,
            inputs=[image_input, format_select],
            outputs=[progress_output, gallery, pdf_output]
        )
        
        batch_btn.click(
            fn=process_batch_images,
            inputs=[csv_input, pdf_name],
            outputs=[batch_progress, pdf_output, selection_row, selection_gallery, selection_checkbox, selection_info]
        )
        
        # 选择确认事件
        confirm_selection_btn.click(
            fn=handle_card_selection,
            inputs=[selection_checkbox, current_selection_index],
            outputs=[selection_gallery, selection_checkbox, selection_info, generate_pdf_row, current_selection_index]
        )
        
        # 生成PDF事件
        generate_pdf_btn.click(
            fn=generate_final_pdf,
            inputs=[pdf_name],
            outputs=[batch_progress, pdf_output]
        )
    
    return demo

if __name__ == "__main__":
    print("=" * 50)
    print("启动证卡处理工具...")
    print("=" * 50)
    
    # 尝试初始化模型
    print("正在初始化模型...")
    if processor.init_model():
        print("✅ 模型初始化成功")
    else:
        print("❌ 模型初始化失败")
        print("请检查：")
        print("1. modelscope 是否正确安装")
        print("2. 网络连接是否正常")
        print("3. 模型路径是否正确")
    
    print("启动Gradio界面...")
    demo = create_interface()
    
    # 添加启动信息
    print("✅ 应用启动成功")
    print("🌐 本地访问: http://localhost:8080")
    print("🛑 按 Ctrl+C 停止服务")
    print("=" * 50)
    
    try:
        demo.launch(
            server_name="0.0.0.0",
            server_port=8080,
            share=False,
            show_error=True,
            root_path="/gr"
        )
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        print("请检查端口8080是否被占用")
```

最新软件版本见项目说明。
