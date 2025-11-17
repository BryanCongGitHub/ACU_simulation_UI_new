import sys
import os
import io
import pyqtgraph as pg

pg.setConfigOptions(useOpenGL=False)


# 解决中文乱码问题
def setup_encoding():
    """设置编码为UTF-8"""
    # 设置环境变量
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # 设置标准输出编码
    if sys.stdout.encoding != "UTF-8":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    if sys.stderr.encoding != "UTF-8":
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

    # 尝试设置控制台编码（Windows）
    if os.name == "nt":
        try:
            import subprocess

            subprocess.run(["chcp", "65001"], shell=True, capture_output=True)
        except Exception:
            pass


# 在程序开始时调用
setup_encoding()

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from app.bootstrap import run

    if __name__ == "__main__":
        print("正在启动ACU仿真器...")
        exit_code = run(sys.argv)
        sys.exit(exit_code)

except Exception as e:
    print(f"启动失败: {e}")
    import traceback

    traceback.print_exc()
    input("按Enter键退出...")
