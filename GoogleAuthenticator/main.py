import os
import sys
import tempfile
from pathlib import Path


# === 字体预处理 - 必须在其他导入之前 ===
def setup_fonts():
    """设置字体 - 优化版本"""
    print("=== 字体初始化 ===")

    # 获取基础路径
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        print(f"📦 打包环境，基础路径: {base_path}")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        print(f"🔧 开发环境，基础路径: {base_path}")

    font_files = {"得意黑": "SmileySans-Oblique.ttf"}

    for font_name, font_file in font_files.items():
        font_path = os.path.join(base_path, font_file)

        if os.path.exists(font_path):
            print(f"✅ 找到字体文件: {font_path}")

            # 在打包环境中，优先检查系统字体
            if getattr(sys, 'frozen', False):
                # 首先尝试使用系统字体（如果已安装）
                if is_font_available(font_name):
                    print(f"✅ 系统字体 '{font_name}' 可用，直接使用")
                    continue

                # 系统字体不可用，再尝试私有注册
                print(f"🔄 系统字体 '{font_name}' 不可用，尝试私有注册...")
                register_font_if_needed(font_path, font_name)
        else:
            print(f"❌ 未找到字体文件: {font_path}")

    print("=== 字体初始化完成 ===\n")


def is_font_available(font_name):
    """检查字体是否已经可用"""
    try:
        from tkinter import font as tkFont
        available_fonts = tkFont.families()
        return font_name in available_fonts
    except:
        return False


def register_font_if_needed(font_path, font_name):
    """只在需要时注册字体"""
    try:
        # 检查是否已经注册过（通过标记文件）
        temp_dir = tempfile.gettempdir()
        registry_marker = os.path.join(temp_dir, f"{font_name}_registered.txt")

        # 如果标记文件存在且字体可用，则跳过注册
        if os.path.exists(registry_marker) and is_font_available(font_name):
            print(f"✅ 字体 '{font_name}' 已注册过且仍然可用")
            return True

        # 将字体复制到临时目录
        temp_font_path = os.path.join(temp_dir, os.path.basename(font_path))

        if not os.path.exists(temp_font_path):
            import shutil
            shutil.copy2(font_path, temp_font_path)
            print(f"📝 字体已复制到临时目录: {temp_font_path}")

        # 在Windows上注册字体
        if sys.platform == "win32":
            success = register_windows_font(temp_font_path, font_name)
            if success:
                # 创建注册标记文件
                with open(registry_marker, 'w') as f:
                    f.write(f"Font registered at: {temp_font_path}\n")
                return True
            else:
                return False
        else:
            # 非Windows系统，直接使用字体文件路径
            print(f"ℹ️ 非Windows系统，使用字体文件路径: {temp_font_path}")
            return True

    except Exception as e:
        print(f"❌ 字体注册失败: {e}")
        return False


def register_windows_font(font_path, font_name):
    """在Windows上注册字体（仅当前进程）"""
    try:
        import ctypes
        from ctypes import wintypes

        # 加载Windows API
        gdi32 = ctypes.WinDLL('gdi32')
        AddFontResourceEx = gdi32.AddFontResourceExW
        AddFontResourceEx.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        AddFontResourceEx.restype = wintypes.INT

        # 添加字体资源（仅当前进程）
        FR_PRIVATE = 0x10
        result = AddFontResourceEx(font_path, FR_PRIVATE, None)

        if result > 0:
            print(f"✅ 成功注册字体: {font_name}")

            # 通知系统字体变化（可选，不影响当前进程）
            try:
                user32 = ctypes.WinDLL('user32')
                HWND_BROADCAST = 0xFFFF
                WM_FONTCHANGE = 0x001D
                user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
                print("✅ 已通知系统字体变化")
            except Exception as e:
                print(f"⚠️ 通知系统字体变化失败: {e}")

            return True
        else:
            print(f"❌ 字体注册失败: {font_name}")
            return False

    except Exception as e:
        print(f"❌ 字体注册过程出错: {e}")
        return False


# 执行字体设置
setup_fonts()

# === 现在导入其他模块 ===
import customtkinter as ctk
from tkinter import filedialog, messagebox, Toplevel, Text, font as tkFont, Tk
import pyotp
import pyzbar.pyzbar as pyzbar
import base64
import urllib.parse
import time
import json
import threading
import subprocess
from pathlib import Path
import re
from PIL import Image
import pystray
from pystray import MenuItem as item
import atexit
import ctypes
from ctypes import wintypes

# 迁移模块支持
try:
    import google_auth_migration_pb2 as migration_pb

    MIGRATION_AVAILABLE = True
    print("✅ 迁移模块已加载")
except ImportError:
    migration_pb = None
    MIGRATION_AVAILABLE = False
    print("⚠️ 迁移模块不可用")

# 初始化主题（深色模式）
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# 颜色常量
DARK_CARD = "#3d3d3d"
DARK_BORDER = "#555555"
TEXT_WHITE = "#ffffff"
TEXT_LIGHT_GRAY = "#bbbbbb"
TEXT_MEDIUM_GRAY = "#999999"


# 基于系统互斥体的单例类（无文件生成）
class SystemMutexSingleInstance:
    def __init__(self):
        self.mutex_handle = None  # Windows互斥体句柄
        self.pipe_handle = None  # Linux/macOS管道句柄
        self.is_single = False  # 是否为单例

    def check(self):
        """跨平台单例检查：Windows用互斥体，Linux/macOS用管道锁"""
        try:
            if sys.platform.startswith('win'):
                # Windows：创建全局互斥体（确保多用户环境生效）
                mutex_name = "Global\\GoogleAuthenticator_SingleInstance_8f2d7c9e"
                kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                # 创建互斥体：无安全描述符、非初始拥有、唯一名称
                self.mutex_handle = kernel32.CreateMutexW(None, False, mutex_name)
                error_code = ctypes.get_last_error()

                if error_code == 183:  # 互斥体已存在（已有程序实例）
                    return False
                atexit.register(self.release)  # 退出时释放资源
                self.is_single = True
                return True

            else:
                # Linux/macOS：匿名管道加锁（进程退出自动释放）
                import fcntl  # 仅Linux/macOS需要，避免Windows报错
                pipe_r, pipe_w = os.pipe()
                self.pipe_handle = pipe_w
                # 非阻塞排他锁：已被锁则抛BlockingIOError
                fcntl.flock(self.pipe_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                atexit.register(self.release)
                self.is_single = True
                return True

        except Exception as e:
            print(f"单例检查错误: {e}")
            return False

    def release(self):
        """释放系统资源"""
        if sys.platform.startswith('win') and self.mutex_handle:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.CloseHandle(self.mutex_handle)
            self.mutex_handle = None
        elif self.pipe_handle:
            os.close(self.pipe_handle)
            self.pipe_handle = None


class GoogleAuthenticator:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Authenticator")
        self.root.geometry("380x680")
        self.root.resizable(False, False)

        # 启动时透明隐藏，避免闪烁
        self.root.attributes("-alpha", 0.0)
        self.root.withdraw()

        # 配置文件路径
        self.config_file = os.path.join(str(Path.home()), ".auth_app_config.json")
        self.load_settings()  # 加载配置目录
        self.old_save_file = os.path.join(str(Path.home()), ".ubisoft_authenticator.json")
        self.save_file = os.path.join(self.config_dir, ".ubisoft_authenticator.json")

        # 配置迁移（旧→新目录）
        self.migrate_from_old_location()

        # 渲染状态
        self.render_complete = False
        self.render_step = 0
        self.total_render_steps = 5

        # 托盘相关
        self.tray_icon = None
        self.tray_thread = None
        self.is_running = True

        # 窗口关闭拦截（最小化到托盘）
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # 资源加载
        self.load_deyihei_font()
        self.set_app_icon()

        # 数据存储
        self.accounts = []
        self.timer_id = None
        self.migrate_accounts = []
        self.current_editing_account = None

        # 复制功能优化
        self.copy_hint = None
        self.copy_lock = False
        self.copy_hint_timer = None
        self.last_copy_time = 0

        # 卡片渲染跟踪
        self.current_card_ids = set()
        self.pages_created = {
            "account": False, "scan": False, "manual": False,
            "migrate_scan": False, "migration_help": False, "edit": False
        }

        # 分步骤创建UI
        self.root.after(10, self.create_ui_step1)

    def create_ui_step1(self):
        """UI步骤1：顶部标题栏"""
        self.header = ctk.CTkFrame(self.root, height=50, fg_color="#1e1e1e")
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)
        self.render_step += 1
        self.root.after(10, self.create_ui_step2)

    def create_ui_step2(self):
        """UI步骤2：标题与账户计数"""
        # 直接使用得意黑字体，如果不可用则使用默认字体
        title_font = self._get_font(size=18, weight="bold")
        count_font = self._get_font(size=14)

        ctk.CTkLabel(
            self.header,
            text="Google Authenticator",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(side="left", padx=20, pady=15)

        self.account_count = ctk.CTkLabel(
            self.header,
            text="0个账户",
            font=count_font,
            text_color=TEXT_MEDIUM_GRAY
        )
        self.account_count.pack(side="right", padx=20, pady=15)
        self.render_step += 1
        self.root.after(10, self.create_ui_step3)

    def create_ui_step3(self):
        """UI步骤3：主内容区容器"""
        self.content = ctk.CTkFrame(self.root, fg_color="#2d2d2d", height=570)
        self.content.pack(fill="x", side="top")
        self.content.pack_propagate(False)
        self.pages = {}  # 页面容器
        self.render_step += 1
        self.root.after(10, self.create_ui_step4)

    def create_ui_step4(self):
        """UI步骤4：所有页面内容"""
        self.create_account_page()
        self.create_scan_page()
        self.create_manual_page()
        self.create_migrate_scan_page()
        self.create_migration_help_page()
        self.create_edit_page()
        self.show_page("account")  # 默认显示账户页
        self.render_step += 1
        self.root.after(10, self.create_ui_step5)

    def create_ui_step5(self):
        """UI步骤5：底部导航栏"""
        self.nav = ctk.CTkFrame(
            self.root,
            height=60,
            border_width=1,
            fg_color="#1e1e1e",
            border_color=DARK_BORDER
        )
        self.nav.pack(fill="x", side="bottom")
        self.nav.pack_propagate(False)

        # 导航按钮
        nav_buttons = [
            ("账户", "account"), ("扫码", "scan"), ("手动", "manual"),
            ("迁移扫码", "migrate_scan"), ("帮助", "migration_help")
        ]
        for text, page in nav_buttons:
            btn_font = self._get_font(size=12)
            ctk.CTkButton(
                self.nav,
                text=text,
                command=lambda p=page: self.show_page(p),
                font=btn_font,
                fg_color="transparent",
                text_color=TEXT_MEDIUM_GRAY,
                hover_color="#444444",
                corner_radius=0,
                width=76
            ).pack(side="left", fill="both", expand=True)

        self.render_step += 1
        self.preload_accounts()  # 预加载账户
        self.root.after(50, self.check_render_complete)

    def _get_font(self, size=14, weight="normal"):
        """获取字体，直接使用得意黑，如果不可用则使用默认字体"""
        try:
            # 检查得意黑字体是否可用
            if "得意黑" in tkFont.families():
                if weight == "bold":
                    return ctk.CTkFont(family="得意黑", size=size, weight="bold")
                else:
                    return ctk.CTkFont(family="得意黑", size=size)
            else:
                # 如果得意黑不可用，使用默认字体
                print("⚠️ 得意黑字体不可用，使用默认字体")
                return ctk.CTkFont(size=size, weight=weight)
        except Exception as e:
            print(f"❌ 字体获取失败: {e}，使用默认字体")
            return ctk.CTkFont(size=size, weight=weight)

    def check_render_complete(self):
        """检查渲染完成，淡入窗口"""
        self.root.update_idletasks()
        if self.render_step >= self.total_render_steps and hasattr(self, 'accounts'):
            self.render_complete = True
            self.root.after(10, self.fade_in_window)
            self.start_tray()  # 启动托盘
            self.start_timer()  # 启动验证码定时器
        else:
            self.root.after(20, self.check_render_complete)

    def fade_in_window(self, alpha=0.0):
        """窗口淡入效果"""
        alpha += 0.1
        self.root.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.root.after(10, self.fade_in_window, alpha)
        else:
            self.root.deiconify()
            self.root.attributes("-alpha", 1.0)
            # 提示迁移模块状态
            if not MIGRATION_AVAILABLE:
                self.show_migration_setup_guide()

    def preload_accounts(self):
        """预加载账户数据"""
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.accounts = []
                for item in data:
                    if not any(a["secret"] == item["secret"] for a in self.accounts):
                        self.accounts.append({
                            "id": hash(item["secret"]),
                            "issuer": item["issuer"],
                            "name": item["name"],
                            "secret": item["secret"],
                            "totp": pyotp.TOTP(item["secret"]),
                            "card_elements": None
                        })
            print(f"预加载完成，账户数量: {len(self.accounts)}")
            self.root.after(10, self.refresh_accounts)
        except Exception as e:
            print(f"预加载失败: {str(e)}")
            self.root.after(10, self.refresh_accounts)

    def load_deyihei_font(self):
        """加载得意黑字体 - 简化版本"""
        try:
            # 检查字体是否可用
            if "得意黑" in tkFont.families():
                print("✅ '得意黑' 字体可用")
                return True
            else:
                print("⚠️ '得意黑' 字体不可用，将使用默认字体")
                return False

        except Exception as e:
            print(f"❌ 字体检查失败: {e}")
            return False

    def set_app_icon(self):
        """设置应用图标"""
        try:
            # 获取基础路径
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            icon_file = os.path.join(base_path, "app_icon_B.ico")
            print(f"尝试加载图标：{icon_file}")

            if os.path.exists(icon_file):
                # Windows图标绑定
                try:
                    self.root.iconbitmap(default=icon_file)
                    print(f"✅ 成功加载主窗口图标：{icon_file}")
                except Exception as e:
                    print(f"iconbitmap加载失败：{e}")
                    # 尝试通用方法
                    try:
                        from tkinter import PhotoImage
                        icon_img = PhotoImage(file=icon_file)
                        self.root.iconphoto(True, icon_img)
                        print(f"✅ 成功加载图标（PhotoImage）：{icon_file}")
                    except Exception as e2:
                        print(f"PhotoImage加载失败：{e2}")
            else:
                print("⚠️ 未找到图标文件，使用系统默认图标")

        except Exception as e:
            print(f"❌ 图标加载失败：{e}")

    def create_account_page(self):
        """账户列表页（带隐藏滚动条）"""
        if self.pages_created["account"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["account"] = frame
        self.pages_created["account"] = True

        # 滚动框架
        self.scrollable_frame = ctk.CTkScrollableFrame(
            frame,
            fg_color="transparent",
            scrollbar_button_color="#444444",
            scrollbar_button_hover_color="#666666"
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=15, pady=10)

        # 隐藏滚动条
        self.scrollbar = self.scrollable_frame._scrollbar
        self.scrollbar.grid_remove()

        # 滚轮绑定
        self.scrollable_frame.bind("<MouseWheel>", self.on_scroll)
        self.scrollable_frame.bind("<Button-4>", self.on_scroll)
        self.scrollable_frame.bind("<Button-5>", self.on_scroll)

        # 账户卡片容器
        self.account_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.account_frame.pack(fill="x", pady=5)

        # 空状态提示
        empty_font = self._get_font(size=14)
        self.empty_hint = ctk.CTkLabel(
            frame,
            text="暂无账户\n可通过扫码、手动添加",
            font=empty_font,
            text_color=TEXT_MEDIUM_GRAY,
            justify="center"
        )

    def on_scroll(self, event):
        """滚轮滚动处理"""
        if event.delta > 0 or event.num == 4:
            self.scrollable_frame._parent_canvas.yview_scroll(-1, "units")
        else:
            self.scrollable_frame._parent_canvas.yview_scroll(1, "units")

    def create_edit_page(self):
        """账户编辑页"""
        if self.pages_created["edit"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["edit"] = frame
        self.pages_created["edit"] = True

        # 返回按钮
        back_font = self._get_font(size=12)
        ctk.CTkButton(
            frame,
            text="← 返回账户列表",
            command=lambda: self.show_page("account"),
            font=back_font,
            fg_color="transparent",
            text_color="#87cefa",
            width=10
        ).pack(anchor="w", padx=20, pady=10)

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        ctk.CTkLabel(
            frame,
            text="编辑账户",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=(10, 20), padx=20, anchor="w")

        # 编辑表单
        self.edit_info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.edit_info_frame.pack(fill="x", padx=20, pady=10)

        # 平台名称
        label_font = self._get_font(size=12)
        entry_font = self._get_font(size=14)

        ctk.CTkLabel(
            self.edit_info_frame,
            text="平台名称",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.edit_issuer_entry = ctk.CTkEntry(
            self.edit_info_frame,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.edit_issuer_entry.pack(anchor="w", pady=(0, 15))

        # 账户名称
        ctk.CTkLabel(
            self.edit_info_frame,
            text="账户",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.edit_name_entry = ctk.CTkEntry(
            self.edit_info_frame,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.edit_name_entry.pack(anchor="w", pady=(0, 15))

        # 密钥（隐藏中间）
        ctk.CTkLabel(
            self.edit_info_frame,
            text="密钥",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.edit_secret = ctk.CTkLabel(
            self.edit_info_frame,
            text="",
            font=entry_font,
            text_color=TEXT_WHITE
        )
        self.edit_secret.pack(anchor="w", pady=(0, 30))

        # 保存按钮
        btn_font = self._get_font(size=14, weight="bold")
        ctk.CTkButton(
            frame,
            text="保存修改",
            command=self.save_edit,
            font=btn_font,
            fg_color="#1a73e8",
            text_color="white",
            height=45
        ).pack(fill="x", padx=20, pady=10)

        # 删除按钮
        ctk.CTkButton(
            frame,
            text="删除此账户",
            command=self.confirm_delete,
            font=btn_font,
            fg_color="#ff4d4d",
            text_color="white",
            height=45
        ).pack(fill="x", padx=20, pady=20)

    def save_edit(self):
        """保存编辑的账户信息"""
        if not self.current_editing_account:
            return
        new_issuer = self.edit_issuer_entry.get().strip()
        new_name = self.edit_name_entry.get().strip()
        if not new_issuer or not new_name:
            messagebox.showwarning("提示", "平台名称和账户名称不能为空")
            return
        # 更新账户信息
        self.current_editing_account["issuer"] = new_issuer
        self.current_editing_account["name"] = new_name
        self.save_accounts()
        self.refresh_accounts()
        self.show_page("account")
        messagebox.showinfo("成功", "账户信息修改保存成功")

    def create_scan_page(self):
        """普通扫码添加页"""
        if self.pages_created["scan"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["scan"] = frame
        self.pages_created["scan"] = True

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        desc_font = self._get_font(size=12)

        ctk.CTkLabel(
            frame,
            text="普通扫码添加",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=(20, 10), padx=20, anchor="w")
        ctk.CTkLabel(
            frame,
            text="请选择Google Authenticator的标准二维码",
            font=desc_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(padx=20, anchor="w", pady=(0, 20))

        # 预览区域
        preview_font = self._get_font(size=12)
        self.scan_preview = ctk.CTkLabel(
            frame,
            text="点击选择二维码图片",
            font=preview_font,
            corner_radius=8,
            fg_color="#444444"
        )
        self.scan_preview.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 结果提示
        self.scan_result = ctk.CTkLabel(
            frame,
            text="",
            font=desc_font,
            wraplength=320,
            text_color=TEXT_MEDIUM_GRAY
        )
        self.scan_result.pack(pady=10, padx=20)

        # 按钮区
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        btn_font = self._get_font(size=14, weight="bold")

        ctk.CTkButton(
            btn_frame,
            text="选择图片",
            command=self.scan_standard_qr,
            font=btn_font,
            fg_color="#1a73e8",
            height=45
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.add_scan_btn = ctk.CTkButton(
            btn_frame,
            text="添加账户",
            command=self.add_scanned,
            font=btn_font,
            fg_color="#1a73e8",
            height=45,
            state="disabled"
        )
        self.add_scan_btn.pack(side="left", fill="x", expand=True)

        self.scanned_data = None

    def create_manual_page(self):
        """手动添加页"""
        if self.pages_created["manual"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["manual"] = frame
        self.pages_created["manual"] = True

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        desc_font = self._get_font(size=12)

        ctk.CTkLabel(
            frame,
            text="手动添加账户",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=(20, 10), padx=20, anchor="w")
        ctk.CTkLabel(
            frame,
            text="请输入平台名称、账户和密钥（Base32格式）",
            font=desc_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(padx=20, anchor="w", pady=(0, 20))

        # 表单
        form = ctk.CTkFrame(frame, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=10)

        # 平台名称
        label_font = self._get_font(size=12)
        entry_font = self._get_font(size=14)

        ctk.CTkLabel(
            form,
            text="平台名称",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.manual_platform = ctk.CTkEntry(
            form,
            height=40,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.manual_platform.pack(fill="x", pady=(0, 15))

        # 账户
        ctk.CTkLabel(
            form,
            text="账户（邮箱/手机号）",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.manual_account = ctk.CTkEntry(
            form,
            height=40,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.manual_account.pack(fill="x", pady=(0, 15))

        # 密钥
        ctk.CTkLabel(
            form,
            text="密钥（Base32）",
            font=label_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 5))
        self.manual_secret = ctk.CTkEntry(
            form,
            height=40,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.manual_secret.pack(fill="x", pady=(0, 15))

        # 示例
        example_font = self._get_font(size=10)
        ctk.CTkLabel(
            form,
            text="示例密钥格式：JBSWY3DPEHPK3PXP",
            font=example_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(anchor="w", pady=(0, 10))

        # 添加按钮
        btn_font = self._get_font(size=14, weight="bold")
        ctk.CTkButton(
            frame,
            text="添加账户",
            command=self.add_manual,
            font=btn_font,
            fg_color="#1a73e8",
            height=45
        ).pack(fill="x", padx=20, pady=20)

    def create_migrate_scan_page(self):
        """迁移扫码页"""
        if self.pages_created["migrate_scan"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["migrate_scan"] = frame
        self.pages_created["migrate_scan"] = True

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        desc_font = self._get_font(size=12)

        ctk.CTkLabel(
            frame,
            text="迁移二维码扫描",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=(20, 10), padx=20, anchor="w")
        ctk.CTkLabel(
            frame,
            text="请选择Google Authenticator导出的迁移二维码",
            font=desc_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(padx=20, anchor="w", pady=(0, 20))

        # 预览区域
        preview_font = self._get_font(size=12)
        self.migrate_scan_preview = ctk.CTkLabel(
            frame,
            text="点击选择迁移二维码图片",
            font=preview_font,
            corner_radius=8,
            fg_color="#444444"
        )
        self.migrate_scan_preview.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # 结果提示
        self.migrate_scan_result = ctk.CTkLabel(
            frame,
            text="",
            font=desc_font,
            wraplength=320,
            text_color=TEXT_MEDIUM_GRAY
        )
        self.migrate_scan_result.pack(pady=10, padx=20)

        # 按钮区
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        btn_font = self._get_font(size=14, weight="bold")

        ctk.CTkButton(
            btn_frame,
            text="选择迁移图片",
            command=self.scan_migration_qr_independent,
            font=btn_font,
            fg_color="#1a73e8",
            height=45,
            state="normal" if MIGRATION_AVAILABLE else "disabled"
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.migrate_scan_import_btn = ctk.CTkButton(
            btn_frame,
            text="导入账户",
            command=self.import_migrated,
            font=btn_font,
            fg_color="#1a73e8",
            height=45,
            state="disabled"
        )
        self.migrate_scan_import_btn.pack(side="left", fill="x", expand=True)

    def create_migration_help_page(self):
        """帮助与配置页"""
        if self.pages_created["migration_help"]:
            return
        frame = ctk.CTkFrame(self.content, fg_color="#2d2d2d")
        self.pages["migration_help"] = frame
        self.pages_created["migration_help"] = True

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        ctk.CTkLabel(
            frame,
            text="迁移功能说明",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=(20, 10), padx=20, anchor="w")

        # 迁移状态
        status_font = self._get_font(size=12)
        status_text = "✅ 迁移模块已就绪" if MIGRATION_AVAILABLE else "❌ 缺少迁移模块"
        status_color = "#4ECDC4" if MIGRATION_AVAILABLE else "#ff6b6b"
        ctk.CTkLabel(
            frame,
            text=status_text,
            font=status_font,
            text_color=status_color
        ).pack(padx=20, anchor="w", pady=(0, 10))

        # 帮助文本
        text_font = self._get_font(size=12)
        text_widget = Text(
            frame,
            wrap="word",
            height=15,
            width=45,
            bg="#2d2d2d",
            fg=TEXT_WHITE,
            font=(text_font.cget("family"), text_font.cget("size"))
        )
        text_widget.pack(padx=20, pady=10)
        text_widget.insert("1.0", """基础使用方法：
1. 扫码功能：扫描平台绑定二维码添加账户
2. 手动添加：输入平台、账户和Base32密钥
3. 复制验证码：点击账户卡片即可复制
4. 批量迁移：通过迁移二维码导入其他设备账户

迁移功能操作步骤：
1. 手机端Google Authenticator → 右上角菜单
2. 选择「转移账户」→「导出账户」
3. 选择需迁移账户并生成二维码
4. 本程序「迁移扫码」功能扫描该二维码
""")
        text_widget.config(state="disabled")

        # 分割线
        ctk.CTkFrame(frame, height=1, fg_color=DARK_BORDER).pack(fill="x", padx=20, pady=15)

        # 配置管理
        config_title_font = self._get_font(size=14, weight="bold")
        ctk.CTkLabel(
            frame,
            text="配置文件管理",
            font=config_title_font,
            text_color=TEXT_WHITE
        ).pack(padx=20, anchor="w", pady=(0, 10))

        # 当前配置目录
        config_font = self._get_font(size=11)
        self.config_path_label = ctk.CTkLabel(
            frame,
            text=f"当前目录：{self.config_dir}",
            font=config_font,
            text_color=TEXT_LIGHT_GRAY,
            wraplength=320
        )
        self.config_path_label.pack(padx=20, anchor="w", pady=(0, 10))

        # 配置按钮
        config_btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        config_btn_frame.pack(fill="x", padx=20, pady=5)
        btn_font = self._get_font(size=12)

        ctk.CTkButton(
            config_btn_frame,
            text="更改配置目录",
            command=self.show_change_config_window,
            font=btn_font,
            fg_color="#1a73e8",
            height=35
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(
            config_btn_frame,
            text="打开当前目录",
            command=self.open_config_folder,
            font=btn_font,
            fg_color="#1a73e8",
            height=35
        ).pack(side="left", fill="x", expand=True)

    def show_page(self, page_name):
        """切换页面"""
        if hasattr(self, 'pages') and page_name in self.pages:
            for page in self.pages.values():
                page.pack_forget()
            self.pages[page_name].pack(fill="both", expand=True)
            if page_name == "account":
                self.refresh_accounts()
            self.root.update_idletasks()

    def refresh_accounts(self):
        """刷新账户列表"""
        print(f"刷新账户列表，当前数量: {len(self.accounts)}")
        self.current_card_ids.clear()

        # 清空现有卡片
        for widget in self.account_frame.winfo_children():
            widget.destroy()

        # 更新账户计数
        count_font = self._get_font(size=14)
        self.account_count.configure(text=f"{len(self.accounts)}个账户", font=count_font)

        # 空状态/账户卡片
        if not self.accounts:
            self.empty_hint.pack(expand=True, pady=50)
            return
        else:
            self.empty_hint.pack_forget()

        # 创建账户卡片
        for account in self.accounts:
            if account["id"] not in self.current_card_ids:
                self.create_account_card(account)
                self.current_card_ids.add(account["id"])

    def create_account_card(self, account):
        """创建单个账户卡片"""
        card = ctk.CTkFrame(
            self.account_frame,
            fg_color=DARK_CARD,
            corner_radius=8,
            border_width=1,
            border_color=DARK_BORDER
        )
        card.pack(fill="x", pady=5)
        card.pack_propagate(False)
        card.configure(height=80)

        # 卡片点击逻辑
        def on_card_click(event=None, is_edit=False):
            if is_edit:
                self.enter_edit_page(account)
            else:
                self.copy_otp(account)

        # 绑定点击事件
        card.bind("<Button-1>", lambda e: on_card_click())
        card.configure(cursor="hand2")

        # 网格布局
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        # 左侧信息区
        left_frame = ctk.CTkFrame(card, fg_color="transparent")
        left_frame.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        left_frame.bind("<Button-1>", lambda e: on_card_click())
        left_frame.configure(cursor="hand2")

        # 平台名称
        issuer_font = self._get_font(size=14, weight="bold")
        issuer_label = ctk.CTkLabel(
            left_frame,
            text=account["issuer"],
            font=issuer_font,
            text_color=TEXT_WHITE
        )
        issuer_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        issuer_label.bind("<Button-1>", lambda e: on_card_click())
        issuer_label.configure(cursor="hand2")

        # 账户名称
        name_font = self._get_font(size=11)
        name_label = ctk.CTkLabel(
            left_frame,
            text=account["name"],
            font=name_font,
            text_color=TEXT_LIGHT_GRAY
        )
        name_label.grid(row=1, column=0, sticky="w")
        name_label.bind("<Button-1>", lambda e: on_card_click())
        name_label.configure(cursor="hand2")

        # 右侧操作区
        right_frame = ctk.CTkFrame(card, fg_color="transparent")
        right_frame.grid(row=0, column=1, padx=15, pady=10, sticky="e")
        right_frame.grid_columnconfigure(0, weight=1)

        # 编辑按钮
        edit_font = self._get_font(size=12)
        edit_btn = ctk.CTkButton(
            right_frame,
            text="✎",
            width=20,
            height=20,
            font=edit_font,
            fg_color="transparent",
            text_color=TEXT_LIGHT_GRAY,
            hover_color="#444444",
            command=lambda: on_card_click(is_edit=True)
        )
        edit_btn.grid(row=0, column=0, sticky="e")

        # 验证码
        otp_font = self._get_font(size=20, weight="bold")
        otp_label = ctk.CTkLabel(
            right_frame,
            text=account["totp"].now(),
            font=otp_font,
            text_color="#1a73e8",
            width=80
        )
        otp_label.grid(row=1, column=0, sticky="e", pady=(5, 0))
        otp_label.bind("<Button-1>", lambda e: on_card_click())
        otp_label.configure(cursor="hand2")

        # 倒计时进度条
        progress = ctk.CTkProgressBar(
            right_frame,
            width=80,
            height=4,
            fg_color="#555555"
        )
        progress.grid(row=2, column=0, sticky="e", pady=3)
        progress.set(0.5)
        progress.bind("<Button-1>", lambda e: on_card_click())
        progress.configure(cursor="hand2")

        # 存储卡片元素（用于定时器更新）
        account["card_elements"] = {
            "otp_label": otp_label,
            "progress": progress,
            "card": card
        }

        # 右键编辑
        card.bind("<Button-3>", lambda e: self.enter_edit_page(account))
        left_frame.bind("<Button-3>", lambda e: self.enter_edit_page(account))
        issuer_label.bind("<Button-3>", lambda e: self.enter_edit_page(account))
        name_label.bind("<Button-3>", lambda e: self.enter_edit_page(account))
        otp_label.bind("<Button-3>", lambda e: self.enter_edit_page(account))
        progress.bind("<Button-3>", lambda e: self.enter_edit_page(account))

    def is_widget_valid(self, widget):
        """检查组件是否有效"""
        try:
            return widget.winfo_exists()
        except:
            return False

    def enter_edit_page(self, account):
        """进入编辑页并加载数据"""
        self.current_editing_account = account
        # 填充表单
        self.edit_issuer_entry.delete(0, "end")
        self.edit_issuer_entry.insert(0, account["issuer"])
        self.edit_name_entry.delete(0, "end")
        self.edit_name_entry.insert(0, account["name"])
        # 隐藏密钥中间部分
        hidden_secret = account["secret"][:4] + "****" + account["secret"][-4:]
        self.edit_secret.configure(text=hidden_secret)
        # 切换页面
        self.show_page("edit")

    def confirm_delete(self):
        """确认删除账户"""
        if not self.current_editing_account:
            return
        if messagebox.askyesno(
                "确认删除",
                f"确定删除 {self.current_editing_account['issuer']} - {self.current_editing_account['name']}？\n此操作不可恢复"
        ):
            self.current_editing_account["card_elements"] = None
            self.accounts.remove(self.current_editing_account)
            self.save_accounts()
            self.refresh_accounts()
            self.show_page("account")

    def copy_otp(self, account):
        """复制验证码"""
        current_time = time.time()
        if current_time - self.last_copy_time < 0.5:
            return
        self.last_copy_time = current_time

        try:
            otp = account["totp"].now()
            self.root.clipboard_clear()
            self.root.clipboard_append(otp)
            self.root.update()
            self.show_copy_hint(f"已复制: {otp}")
        except Exception as e:
            print(f"复制失败: {e}")
            self.show_copy_hint("复制失败")

    def show_copy_hint(self, text):
        """显示复制提示"""
        if self.copy_hint_timer:
            self.root.after_cancel(self.copy_hint_timer)
            self.copy_hint_timer = None

        if not self.copy_hint:
            hint_font = self._get_font(size=12)
            self.copy_hint = ctk.CTkLabel(
                self.root,
                text=text,
                font=hint_font,
                fg_color="#1a73e8",
                text_color="white",
                corner_radius=4,
                padx=15,
                pady=8
            )
        else:
            self.copy_hint.configure(text=text)

        self.copy_hint.place(relx=0.5, rely=0.8, anchor="center")
        self.copy_hint.lift()
        self.copy_hint_timer = self.root.after(800, self.hide_copy_hint)

    def hide_copy_hint(self):
        """隐藏复制提示"""
        if self.copy_hint:
            self.copy_hint.place_forget()
        self.copy_hint_timer = None

    def scan_standard_qr(self):
        """扫描普通二维码"""
        file_path = filedialog.askopenfilename(
            title="选择二维码图片",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg")]
        )
        if not file_path:
            return

        try:
            # 处理图片
            image = Image.open(file_path).resize((280, 280), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(image, size=(280, 280))
            self.scan_preview.configure(image=ctk_img, text="")

            # 解析二维码
            decoded_objects = pyzbar.decode(image)
            if not decoded_objects:
                raise Exception("未识别到二维码，请确保图片清晰")

            # 提取TOTP链接
            qr_data = None
            for obj in decoded_objects:
                data = obj.data.decode().strip().lower()
                if data.startswith("otpauth://totp/"):
                    qr_data = data
                    break
            if not qr_data:
                raise Exception("未找到有效的Google Authenticator链接")

            # 解析链接参数
            parsed = urllib.parse.urlparse(qr_data)
            params = urllib.parse.parse_qs(parsed.query)
            if "secret" not in params:
                raise Exception("链接中缺少secret参数")

            # 提取平台和账户名
            path = parsed.path[1:].split(":")
            if len(path) >= 2:
                issuer = path[0]
                name = ":".join(path[1:])
            else:
                issuer = params.get("issuer", ["未知平台"])[0]
                name = path[0] if path else "未知账户"

            self.scanned_data = {
                "issuer": issuer.strip(),
                "name": name.strip(),
                "secret": params["secret"][0].strip()
            }

            # 更新UI
            self.add_scan_btn.configure(state="normal")
            self.scan_result.configure(
                text=f"✅ 识别成功：{self.scanned_data['issuer']} - {self.scanned_data['name']}",
                text_color="#4ECDC4"
            )

        except Exception as e:
            self.scan_result.configure(
                text=f"❌ 识别失败：{str(e)}",
                text_color="#ff6b6b"
            )
            self.add_scan_btn.configure(state="disabled")

    def add_scanned(self):
        """添加扫码识别的账户"""
        if not self.scanned_data:
            return
        try:
            # 检查重复
            if any(a["secret"] == self.scanned_data["secret"] for a in self.accounts):
                messagebox.showinfo("提示", "该账户已存在")
                return

            # 添加账户
            new_account = {
                "id": hash(self.scanned_data["secret"]),
                "issuer": self.scanned_data["issuer"],
                "name": self.scanned_data["name"],
                "secret": self.scanned_data["secret"],
                "totp": pyotp.TOTP(self.scanned_data["secret"]),
                "card_elements": None
            }
            self.accounts.append(new_account)
            print(f"添加新账户: {new_account['name']}, 总数量: {len(self.accounts)}")

            # 保存刷新
            self.save_accounts()
            self.refresh_accounts()
            messagebox.showinfo("成功", "账户添加完成")
            self.show_page("account")

        except Exception as e:
            messagebox.showerror("错误", f"添加失败：{str(e)}")

    def scan_migration_qr_independent(self):
        """扫描迁移二维码"""
        if not MIGRATION_AVAILABLE:
            messagebox.showerror("错误", "缺少迁移模块，请安装google_auth_migration_pb2.py")
            return

        file_path = filedialog.askopenfilename(
            title="选择迁移二维码",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg")]
        )
        if not file_path:
            return

        try:
            # 处理图片
            image = Image.open(file_path).convert("L").resize((300, 300), Image.Resampling.LANCZOS)
            preview = Image.open(file_path).resize((280, 280), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(preview, size=(280, 280))
            self.migrate_scan_preview.configure(image=ctk_img, text="")

            # 解析二维码
            decoded = pyzbar.decode(image)
            if not decoded:
                raise Exception("未识别到二维码")

            # 提取迁移链接
            qr_data = decoded[0].data.decode().strip()
            if not qr_data.startswith("otpauth-migration://"):
                match = re.search(r"otpauth-migration://[^\s]+", qr_data)
                if match:
                    qr_data = match.group(0)
                else:
                    raise Exception("不是有效的迁移二维码")

            # 解析迁移参数
            parsed = urllib.parse.urlparse(qr_data)
            params = urllib.parse.parse_qs(parsed.query)
            if "data" not in params:
                raise Exception("迁移链接中缺少data参数")

            # 解码data参数
            data_str = params["data"][0]
            data_str = urllib.parse.unquote(data_str).replace('-', '+').replace('_', '/')
            padding = 4 - (len(data_str) % 4)
            if padding < 4:
                data_str += '=' * padding
            decoded_data = base64.b64decode(data_str)

            # 解析protobuf数据
            payload = migration_pb.MigrationPayload()
            payload.ParseFromString(decoded_data)
            if not payload.otp_parameters:
                raise Exception("未找到账户数据")

            # 提取TOTP账户
            self.migrate_accounts = []
            for param in payload.otp_parameters:
                if param.type != migration_pb.OtpParameters.TOTP:
                    continue
                secret = base64.b32encode(param.secret).decode().strip()
                self.migrate_accounts.append({
                    "id": hash(secret),
                    "issuer": param.issuer or "未知平台",
                    "name": param.name or "未知账户",
                    "secret": secret
                })

            # 更新UI
            self.migrate_scan_import_btn.configure(state="normal")
            self.migrate_scan_result.configure(
                text=f"✅ 成功解析到 {len(self.migrate_accounts)} 个账户",
                text_color="#4ECDC4"
            )

        except Exception as e:
            error_msg = f"❌ 解析失败：{str(e)}"
            self.migrate_scan_result.configure(
                text=error_msg,
                text_color="#ff6b6b"
            )
            self.migrate_scan_import_btn.configure(state="disabled")

    def import_migrated(self):
        """导入迁移账户"""
        if not self.migrate_accounts:
            messagebox.showwarning("提示", "没有可导入的账户")
            return

        added = 0
        duplicate = 0
        for acc in self.migrate_accounts:
            # 检查重复
            if any(a["secret"] == acc["secret"] for a in self.accounts):
                duplicate += 1
                continue
            try:
                # 添加账户
                self.accounts.append({
                    "id": acc["id"],
                    "issuer": acc["issuer"],
                    "name": acc["name"],
                    "secret": acc["secret"],
                    "totp": pyotp.TOTP(acc["secret"]),
                    "card_elements": None
                })
                added += 1
            except Exception as e:
                messagebox.showerror("错误", f"添加账户 {acc['name']} 失败：{str(e)}")

        # 结果提示
        print(f"导入完成：新增{added}个，重复{duplicate}个，总数量{len(self.accounts)}")
        self.save_accounts()
        self.refresh_accounts()
        messagebox.showinfo(
            "导入完成",
            f"成功添加：{added}个\n已存在：{duplicate}个"
        )
        self.show_page("account")

    def add_manual(self):
        """手动添加账户"""
        platform = self.manual_platform.get().strip()
        account = self.manual_account.get().strip()
        secret = self.manual_secret.get().strip()

        if not all([platform, account, secret]):
            messagebox.showwarning("提示", "请填写完整信息")
            return

        try:
            # 验证密钥
            totp = pyotp.TOTP(secret)

            # 检查重复
            if any(a["secret"] == secret for a in self.accounts):
                messagebox.showinfo("提示", "该账户已存在")
                return

            # 添加账户
            new_account = {
                "id": hash(secret),
                "issuer": platform,
                "name": account,
                "secret": secret,
                "totp": totp,
                "card_elements": None
            }
            self.accounts.append(new_account)
            print(f"手动添加账户: {new_account['name']}, 总数量: {len(self.accounts)}")

            # 清空表单
            self.manual_platform.delete(0, "end")
            self.manual_account.delete(0, "end")
            self.manual_secret.delete(0, "end")

            # 保存刷新
            self.save_accounts()
            self.refresh_accounts()
            messagebox.showinfo("成功", "账户添加完成")
            self.show_page("account")

        except Exception as e:
            messagebox.showerror("错误", f"添加失败：{str(e)}\n请检查密钥格式（Base32）")

    def show_migration_setup_guide(self):
        """迁移模块帮助弹窗"""
        guide = Toplevel(self.root)
        guide.title("迁移功能设置")
        guide.geometry("400x300")
        guide.resizable(False, False)
        guide.configure(bg="#1e1e1e")

        # 标题
        title_font = self._get_font(size=16, weight="bold")
        ctk.CTkLabel(
            guide,
            text="迁移功能需要额外模块",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(pady=10, padx=20, anchor="w")

        # 帮助文本
        text_font = self._get_font(size=12)
        text_widget = Text(
            guide,
            wrap="word",
            height=12,
            width=45,
            bg="#1e1e1e",
            fg=TEXT_WHITE,
            font=(text_font.cget("family"), text_font.cget("size"))
        )
        text_widget.pack(padx=20, pady=10)
        text_widget.insert("1.0", """
迁移功能需要 google_auth_migration_pb2.py 文件，获取方法：

1. 从可信来源下载该文件
2. 放置在与本程序相同的目录下
3. 重启程序即可启用迁移功能

提示：该文件是Google Authenticator迁移协议的
Protobuf定义文件，需确保来源安全。
""")
        text_widget.config(state="disabled")

        # 关闭按钮
        btn_font = self._get_font(size=12, weight="bold")
        ctk.CTkButton(
            guide,
            text="我知道了",
            command=guide.destroy,
            font=btn_font,
            fg_color="#1a73e8"
        ).pack(pady=10)

    def start_timer(self):
        """验证码定时器（30秒刷新）"""
        if self.timer_id:
            self.root.after_cancel(self.timer_id)

        try:
            current_time = time.time()
            remaining = 30 - (int(current_time) % 30)

            # 更新所有账户的进度条和验证码
            for acc in self.accounts:
                if not acc.get("card_elements"):
                    continue
                card_elements = acc["card_elements"]

                # 检查组件有效性
                if not self.is_widget_valid(card_elements.get("card")):
                    acc["card_elements"] = None
                    continue

                # 更新进度条
                if self.is_widget_valid(card_elements.get("progress")):
                    card_elements["progress"].set(remaining / 30)
                    if remaining <= 10:
                        card_elements["progress"].configure(progress_color="#ff6b6b")
                    else:
                        card_elements["progress"].configure(progress_color="#1a73e8")

                # 每30秒刷新验证码
                if int(current_time) % 30 == 0:
                    if self.is_widget_valid(card_elements.get("otp_label")):
                        card_elements["otp_label"].configure(text=acc["totp"].now())

        except Exception as e:
            print(f"定时器错误: {e}")

        # 继续定时
        if self.is_running:
            self.timer_id = self.root.after(1000, self.start_timer)

    def save_accounts(self):
        """保存账户数据"""
        try:
            # 确保目录存在
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)

            # 排除UI元素，仅保存核心数据
            data = [{
                "issuer": acc["issuer"],
                "name": acc["name"],
                "secret": acc["secret"]
            } for acc in self.accounts]

            # 写入文件
            with open(self.save_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def load_accounts(self):
        """加载账户数据"""
        try:
            if os.path.exists(self.save_file):
                with open(self.save_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.accounts = []
                for item in data:
                    try:
                        # 避免重复添加
                        if not any(a["secret"] == item["secret"] for a in self.accounts):
                            self.accounts.append({
                                "id": hash(item["secret"]),
                                "issuer": item["issuer"],
                                "name": item["name"],
                                "secret": item["secret"],
                                "totp": pyotp.TOTP(item["secret"]),
                                "card_elements": None
                            })
                    except Exception as e:
                        messagebox.showwarning("警告", f"加载账户 {item['name']} 失败: {str(e)}")

            self.refresh_accounts()
        except Exception as e:
            messagebox.showerror("错误", f"加载失败: {str(e)}")

    # 托盘功能
    def start_tray(self):
        """启动托盘线程"""
        self.tray_thread = threading.Thread(target=self.create_tray_icon, daemon=True)
        self.tray_thread.start()

    def create_tray_icon(self):
        """创建托盘图标"""
        try:
            # 图标路径
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            tray_icon_path = os.path.join(base_path, "app_icon_B.ico")

            # 加载图标（无图标则用空白）
            if os.path.exists(tray_icon_path):
                tray_image = Image.open(tray_icon_path)
                print(f"✅ 加载托盘图标: {tray_icon_path}")
            else:
                # 创建简单的默认图标
                tray_image = Image.new("RGBA", (64, 64), (30, 30, 46, 255))
                print("⚠️ 未找到托盘图标，使用默认图标")

            # 托盘菜单
            tray_menu = pystray.Menu(
                item("显示Google Authenticator", self.show_main_window, default=True),
                item("退出程序", self.quit_app)
            )

            # 创建托盘
            self.tray_icon = pystray.Icon(
                "GoogleAuthenticator",
                tray_image,
                "Google Authenticator",
                tray_menu
            )
            self.tray_icon.run()

        except Exception as e:
            print(f"托盘创建失败：{e}")

    def minimize_to_tray(self):
        """最小化到托盘"""
        self.root.withdraw()
        if self.tray_icon:
            self.tray_icon.visible = True

    def show_main_window(self):
        """从托盘显示窗口"""
        self.root.after(0, self._show_main_window_ui)

    def _show_main_window_ui(self):
        """主线程显示窗口"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_app(self):
        """退出程序"""
        self.is_running = False
        # 停止托盘
        if self.tray_icon:
            self.tray_icon.stop()
        # 停止定时器
        if self.timer_id:
            self.root.after_cancel(self.timer_id)
        # 销毁窗口
        self.root.after(0, self.root.destroy)

    # 配置管理
    def load_settings(self):
        """加载配置（配置目录）"""
        default_dir = str(Path.home())
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                config_dir = settings.get("config_dir", default_dir)
                # 验证目录有效性
                if os.path.exists(config_dir) and os.access(config_dir, os.W_OK):
                    self.config_dir = config_dir
                else:
                    self.config_dir = default_dir
            else:
                self.config_dir = default_dir

            # 确保目录存在
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir)

        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config_dir = default_dir

    def save_settings(self):
        """保存配置"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump({"config_dir": self.config_dir}, f, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败：{str(e)}")

    def migrate_from_old_location(self):
        """旧配置迁移"""
        if (os.path.exists(self.old_save_file) and
                not os.path.exists(self.save_file) and
                self.config_dir != str(Path.home())):
            try:
                # 读取旧数据
                with open(self.old_save_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                # 写入新目录
                with open(self.save_file, "w", encoding="utf-8") as f:
                    json.dump(old_data, f, ensure_ascii=False, indent=2)
                print(f"配置迁移完成：{self.old_save_file} → {self.save_file}")
                messagebox.showinfo("配置迁移", f"配置已迁移到新目录:\n{self.config_dir}")
            except Exception as e:
                print(f"配置迁移失败: {e}")
                messagebox.showwarning("迁移警告", f"迁移失败: {str(e)}\n可手动复制旧文件到新目录")

    def show_change_config_window(self):
        """更改配置目录弹窗"""
        config_window = Toplevel(self.root)
        config_window.title("更改配置文件目录")
        config_window.geometry("400x220")
        config_window.resizable(False, False)
        config_window.configure(bg="#2d2d2d")
        config_window.transient(self.root)
        config_window.grab_set()

        # 标题
        title_font = self._get_font(size=14, weight="bold")
        ctk.CTkLabel(
            config_window,
            text="请选择配置文件存储目录",
            font=title_font,
            text_color=TEXT_WHITE
        ).pack(padx=20, pady=(15, 10), anchor="w")

        # 路径输入框
        path_frame = ctk.CTkFrame(config_window, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=5)
        entry_font = self._get_font(size=12)
        self.new_config_path = ctk.CTkEntry(
            path_frame,
            font=entry_font,
            text_color=TEXT_WHITE,
            fg_color="#444444",
            border_color="#555555"
        )
        self.new_config_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.new_config_path.insert(0, self.config_dir)

        # 浏览按钮
        btn_font = self._get_font(size=12)
        ctk.CTkButton(
            path_frame,
            text="浏览...",
            command=self.browse_config_dir,
            font=btn_font,
            width=70,
            fg_color="#1a73e8"
        ).pack(side="left")

        # 提示
        hint_font = self._get_font(size=11)
        ctk.CTkLabel(
            config_window,
            text="提示：更改后立即生效",
            font=hint_font,
            text_color=TEXT_MEDIUM_GRAY
        ).pack(padx=20, pady=(5, 20), anchor="w")

        # 按钮区
        btn_frame = ctk.CTkFrame(config_window, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(
            btn_frame,
            text="取消",
            command=config_window.destroy,
            font=btn_font,
            fg_color="#555555",
            height=35
        ).pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(
            btn_frame,
            text="确定",
            command=lambda: self.confirm_change_config(config_window),
            font=btn_font,
            fg_color="#1a73e8",
            height=35
        ).pack(side="left", fill="x", expand=True)

    def browse_config_dir(self):
        """浏览选择目录"""
        selected_dir = filedialog.askdirectory(title="选择配置文件目录")
        if selected_dir:
            self.new_config_path.delete(0, "end")
            self.new_config_path.insert(0, selected_dir)

    def confirm_change_config(self, window):
        """确认更改配置目录"""
        new_dir = self.new_config_path.get().strip()
        if not new_dir:
            messagebox.showwarning("提示", "目录不能为空")
            return
        if not os.path.exists(new_dir):
            try:
                os.makedirs(new_dir)
            except Exception as e:
                messagebox.showerror("错误", f"创建目录失败：{str(e)}")
                return
        if not os.access(new_dir, os.W_OK):
            messagebox.showerror("错误", "没有目录写入权限")
            return

        # 保存旧路径
        old_dir = self.config_dir
        old_save_file = self.save_file

        # 更新配置
        self.config_dir = new_dir
        self.save_file = os.path.join(self.config_dir, ".ubisoft_authenticator.json")
        self.save_settings()

        # 迁移数据
        if os.path.exists(old_save_file) and not os.path.exists(self.save_file):
            try:
                import shutil
                shutil.copy2(old_save_file, self.save_file)
                messagebox.showinfo("成功", f"配置目录已更改并迁移数据到:\n{new_dir}")
            except Exception as e:
                messagebox.showwarning("警告", f"目录已更改，但数据迁移失败：{str(e)}\n请手动复制数据")
        else:
            messagebox.showinfo("成功", f"配置目录已更改到:\n{new_dir}")

        # 重新加载账户
        self.load_accounts()
        self.config_path_label.configure(text=f"当前目录：{self.config_dir}")
        window.destroy()

    def open_config_folder(self):
        """打开配置目录"""
        try:
            if sys.platform.startswith('win'):
                os.startfile(self.config_dir)
            elif sys.platform.startswith('darwin'):
                subprocess.Popen(['open', self.config_dir])
            else:
                subprocess.Popen(['xdg-open', self.config_dir])
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录：{str(e)}")


if __name__ == "__main__":
    # 单例检查
    single_instance = SystemMutexSingleInstance()
    if not single_instance.check():
        messagebox.showinfo("提示", "程序已在运行中")
        sys.exit(0)

    # 启动应用
    root = ctk.CTk()
    app = GoogleAuthenticator(root)
    root.mainloop()