# 主程序入口
import logging

from card_processor import processor
from gradio_interface import create_interface

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
        
# 在main.py中添加提示
if __name__ == "__main__":
    print("=" * 50)
    print("启动证卡处理工具...")
    print("=" * 50)
    
    # 检查pymysql是否安装
    try:
        import pymysql
        print("✅ pymysql 已安装")
    except ImportError:
        print("❌ pymysql 未安装，数据库功能将不可用")
        print("请运行: pip install pymysql")
    
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