# Review Agent

基于 PR-Agent 核心功能的代码审查系统，专注于 GitLab 平台。

## 功能特性

- **代码审查** (/review) - 自动分析 MR 代码质量，提供详细审查意见
- **PR 描述** (/describe) - 自动生成 MR 描述摘要
- **代码改进** (/improve) - 提供具体的代码改进建议
- **智能问答** (/ask) - 针对代码进行问答交互

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Nginx (80/443)                          │
├──────────────────────────────┬──────────────────────────────────┤
│         Django (8000)        │         FastAPI (8001)           │
│  ────────────────────────   │  ──────────────────────────────  │
│  · Web UI (Bootstrap 5)     │  · GitLab Webhook 接收           │
│  · 用户管理                  │  · RESTful API                   │
│  · 项目/PR/审查管理          │  · AI 审查服务                   │
│  · 配置管理                  │  · 异步任务处理                  │
├──────────────────────────────┴──────────────────────────────────┤
│                       PostgreSQL + Redis                         │
│                    (数据持久化 + 消息队列)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌──────────────────┐
                    │   Celery Worker  │
                    │   (后台任务处理)  │
                    └──────────────────┘
```

## 快速开始

### 使用 Docker Compose (推荐)

1. **克隆项目**
   ```bash
   git clone https://github.com/your-org/review-agent.git
   cd review-agent
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，设置必要的配置
   ```

3. **启动服务**
   ```bash
   docker-compose up -d
   ```

4. **运行数据库迁移**
   ```bash
   docker-compose exec django python manage.py migrate
   ```

5. **创建超级用户**
   ```bash
   docker-compose exec django python manage.py createsuperuser
   ```

6. **访问服务**
   - Web UI: http://localhost
   - API 文档: http://localhost/api/docs
   - Admin 后台: http://localhost/admin

### 本地开发

1. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境变量**
   ```bash
   cp .env.example .env
   # 编辑 .env 文件
   ```

3. **运行数据库**
   ```bash
   # 使用 Docker 运行 PostgreSQL 和 Redis
   docker-compose up -d postgres redis
   ```

4. **运行 Django**
   ```bash
   cd backend
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
   ```

5. **运行 FastAPI**
   ```bash
   cd backend
   uvicorn api.main:app --reload --port 8001
   ```

6. **运行 Celery**
   ```bash
   cd backend
   celery -A integration.tasks worker --loglevel=info
   ```

## 配置说明

### GitLab 配置

1. 生成 GitLab Personal Access Token:
   - 权限: `api`, `read_repository`, `read_api`

2. 设置环境变量:
   ```bash
   GITLAB_URL=https://gitlab.com
   GITLAB_ACCESS_TOKEN=your-token
   ```

3. 配置 Webhook:
   - URL: `http://your-domain/api/v1/webhook/gitlab`
   - Secret: 设置随机字符串
   - 事件: Merge request events, Comment events

### AI 配置

支持多种 AI 提供商:

```bash
# OpenAI
AI_PROVIDER=openai
AI_MODEL=gpt-4o
AI_API_KEY=sk-...

# Anthropic Claude
AI_PROVIDER=anthropic
AI_MODEL=claude-3-opus-20240229
AI_API_KEY=sk-ant-...

# LiteLLM (多提供商统一接口)
AI_PROVIDER=litellm
AI_MODEL=gpt-4o
AI_API_KEY=your-key
```

## 使用指南

### Web 界面

1. **添加项目**
   - 访问 Admin 后台 (`/admin/core/gitlabproject/add/`)
   - 输入 GitLab 项目路径

2. **配置审查规则**
   - 进入项目详情页
   - 在"配置"标签页设置自动审查规则

3. **查看审查结果**
   - 项目详情 → MR 列表 → 选择 MR
   - 或访问审查任务列表

### GitLab 命令

在 MR 评论中使用以下命令:

| 命令 | 描述 |
|------|------|
| `/review` | 执行代码审查 |
| `/describe` | 生成 PR 描述 |
| `/improve` | 提供改进建议 |
| `/ask <问题>` | 提问相关代码 |

### API 接口

FastAPI 提供以下接口:

- `POST /api/v1/webhook/gitlab` - 接收 GitLab Webhook
- `POST /api/v1/review/start` - 手动触发审查
- `GET /api/v1/review/task/{task_id}` - 查询任务状态
- `POST /api/v1/review/task/{task_id}/cancel` - 取消任务

API 文档: http://localhost/api/docs

## 项目结构

```
review-agent/
├── backend/
│   ├── manage.py              # Django 管理入口
│   ├── settings/              # Django 配置
│   ├── config/                # Dynaconf 配置系统
│   │   ├── settings.py        # 配置加载器
│   │   ├── defaults.yaml      # 默认配置
│   │   └── secrets.yaml       # 密钥配置
│   ├── core/                  # 核心模型
│   │   ├── models.py          # 数据模型
│   │   └── admin.py           # Django Admin
│   ├── api/                   # FastAPI 应用
│   │   ├── main.py            # FastAPI 入口
│   │   └── routers/           # API 路由
│   ├── review/                # 审查引擎
│   │   ├── providers/         # Git 平台适配
│   │   ├── tools/             # 审查工具
│   │   └── ai/                # AI 服务
│   ├── integration/           # 集成模块
│   │   ├── gitlab/            # GitLab 集成
│   │   └── tasks/             # Celery 任务
│   ├── web/                   # Django Web 应用
│   │   ├── views/             # 视图
│   │   └── templates/         # 模板
│   └── utils/                 # 工具模块
├── docker/                    # Docker 配置
│   ├── docker-compose.yml
│   ├── Dockerfile.django
│   ├── Dockerfile.fastapi
│   └── nginx.conf
├── requirements.txt           # Python 依赖
├── .env.example              # 环境变量模板
└── README.md
```

## 开发指南

### 添加新的审查工具

1. 在 `backend/review/tools/` 创建新工具类
2. 继承 `BaseReviewTool`
3. 实现 `run()` 方法
4. 在 `backend/review/tools/__init__.py` 中注册

### 添加新的 Git 平台支持

1. 在 `backend/review/providers/` 创建新的 Provider
2. 继承 `GitProvider` 基类
3. 实现所有抽象方法
4. 在 FastAPI 中添加对应的 Webhook 处理

## 许可证

MIT License

## 致谢

本项目基于 [PR-Agent](https://github.com/Codium-ai/pr-agent) 的核心功能开发。
