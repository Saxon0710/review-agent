"""常量定义"""


class ReviewType:
    """审查类型"""
    REVIEW = "review"
    DESCRIBE = "describe"
    IMPROVE = "improve"
    QUESTION = "question"
    UPDATE_CHANGELOG = "update_changelog"
    GENERATE_LABELS = "generate_labels"
    ADD_DOCS = "add_docs"


class TaskStatus:
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MRState:
    """MR 状态"""
    OPENED = "opened"
    CLOSED = "closed"
    MERGED = "merged"
    LOCKED = "locked"


class TriggerType:
    """触发类型"""
    WEBHOOK = "webhook"
    MANUAL = "manual"
    SCHEDULE = "schedule"


# GitLab Webhook 事件类型
GITLAB_WEBHOOK_EVENTS = [
    "merge_request",  # MR 事件
    "note",           # 评论事件
    "push",           # 推送事件
]

# GitLab MR 动作
GITLAB_MR_ACTIONS = [
    "open",           # 打开
    "close",          # 关闭
    "reopen",         # 重新打开
    "merge",          # 合并
    "update",         # 更新
    "approved",       # 批准
    "unapproved",     # 取消批准
]

# 支持的命令格式
SUPPORTED_COMMANDS = [
    "/review",
    "/describe",
    "/improve",
    "/ask",
    "/update_changelog",
    "/generate_labels",
    "/add_docs",
    "/test",
    "/help",
    "/config",
]

# 审查评分等级
SCORE_GRADES = {
    1: "严重问题",
    2: "严重问题",
    3: "需要改进",
    4: "需要改进",
    5: "一般",
    6: "一般",
    7: "良好",
    8: "良好",
    9: "优秀",
    10: "完美",
}

# 工作量估算
EFFORT_ESTIMATES = {
    "small": "小 (< 1 小时)",
    "medium": "中 (1-4 小时)",
    "large": "大 (4-8 小时)",
    "x-large": "超大 (> 8 小时)",
}

# 问题严重程度
ISSUE_SEVERITY = {
    "critical": "严重",
    "major": "重要",
    "minor": "次要",
    "suggestion": "建议",
}

# 常见编程语言 (用于文件扩展名映射)
LANGUAGE_EXTENSIONS = {
    "Python": [".py", ".pyi", ".pyx", ".pyw"],
    "JavaScript": [".js", ".jsx", ".mjs", ".cjs"],
    "TypeScript": [".ts", ".tsx"],
    "Java": [".java"],
    "C#": [".cs", ".cake", ".cshtml", ".csx"],
    "C++": [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h"],
    "Go": [".go"],
    "Rust": [".rs"],
    "Ruby": [".rb"],
    "PHP": [".php"],
    "Swift": [".swift"],
    "Kotlin": [".kt", ".kts"],
    "Scala": [".scala"],
    "HTML": [".html", ".htm"],
    "CSS": [".css", ".scss", ".sass", ".less"],
    "Shell": [".sh", ".bash", ".zsh"],
    "SQL": [".sql"],
    "YAML": [".yaml", ".yml"],
    "JSON": [".json"],
    "Markdown": [".md", ".markdown"],
}

# 忽略的文件/目录模式
DEFAULT_IGNORE_PATTERNS = [
    "*.min.js",
    "*.min.css",
    "*.map",
    "node_modules/**",
    "vendor/**",
    ".git/**",
    "dist/**",
    "build/**",
    "*.egg-info/**",
    "__pycache__/**",
    "*.pyc",
]

# 默认配置值
DEFAULT_CONFIG = {
    "auto_review_on_open": False,
    "auto_review_commands": ["/describe", "/review"],
    "ignore_draft": True,
    "review_max_findings": 3,
    "ai_model": "gpt-4o",
    "ai_temperature": 0.2,
}
