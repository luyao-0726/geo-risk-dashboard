import sys
import importlib

print("环境ok")
print(f"Python version: {sys.version}")

# 检查 pandas 是否安装
pandas_installed = importlib.util.find_spec("pandas") is not None
if pandas_installed:
    print("pandas is installed.")
else:
    print("pandas is NOT installed.")
