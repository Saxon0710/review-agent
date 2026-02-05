"""
创建默认管理员用户
开发环境用，生产环境请修改密码
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '创建默认管理员用户'

    def handle(self, *args, **options):
        username = 'admin'
        password = 'admin123'
        email = 'admin@example.com'

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(
                self.style.SUCCESS(f'✓ 默认管理员已创建\n  用户名: {username}\n  密码: {password}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'✓ 用户 {username} 已存在，跳过创建')
            )
