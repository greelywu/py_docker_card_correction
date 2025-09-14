# 批量处理功能
from PIL import Image
import gradio as gr
import logging
import pandas as pd
import numpy as np
import pymysql
import tempfile
import os

from card_processor import processor
from image_utils import compress_image, numpy_to_temp_file
from pdf_generator import generate_pdf, sort_images_by_type
from image_utils import process_image_format

logger = logging.getLogger(__name__)

# 添加数据库查询函数
def query_database_to_csv():
    """从MySQL数据库查询数据并生成CSV文件"""
    try:
        # 连接数据库
        connection = pymysql.connect(
            host='',
            database='',
            port=,
            user='',
            password='',
            charset=''
        )
        
        logger.info("数据库连接成功")
        
        # 执行SQL查询
        sql = """
        SELECT 
            zhp.household_user_name AS '户主',
            REPLACE(CONCAT(COALESCE(zhwa.front_img_url, ''), COALESCE(zhdcu.front_img_url, '')), ' ', '') AS id_card_front,
            REPLACE(CONCAT(COALESCE(zhwa.back_img_url, ''), COALESCE(zhdcu.back_img_url, '')), ' ', '') AS id_card_back
        FROM zy_household_project zhp 
        LEFT JOIN zy_household_user zhu ON zhu.id = zhp.household_user_id 
        LEFT JOIN zy_household_wallet_account zhwa ON zhwa.project_id = zhp.id 
        LEFT JOIN zy_household_debit_card_upload zhdcu ON zhdcu.id = (
            SELECT MAX(zhdcud.id)
            FROM zy_household_debit_card_upload zhdcud
            WHERE zhdcud.project_id = zhp.id 
        )
        WHERE zhp.project_status = 2
        ORDER BY (
            SELECT 序号 FROM (
                SELECT 
                    ROW_NUMBER() OVER () AS '序号',
                    zhp_inner.id AS project_id
                FROM zy_household_project zhp_inner
                LEFT JOIN zy_household_project_design_device zhpdd_inner ON zhp_inner.id = zhpdd_inner.project_id 
                WHERE zhp_inner.project_status = 2 
                  AND zhpdd_inner.material_type = '组件'
                GROUP BY zhp_inner.id
            ) AS order_subquery
            WHERE order_subquery.project_id = zhp.id
        )
        """
        
        # 读取数据到DataFrame
        df = pd.read_sql(sql, connection)
        
        # 关闭数据库连接
        connection.close()
        
        logger.info(f"查询成功，获取到 {len(df)} 条记录")
        
        # 创建临时CSV文件
        temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        
        # 写入CSV文件（不包含表头）
        df.to_csv(temp_csv.name, index=False, header=False)
        temp_csv.close()
        
        logger.info(f"CSV文件已生成: {temp_csv.name}")
        
        return temp_csv.name, f"成功获取 {len(df)} 条记录"
        
    except Exception as e:
        logger.error(f"数据库查询失败: {e}")
        return None, f"数据库查询失败: {str(e)}"

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
                    
                    # 检查缓存中是否已有处理好的图片
                    # 在batch_processing.py中修改process_batch_images函数的相关部分

                    # 检查缓存中是否已有处理好的图片
                    cache_path = processor.check_cache(url)
                    if cache_path:
                        # 使用缓存中的图片（直接使用缓存路径，不生成临时文件）
                        progress_info.append(f"  ✓ {card_type}: 使用缓存图片")
                        logger.info(f"使用缓存图片: {cache_path}")
                        # 直接使用缓存图片路径，不进行额外压缩
                        processor.add_processed_image(cache_path, card_type, i, name)
                        yield "\n".join(progress_info), None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
                        continue
                    
                    # 没有缓存，调用模型处理
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
                                    # 保存到缓存
                                    cache_path = processor.save_to_cache(img, url)
                                    # 压缩图片用于显示和PDF生成
                                    compressed_img_path = compress_image(cache_path)
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
            
            # 检查缓存中是否已有处理好的图片
            cache_path = processor.check_cache(url)
            if cache_path:
                # 使用缓存中的图片
                processor.add_processed_image(cache_path, card_type, item["row_index"], name)
                continue
            
            # 没有缓存，重新处理URL获取选择的卡证
            result = processor.model(url)
            if result and result.get("output_imgs"):
                for selected_index in selected_indices:
                    if selected_index < len(result["output_imgs"]):
                        img = result["output_imgs"][selected_index]
                        if isinstance(img, np.ndarray):
                            img = process_image_format(img)
                            # 保存到缓存
                            cache_path = processor.save_to_cache(img, url)
                            compressed_img_path = compress_image(cache_path)
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