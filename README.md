# 证卡处理工具 - 部署使用说明（ModelScope 模型下载到本地Docker 容器）

## 环境搭建

### 启动Docker容器
```bash
# 下载官方镜像
docker pull modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-py311-torch2.3.1-1.29.0

# 运行容器（将/path/to/your/workspace替换为实际工作目录）
docker run -it --volume=/path/to/your/workspace:/home -p 8080:8080 --name modelscope-container modelscope-registry.cn-beijing.cr.aliyuncs.com/modelscope-repo/modelscope:ubuntu22.04-py311-torch2.3.1-1.29.0 /bin/bash
```

### 进入Docker容器
如果容器已在后台运行，使用以下命令进入：
```bash
# 查看运行中的容器
docker ps

# 进入容器（使用容器名称或ID）
docker exec -it modelscope-container /bin/bash
```

### 安装依赖和下载模型
在Docker容器内执行：
```bash
# 安装所需依赖包
pip install modelscope gradio opencv-python pillow pandas reportlab numpy

# 下载证卡校正模型（重要步骤）
modelscope download --model iic/cv_resnet18_card_correction
# 进入工作目录
cd /home

#克隆项目
git clone https://github.com/greelywu/py_docker_card_correction.git
cd py_docker_card_correction

# 运行证卡处理工具
python main.py
```

### 访问应用
程序启动后，通过浏览器访问：
```
http://localhost:8080
```

## 核心功能

1. **单张图片处理**
   - 上传单张图片进行卡证检测和校正
   - 支持多种输出格式（PNG/JPG）
   - 实时显示处理结果和提取的证卡

2. **批量处理**
   - 支持上传CSV文件进行批量处理
   - 提供数据库查询功能，直接从MySQL数据库获取数据
   - 自动处理大量证卡图片并生成PDF

3. **智能选择功能**
   - 当一张图片中包含多张卡证时，提供用户选择界面
   - 用户选择结果会被缓存，提高后续处理效率

4. **PDF生成**
   - 自动将处理后的证卡图片排版生成PDF
   - 每张图片下方标注序号和姓名信息
   - 支持中文字体显示

## 技术架构

### 主要技术栈

- **后端框架**: Python
- **深度学习模型**: ModelScope卡证检测校正模型
- **Web界面**: Gradio
- **数据库**: MySQL (通过pymysql连接)
- **图像处理**: PIL, OpenCV, NumPy
- **PDF生成**: ReportLab

### 项目结构

```
project/
├── main.py              # 主程序入口
├── card_processor.py    # CardProcessor类 - 核心模型处理
├── image_utils.py       # 图像处理工具函数
├── batch_processing.py  # 批量处理功能
├── pdf_generator.py     # PDF生成功能
├── gradio_interface.py  # Gradio界面
├── single_image_processing.py # 单张图片处理
└── config.py           # 配置和常量
```

### 数据库配置

在`batch_processing.py`中修改数据库连接参数:

```python
connection = pymysql.connect(
    host='',        # 数据库服务器地址
    database='', # 数据库名
    port=,                 # 端口
    user='',           # 用户名
    password='', # 密码
    charset=''          # 字符集
)
```

## 使用说明

### 单张处理

1. 在"单张处理"标签页上传图片
2. 选择输出格式（PNG/JPG）
3. 点击"处理图片"按钮
4. 查看处理结果和提取的证卡

### 批量处理

1. 在"批量处理"标签页:
   - 点击"从数据库获取数据"按钮直接从数据库查询
   - 或上传CSV文件（格式: 姓名,正面URL,背面URL）
2. 设置PDF文件名
3. 点击"批量处理"按钮
4. 如有需要，在出现的选择界面中选择要使用的卡证
5. 处理完成后下载生成的PDF文件

### CSV文件格式

CSV文件应包含以下列（无表头）:

```
姓名,正面图片URL,背面图片URL
张三,http://example.com/front1.jpg,http://example.com/back1.jpg
李四,http://example.com/front2.jpg,http://example.com/back2.jpg
```

## 特色功能

1. **智能缓存系统**
   - 处理过的图片会缓存到本地，提高后续处理速度
   - 基于URL的缓存键，确保相同图片只处理一次

2. **用户选择记忆**
   - 用户对多卡证图片的选择结果会被保存
   - 下次处理相同图片时自动应用之前的选择

3. **图像优化处理**
   - 自动处理图像格式和颜色空间转换
   - 支持多种图像格式（JPG, PNG, BMP, TIFF, WebP）

4. **PDF智能排版**
   - 自动按行索引和正反面顺序排序图片
   - 每页4行2列的整齐布局
   - 支持中文字体显示姓名信息

## 注意事项

1. 首次运行时会下载模型文件，需要网络连接
2. 数据库功能需要正确配置连接参数
3. 处理大量图片时需要足够的内存和存储空间
4. 中文字体显示需要系统安装相应字体文件

## 故障排除

1. **模型初始化失败**: 检查网络连接和modelscope安装
2. **数据库连接失败**: 检查数据库配置参数
3. **中文显示问题**: 检查系统中文字体安装
4. **内存不足**: 减少批量处理的数量或增加系统内存

这个工具特别适合需要批量处理身份证、银行卡等证卡图片的场景，如金融、政务、企业人事等领域的自动化处理需求。
