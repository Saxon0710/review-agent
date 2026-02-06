"""
Celery 应用入口 - 在启动前初始化 Django
"""
import os
import sys

# 设置 Django 设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.base')
os.environ.setdefault('REVIEW_AGENT_ENV', 'development')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 初始化 Django
import django
django.setup()

# 启动 Celery
from celery import bin

if __name__ == '__main__':
    # 获取命令行参数并传递给 celery
    from celery.__main__ import main
    main()
