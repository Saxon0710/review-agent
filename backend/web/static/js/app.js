/**
 * Review Agent - 全局交互逻辑
 * 功能：标签页管理、侧边栏折叠、面包屑导航
 */

(function() {
    'use strict';

    // ==================== 配置 ====================
    const CONFIG = {
        storageKey: 'review_agent_ui_state',
        maxTabs: 20
    };

    // ==================== 菜单配置 ====================
    const MENU_ITEMS = [
        { title: '仪表板', url: '/', icon: 'bi-speedometer2', closable: false },
        { title: '项目列表', url: '/projects/', icon: 'bi-folder', closable: true },
        { title: '审查任务', url: '/reviews/', icon: 'bi-file-earmark-check', closable: true }
    ];

    // ==================== 状态管理 ====================
    let state = {
        tabs: [],
        activeTab: null,
        sidebarCollapsed: false
    };

    // ==================== DOM 元素 ====================
    let elements = {};

    // ==================== 工具函数 ====================
    function $(selector) {
        return document.querySelector(selector);
    }

    function initElements() {
        elements = {
            sidebar: $('.sidebar-container'),
            sidebarToggle: $('#sidebarToggle'),
            tagsList: $('#tagsList'),
            refreshBtn: $('#refreshTag'),
            closeAllBtn: $('#closeAllTags'),
            overlay: $('.sidebar-overlay'),
            breadcrumb: $('.breadcrumb')
        };
    }

    // ==================== 本地存储 ====================
    function loadState() {
        try {
            const saved = localStorage.getItem(CONFIG.storageKey);
            if (saved) {
                const parsed = JSON.parse(saved);
                state.tabs = parsed.tabs || [];
                state.activeTab = parsed.activeTab || null;
                state.sidebarCollapsed = parsed.sidebarCollapsed || false;
            }
        } catch (e) {
            console.warn('Failed to load state:', e);
        }

        // 如果没有标签页，初始化仪表板
        if (state.tabs.length === 0) {
            const dashboardTab = { ...MENU_ITEMS[0], active: true };
            state.tabs.push(dashboardTab);
            state.activeTab = dashboardTab.url;
        }
    }

    function saveState() {
        try {
            localStorage.setItem(CONFIG.storageKey, JSON.stringify({
                tabs: state.tabs,
                activeTab: state.activeTab,
                sidebarCollapsed: state.sidebarCollapsed
            }));
        } catch (e) {
            console.warn('Failed to save state:', e);
        }
    }

    // ==================== 标签页管理器 ====================
    const TabManager = {
        // 打开标签页
        openTab(title, url, icon = 'bi-file-text', closable = true) {
            // 检查是否已存在
            const existingTab = state.tabs.find(tab => tab.url === url);
            if (existingTab) {
                this.switchTab(url);
                return;
            }

            // 限制标签数量
            if (state.tabs.length >= CONFIG.maxTabs) {
                // 关闭最旧的的可关闭标签
                const closableTab = state.tabs.find(tab => tab.closable);
                if (closableTab) {
                    this.closeTab(closableTab.url);
                }
            }

            // 添加新标签
            const newTab = { title, url, icon, closable, active: false };
            state.tabs.push(newTab);
            this.switchTab(url);
        },

        // 切换标签页
        switchTab(url) {
            // 更新激活状态
            state.tabs.forEach(tab => {
                tab.active = tab.url === url;
            });
            state.activeTab = url;

            this.render();
            saveState();

            // 如果不是当前页面，则导航
            if (window.location.pathname !== url) {
                window.location.href = url;
            }
        },

        // 关闭标签页
        closeTab(url) {
            const index = state.tabs.findIndex(tab => tab.url === url);
            if (index === -1) return;

            const tab = state.tabs[index];
            if (!tab.closable) return;

            state.tabs.splice(index, 1);

            // 如果关闭的是当前激活的标签，切换到相邻标签
            if (tab.active && state.tabs.length > 0) {
                const newIndex = Math.min(index, state.tabs.length - 1);
                const newTab = state.tabs[newIndex];
                newTab.active = true;
                state.activeTab = newTab.url;

                // 跳转到新标签页面
                if (window.location.pathname === url) {
                    window.location.href = newTab.url;
                }
            }

            this.render();
            saveState();
        },

        // 关闭所有标签（除不可关闭的）
        closeAllTabs() {
            state.tabs = state.tabs.filter(tab => !tab.closable);
            if (state.tabs.length > 0 && !state.tabs.some(tab => tab.active)) {
                state.tabs[0].active = true;
                state.activeTab = state.tabs[0].url;
            }
            this.render();
            saveState();
        },

        // 关闭其他标签
        closeOtherTabs(url) {
            state.tabs = state.tabs.filter(tab => !tab.closable || tab.url === url);
            state.tabs.forEach(tab => {
                tab.active = tab.url === url;
            });
            state.activeTab = url;
            this.render();
            saveState();
        },

        // 获取当前激活标签
        getActiveTab() {
            return state.tabs.find(tab => tab.active);
        },

        // 渲染标签页
        render() {
            if (!elements.tagsList) return;

            elements.tagsList.innerHTML = state.tabs.map(tab => `
                <div class="tag-item ${tab.active ? 'active' : ''}" data-url="${tab.url}">
                    <i class="bi ${tab.icon}"></i>
                    <span>${tab.title}</span>
                    ${tab.closable ? `<span class="tag-close" data-close="${tab.url}"><i class="bi bi-x"></i></span>` : ''}
                </div>
            `).join('');

            // 绑定事件
            this.bindEvents();
        },

        // 绑定标签页事件
        bindEvents() {
            elements.tagsList.querySelectorAll('.tag-item').forEach(item => {
                const url = item.dataset.url;

                // 点击切换
                item.addEventListener('click', (e) => {
                    if (!e.target.closest('.tag-close')) {
                        this.switchTab(url);
                    }
                });

                // 关闭按钮
                const closeBtn = item.querySelector('.tag-close');
                if (closeBtn) {
                    closeBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.closeTab(url);
                    });
                }
            });
        }
    };

    // ==================== 侧边栏管理器 ====================
    const Sidebar = {
        init() {
            // 恢复折叠状态
            if (state.sidebarCollapsed) {
                this.collapse();
            }

            // 绑定切换事件
            if (elements.sidebarToggle) {
                elements.sidebarToggle.addEventListener('click', () => this.toggle());
            }
        },

        toggle() {
            if (elements.sidebar && elements.sidebar.classList.contains('collapsed')) {
                this.expand();
            } else {
                this.collapse();
            }
        },

        collapse() {
            if (elements.sidebar) {
                elements.sidebar.classList.add('collapsed');
            }
            state.sidebarCollapsed = true;
            saveState();
        },

        expand() {
            if (elements.sidebar) {
                elements.sidebar.classList.remove('collapsed');
            }
            state.sidebarCollapsed = false;
            saveState();
        },

        // 移动端打开
        openMobile() {
            if (elements.sidebar) {
                elements.sidebar.classList.add('mobile-open');
            }
            if (elements.overlay) {
                elements.overlay.classList.add('show');
            }
        },

        // 移动端关闭
        closeMobile() {
            if (elements.sidebar) {
                elements.sidebar.classList.remove('mobile-open');
            }
            if (elements.overlay) {
                elements.overlay.classList.remove('show');
            }
        }
    };

    // ==================== 面包屑管理器 ====================
    const Breadcrumb = {
        render() {
            if (!elements.breadcrumb) return;

            const currentTab = TabManager.getActiveTab();
            if (!currentTab) return;

            // 简单的面包屑：首页 > 当前页面
            let html = `
                <div class="breadcrumb-item">
                    <a href="/" data-url="/">
                        <i class="bi bi-house"></i>
                    </a>
                </div>
            `;

            if (currentTab.url !== '/') {
                html += `
                    <div class="breadcrumb-item active">${currentTab.title}</div>
                `;
            }

            elements.breadcrumb.innerHTML = html;

            // 绑定点击事件
            elements.breadcrumb.querySelectorAll('a[data-url]').forEach(link => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    TabManager.switchTab(link.dataset.url);
                });
            });
        }
    };

    // ==================== 同步当前页面到标签页 ====================
    function syncCurrentPage() {
        const currentUrl = window.location.pathname;
        let tab = state.tabs.find(t => t.url === currentUrl);

        // 如果当前页面不在标签页中，添加它
        if (!tab) {
            // 从菜单配置中查找
            const menuItem = MENU_ITEMS.find(item => item.url === currentUrl);
            if (menuItem) {
                tab = { ...menuItem };
            } else {
                // 尝试从页面标题获取
                const title = document.title.split(' - ')[0] || '页面';
                tab = { title, url: currentUrl, icon: 'bi-file-text', closable: true };
            }
            state.tabs.push(tab);
        }

        // 更新激活状态
        state.tabs.forEach(t => t.active = t.url === currentUrl);
        state.activeTab = currentUrl;

        TabManager.render();
        Breadcrumb.render();
        saveState();
    }

    // ==================== 菜单绑定 ====================
    function bindMenuEvents() {
        document.querySelectorAll('.menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const url = item.dataset.url;
                const title = item.dataset.title;
                const icon = item.dataset.icon || 'bi-file-text';
                const closable = item.dataset.closable !== 'false';

                TabManager.openTab(title, url, icon, closable);

                // 移动端点击后关闭侧边栏
                if (window.innerWidth <= 768) {
                    Sidebar.closeMobile();
                }
            });
        });
    }

    // ==================== 绑定标签操作按钮 ====================
    function bindTagActions() {
        // 刷新当前标签页
        if (elements.refreshBtn) {
            elements.refreshBtn.addEventListener('click', () => {
                location.reload();
            });
        }

        // 关闭所有标签
        if (elements.closeAllBtn) {
            elements.closeAllBtn.addEventListener('click', () => {
                TabManager.closeAllTabs();
            });
        }

        // 移动端遮罩层点击
        if (elements.overlay) {
            elements.overlay.addEventListener('click', () => {
                Sidebar.closeMobile();
            });
        }
    }

    // ==================== 初始化 ====================
    function init() {
        initElements();
        loadState();

        // 初始化侧边栏
        Sidebar.init();

        // 同步当前页面
        syncCurrentPage();

        // 绑定菜单事件
        bindMenuEvents();

        // 绑定标签操作
        bindTagActions();
    }

    // ==================== 暴露全局 API ====================
    window.ReviewAgentUI = {
        TabManager,
        Sidebar,
        openTab: (title, url, icon, closable) => TabManager.openTab(title, url, icon, closable),
        closeTab: (url) => TabManager.closeTab(url),
        switchTab: (url) => TabManager.switchTab(url)
    };

    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
