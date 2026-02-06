#!/usr/bin/env python
"""
Celery 启动脚本 - 在启动 Celery 前初始化 Django
"""
import os
import sys

# 设置 Django 设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.base')
os.environ.setdefault('REVIEW_AGENT_ENV', 'development')

# 添加项目路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# 初始化 Django
import django
django.setup()

# 启动 Celery
if __name__ == '__main__':
    from celery.bin import celery
    celery.main()
