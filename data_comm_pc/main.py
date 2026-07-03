# -*- coding: utf-8 -*-
"""
地面站程序入口
仅负责路径初始化和启动应用，所有模块装配逻辑由AppAssembler统一管理
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.app_assembler import AppAssembler


def main():
    assembler = AppAssembler()
    try:
        exit_code = assembler.run()
        sys.exit(exit_code)
    finally:
        assembler.shutdown()


if __name__ == "__main__":
    main()
