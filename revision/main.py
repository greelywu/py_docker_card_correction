import gradio as gr
import logging
import os
import tempfile
from datetime import datetime

from card_processor import processor
from batch_processing import process_batch_images, query_database_to_csv
from config import CACHE_DIR

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # 创建界面
    with gr.Blocks(title="证卡处理工具") as demo:
        gr.Markdown("# 证卡处理工具")
        
        with gr.Tab("批量处理"):
            with gr.Row():
                with gr.Column():
                    csv_input = gr.File(label="上传CSV文件", file_types=[".csv"])
                    db_query_btn = gr.Button("从数据库生成CSV")
                    output_name = gr.Textbox(label="输出PDF文件名", value=f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                    process_btn = gr.Button("开始处理", variant="primary")
                
                with gr.Column():
                    progress_output = gr.Textbox(label="处理进度", lines=15, interactive=False)
                    pdf_output = gr.File(label="生成PDF", visible=False)
            
            # 选择界面组件（初始隐藏）
            selection_gallery = gr.Gallery(label="请选择正确的证卡", visible=False, columns=3, height=400)
            selection_checkbox = gr.CheckboxGroup(label="选择图片", visible=False, interactive=True)
            selection_info = gr.Textbox(label="选择信息", visible=False)
            confirm_selection_btn = gr.Button("确认选择", visible=False)
        
        # 事件处理
        db_query_btn.click(
            fn=query_database_to_csv,
            outputs=[csv_input, progress_output]
        )
        
        process_btn.click(
            fn=process_batch_images,
            inputs=[csv_input, output_name],
            outputs=[progress_output, pdf_output, confirm_selection_btn, selection_gallery, selection_checkbox, selection_info]
        )
        
        confirm_selection_btn.click(
            fn=confirm_selection,
            inputs=[selection_checkbox],
            outputs=[progress_output, pdf_output, confirm_selection_btn, selection_gallery, selection_checkbox, selection_info]
        )
    
    # 启动应用
    demo.launch(server_name="0.0.0.0", server_port=8080)

def confirm_selection(selected_items):
    """确认用户选择"""
    try:
        selection_data = processor.get_selection_data()
        if not selection_data:
            return "没有选择数据", None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)
        
        current_item = selection_data[0]
        selected_indices = [int(item.split(" ")[1]) - 1 for item in selected_items]
        
        # 保存用户选择
        processor.save_selection(current_item["url"], current_item["card_type"], selected_indices)
        
        # 处理选择的图片
        for idx in selected_indices:
            if idx < len(current_item["temp_files"]):
                temp_file = current_item["temp_files"][idx]
                
                # 读取图片并保存到缓存
                try:
                    img = Image.open(temp_file)
                    img_array = np.array(img)
                    
                    # 保存到缓存
                    cache_path = processor.save_image(img_array, current_item["url"])
                    if cache_path:
                        # 压缩图片用于PDF生成
                        from image_utils import compress_image
                        compressed_path = compress_image(cache_path)
                        processor.add_processed_image(compressed_path, current_item["card_type"], 
                                                     current_item["row_index"], current_item["name"])
                except Exception as e:
                    logger.error(f"处理选择图片失败: {e}")
        
        # 移除已处理的项
        selection_data.pop(0)
        processor.set_selection_data(selection_data)
        
        # 如果还有需要选择的项，显示下一项
        if selection_data:
            next_item = selection_data[0]
            selected_indices = next_item["selected_indices"]
            checkbox_values = [f"第 {i+1} 张" for i in selected_indices]
            
            return (
                f"已保存选择，还有 {len(selection_data)} 组需要选择",
                None,
                gr.update(visible=True),
                gr.update(visible=True, value=next_item["temp_files"]),
                gr.update(choices=[f"第 {i+1} 张" for i in range(len(next_item["temp_files"]))], 
                         value=checkbox_values),
                gr.update(value=f"当前选择: {next_item['card_type']} - {next_item['url']} - {next_item['name']}")
            )
        else:
            # 所有选择完成，生成PDF
            processed_images, image_info_list, names_list = processor.get_processed_data()
            if processed_images:
                logger.info(f"生成PDF，包含 {len(processed_images)} 张图片")
                from pdf_generator import sort_images_by_type, generate_pdf
                sorted_images = sort_images_by_type(processed_images, image_info_list, names_list)
                pdf_path = generate_pdf(sorted_images, names_list, "output.pdf")
                
                # 清理临时文件（保留缓存文件）
                processor.cleanup_all_temp_files()
                
                return (
                    f"所有选择完成！生成PDF: {pdf_path}",
                    pdf_path,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(value=[]),
                    gr.update(visible=False)
                )
            else:
                return (
                    "处理完成，但未生成任何图片",
                    None,
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(value=[]),
                    gr.update(visible=False)
                )
                
    except Exception as e:
        error_msg = f"确认选择失败: {str(e)}"
        logger.error(error_msg)
        return error_msg, None, gr.update(visible=False), gr.update(visible=False), gr.update(value=[]), gr.update(visible=False)

if __name__ == "__main__":
    main()