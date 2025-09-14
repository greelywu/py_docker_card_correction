# 配置和常量
import os
import tempfile

# 设置临时文件夹
TEMP_DIR = "/home/tmp"
os.makedirs(TEMP_DIR, exist_ok=True)
tempfile.tempdir = TEMP_DIR

# 缓存目录
CACHE_DIR = "/home/file"
os.makedirs(CACHE_DIR, exist_ok=True)