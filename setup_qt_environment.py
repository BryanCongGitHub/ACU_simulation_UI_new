import sys
import os
from pathlib import Path


def setup_qt_environment():
    """设置Qt环境，解决平台插件问题 - 打包专用版本"""

    # 禁用内部qt.conf，使用我们自己的配置
    os.environ["PYSIDE_DISABLE_INTERNAL_QT_CONF"] = "1"

    if hasattr(sys, "_MEIPASS"):
        # 运行在打包环境中
        base_path = sys._MEIPASS
        print(f"打包环境 - MEIPASS: {base_path}")

        # 设置插件路径
        plugin_path = os.path.join(base_path, "PySide6", "plugins")
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

        # 设置其他Qt相关路径
        os.environ["QT_PLUGIN_PATH"] = plugin_path
        os.environ["QML2_IMPORT_PATH"] = os.path.join(base_path, "PySide6", "qml")

        print(f"设置的插件路径: {plugin_path}")

        # 检查插件是否存在
        platforms_path = os.path.join(plugin_path, "platforms")
        if os.path.exists(platforms_path):
            print(f"找到平台插件目录: {platforms_path}")
            plugins = os.listdir(platforms_path)
            print(f"平台插件: {plugins}")
        else:
            print(f"警告: 未找到平台插件目录: {platforms_path}")

    else:
        # 运行在开发环境中
        try:
            import PySide6

            pyside6_dir = Path(PySide6.__file__).parent
            plugin_path = pyside6_dir / "plugins"

            if plugin_path.exists():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_path)
                os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
                print(f"开发环境 - Qt插件路径: {plugin_path}")
            else:
                print("警告: 未找到Qt插件路径")

        except ImportError as e:
            print(f"无法导入PySide6: {e}")
            sys.exit(1)


# 在导入任何PySide6模块之前调用
setup_qt_environment()

# 调试信息
print("=== Qt环境设置完成 ===")
qt_platform_path = os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "未设置")
print(f"QT_QPA_PLATFORM_PLUGIN_PATH: {qt_platform_path}")
qt_plugin_path = os.environ.get("QT_PLUGIN_PATH", "未设置")
print(f"QT_PLUGIN_PATH: {qt_plugin_path}")
