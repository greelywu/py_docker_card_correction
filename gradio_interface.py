# 在文件开头添加导入
import gradio as gr
import logging
import tempfile
import os

from card_processor import processor
from single_image_processing import process_single_image
from batch_processing import process_batch_images, handle_card_selection, generate_final_pdf, query_database_to_csv

logger = logging.getLogger(__name__)

# 在create_interface函数中添加数据库查询部分
def create_interface():
    """创建Gradio界面"""
    logger.info("创建Gradio界面")
    
    with gr.Blocks(title="证卡处理工具", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 📄 证卡图片处理工具")
        
        # 添加状态显示
        status_text = "✅ 模型已就绪" if processor.init_model() else "❌ 模型初始化失败"
        
        # 隐藏的状态变量
        current_selection_index = gr.State(0)
        db_csv_path = gr.State(None)  # 存储数据库查询生成的CSV文件路径
        
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
                        gr.Markdown("### 上传CSV或从数据库获取")
                        
                        # 数据库查询部分
                        with gr.Row():
                            db_query_btn = gr.Button("从数据库获取数据", variant="secondary")
                            db_status = gr.Textbox(
                                label="数据库状态",
                                value="点击按钮从数据库获取数据",
                                interactive=False
                            )
                        
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
                **数据库获取：** 直接从MySQL数据库获取需要处理的数据  
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
        
        # 添加数据库查询事件
        db_query_btn.click(
            fn=query_database_to_csv,
            outputs=[db_csv_path, db_status]
        )
        
        # 当数据库查询完成后，更新CSV文件输入
        def update_csv_input(csv_path):
            if csv_path and os.path.exists(csv_path):
                return gr.update(value=csv_path)
            return gr.update()
        
        db_csv_path.change(
            fn=update_csv_input,
            inputs=db_csv_path,
            outputs=csv_input
        )
    
    return demo