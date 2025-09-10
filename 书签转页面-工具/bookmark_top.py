"""解析书签HTML文件并转换为指定格式"""
def parse_bookmark_html(html_content):
    """解析书签HTML文件并转换为指定格式"""
    from bs4 import BeautifulSoup
    import re
    import os
    import sys

    soup = BeautifulSoup(html_content, 'html.parser')
    
    result_html = []
    result_html.append('<!DOCTYPE html>')
    result_html.append('<html lang="zh-CN">')
    result_html.append('<head>')
    result_html.append('<meta charset="UTF-8">')
    result_html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    
    # 从原始HTML中提取标题
    original_title = soup.title.string if soup.title else "书签导航"
    result_html.append(f'<title>{original_title}</title>')
    
    result_html.append('<style>')
    result_html.append('body { font-family: Arial, sans-serif; margin: 20px; }')
    result_html.append('.toc { background: #f5f5f5; padding: 15px; margin-bottom: 20px; border-radius: 5px; }')
    result_html.append('.toc h2 { margin-top: 0; }')
    result_html.append('.toc a { text-decoration: none; color: #0066cc; display: inline-block; margin: 5px 0; }')
    result_html.append('.toc a:hover { text-decoration: underline; }')
    result_html.append('.toc-h3 { padding-left: 20px; }')  # 子分类缩进
    result_html.append('h2 { color: #333; border-bottom: 2px solid #0066cc; padding-bottom: 5px; }')
    result_html.append('h3 { color: #666; margin-top: 25px; }')
    result_html.append('ol { margin-bottom: 20px; }')
    result_html.append('li { margin-bottom: 5px; }')
    result_html.append('</style>')

    result_html.append('</head>')
    result_html.append('<body>')
    
    # 找到所有的DT元素
    all_dt_tags = soup.find_all('dt')

    categories = []
    current_category = None
    current_parent_category = None  # 记录当前父分类
    
    # 遍历所有DT标签
    for dt_tag in all_dt_tags:
        h3_tag = dt_tag.find('h3')
        a_tag = dt_tag.find('a')
        
        if h3_tag:
            # 这是一个分类标题
            title = h3_tag.get_text().strip()
            
            # 跳过顶层无意义的收藏夹标题
            if title.lower() in ["bookmarks", "收藏夹", "收藏栏", "书签栏"]:
                continue
            
            # 判断层级：通过检查H3的父DL的层级来判断
            parent_dl = h3_tag.find_parent('dl')
            is_main_category = False
            if parent_dl and parent_dl.find_parent('dl') is None:  # 顶层DL下的分类
                is_main_category = True
                current_parent_category = title  # 更新当前父分类
            else:
                # 子分类，使用父分类+子分类作为唯一标识
                pass

            # 生成唯一标识：主分类-子分类（如果是子分类）
            unique_id = title if is_main_category else f"{current_parent_category}-{title}"
            
            # 检查是否重复（通过唯一标识判断）
            if any(cat['unique_id'] == unique_id for cat in categories):
                continue

            current_category = {
                'title': title,
                'unique_id': unique_id,  # 用于判断重复的唯一标识
                'tag_type': 'h2' if is_main_category else 'h3',
                'links': [],
                'anchor': re.sub(r'[^\w\u4e00-\u9fff]', '', unique_id)  # 基于唯一标识生成锚点ID
            }
            categories.append(current_category)

            
        elif a_tag and current_category:
            # 这是一个链接，添加到当前分类下
            href = a_tag.get('href', '')
            text = a_tag.get_text().strip()
            if href and text:
                current_category['links'].append((text, href))

    # 生成目录 - 遍历所有分类
    result_html.append('<div class="toc">')
    result_html.append('<h2>目录</h2>')
    result_html.append('<div class="toc-content">')  # 目录内容容器
    
    # 遍历所有分类，包括h2和h3
    for cat in categories:
        if cat['tag_type'] == 'h2':
            # 顶级分类
            result_html.append(f'<a href="#{cat["anchor"]}">{cat["title"]}</a>')
        else:
            # 子分类，添加缩进样式
            result_html.append(f'<a href="#{cat["anchor"]}" class="toc-h3">{cat["title"]}</a>')
    
    result_html.append('</div>')  # 关闭目录内容容器
    result_html.append('</div>')  # 关闭toc
    
    # 生成内容
    for cat in categories:
        if cat['tag_type'] == 'h2':
            result_html.append(f'<h2 id="{cat["anchor"]}">{cat["title"]}</h2>')
        else:
            result_html.append(f'<h3 id="{cat["anchor"]}">{cat["title"]}</h3>')
        
        if cat['links']:
            result_html.append('<ol>')
            for link_text, link_url in cat['links']:
                result_html.append(f'<li>{link_text}：<a href="{link_url}" target="_blank">{link_url}</a></li>')
            result_html.append('</ol>')
    
    result_html.append('</body>')
    result_html.append('</html>')
    
    return '\n'.join(result_html)


def main():
    try:
        import os
        import sys
        # 提示用户输入文件路径
        input_file = input("请输入书签HTML文件的完整路径：")
        
        # 检查文件是否存在
        if not os.path.exists(input_file):
            print(f"错误：文件不存在：{input_file}")
            sys.exit(1)
        
        # 检查文件是否为HTML
        if not input_file.lower().endswith('.html'):
            print("错误：文件类型不是HTML文件。")
            sys.exit(1)

        # 确定输出文件路径
        output_dir = os.path.dirname(input_file)
        input_filename_without_ext = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{input_filename_without_ext}_top.html")
        
        # 读取、转换和写入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        converted_html = parse_bookmark_html(html_content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(converted_html)
        
        print(f"转换完成！输出文件已保存到：{output_file}")
    
    except Exception as e:
        print(f"转换过程中发生错误：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()