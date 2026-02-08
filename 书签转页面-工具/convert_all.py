#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一键将书签 HTML 转为三种格式：_top.html（简洁版）、_tree.html（增强版）、.md（Markdown）。
用法：
  python convert_all.py                    # 提示输入文件路径
  python convert_all.py 路径/xxx.html      # 转换单个文件
  python convert_all.py 路径/目录          # 转换目录下所有书签 HTML（不含 _top/_tree 的 .html）
"""

import os
import sys

# 保证从本脚本所在目录能导入 bookmark_*.py（支持在仓库根目录执行）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

# 从同目录下的三个模块导入转换函数（两个重名，用别名）
from bookmark_tree import parse_bookmark_html as parse_to_tree
from bookmark_top import parse_bookmark_html as parse_to_top
from bookmark_md import parse_bookmark_html_to_markdown as parse_to_md


def convert_one(input_file, output_dir=None):
    """将单个书签 HTML 转为 _top.html、_tree.html、.md，输出到同目录或指定目录。"""
    input_file = os.path.normpath(input_file)
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"文件不存在：{input_file}")
    if not input_file.lower().endswith(".html"):
        raise ValueError("请指定 .html 书签文件")

    if output_dir is None:
        output_dir = os.path.dirname(input_file)
    else:
        output_dir = os.path.normpath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    with open(input_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    # 三种输出
    out_top = os.path.join(output_dir, f"{base_name}_top.html")
    out_tree = os.path.join(output_dir, f"{base_name}_tree.html")
    out_md = os.path.join(output_dir, f"{base_name}.md")

    with open(out_top, "w", encoding="utf-8") as f:
        f.write(parse_to_top(html_content))
    with open(out_tree, "w", encoding="utf-8") as f:
        f.write(parse_to_tree(html_content))
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(parse_to_md(html_content))

    return out_top, out_tree, out_md


def collect_html_files(dir_path):
    """收集目录下可作为“源书签”的 .html 文件（排除已是 _top / _tree 输出的）。"""
    dir_path = os.path.normpath(dir_path)
    if not os.path.isdir(dir_path):
        return []
    result = []
    for name in os.listdir(dir_path):
        if not name.lower().endswith(".html"):
            continue
        # 跳过已经是转换产物的文件
        base = name[:-5]  # 去掉 .html
        if base.endswith("_top") or base.endswith("_tree"):
            continue
        result.append(os.path.join(dir_path, name))
    return sorted(result)


def main():
    if len(sys.argv) > 1:
        path = os.path.normpath(sys.argv[1])
    else:
        path = input("请输入书签 HTML 文件或目录路径：").strip()
        if not path:
            print("未输入路径，已退出。")
            sys.exit(0)
        path = os.path.normpath(path)

    if not os.path.exists(path):
        print(f"错误：路径不存在：{path}")
        sys.exit(1)

    if os.path.isfile(path):
        files = [path]
    else:
        files = collect_html_files(path)
        if not files:
            print(f"目录下没有可转换的书签 HTML 文件：{path}")
            sys.exit(0)
        print(f"在目录中发现 {len(files)} 个书签 HTML，将逐一转为三种格式。\n")

    ok = 0
    for input_file in files:
        try:
            out_top, out_tree, out_md = convert_one(input_file)
            ok += 1
            print(f"[{ok}/{len(files)}] {os.path.basename(input_file)}")
            print(f"    → {os.path.basename(out_top)}")
            print(f"    → {os.path.basename(out_tree)}")
            print(f"    → {os.path.basename(out_md)}")
        except Exception as e:
            print(f"跳过 {input_file}：{e}")

    if ok:
        print(f"\n全部完成，共转换 {ok} 个文件。")
    else:
        print("没有成功转换任何文件。")
        sys.exit(1)


if __name__ == "__main__":
    main()
