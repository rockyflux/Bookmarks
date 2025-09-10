
"""解析书签HTML文件并转换为Markdown格式"""
from bs4 import BeautifulSoup
import re
import os
import sys

def parse_bookmark_html_to_markdown(html_content):
    """解析书签HTML文件并转换为Markdown格式"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    result_md = []
    
    # 从原始HTML中提取标题
    original_title = soup.title.string if soup.title else "书签导航"
    result_md.append(f"# {original_title}\n")
    
    all_dt_tags = soup.find_all('dt')

    categories = []
    current_category = None
    current_parent_category = ""  # 初始化为空字符串
    
    for dt_tag in all_dt_tags:
        h3_tag = dt_tag.find('h3')
        a_tag = dt_tag.find('a')
        
        if h3_tag:
            title = h3_tag.get_text().strip()
            
            if title.lower() in ["bookmarks", "收藏夹", "收藏栏", "书签栏"]:
                continue
            
            parent_dl = h3_tag.find_parent('dl')
            is_main_category = False
            if parent_dl and parent_dl.find_parent('dl') is None:
                is_main_category = True
                current_parent_category = title
            else:
                pass

            # 修正 unique_id 的生成逻辑，避免 None
            if is_main_category:
                unique_id = title
            elif current_parent_category:
                unique_id = f"{current_parent_category}-{title}"
            else:
                unique_id = title # 如果没有父分类，就直接用当前标题

            # 确保锚点ID只包含字母、数字、中文和下划线，并替换空格为连字符
            # 修正：将所有非字母数字下划线和中文的字符替换为连字符，并处理连续连字符和首尾连字符
            anchor_id = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]+', '-', unique_id).strip('-').lower()
            
            if any(cat['unique_id'] == unique_id for cat in categories):
                continue

            current_category = {
                'title': title,
                'unique_id': unique_id,
                'tag_type': 'h2' if is_main_category else 'h3',
                'links': [],
                'anchor': anchor_id
            }
            categories.append(current_category)

            
        elif a_tag and current_category:
            href = a_tag.get('href', '')
            text = a_tag.get_text().strip()
            if href and text:
                current_category['links'].append((text, href))

    # 生成目录
    result_md.append("## 目录\n")
    for cat in categories:
        if cat['tag_type'] == 'h2':
            result_md.append(f"- [{cat['title']}](#{cat['anchor']})")
        else:
            result_md.append(f"  - [{cat['title']}](#{cat['anchor']})")
    result_md.append("\n")
    
    # 生成内容
    for cat in categories:
        if cat['tag_type'] == 'h2':
            result_md.append(f"## {cat['title']}\n")
        else:
            result_md.append(f"### {cat['title']}\n")
        
        if cat['links']:
            for link_text, link_url in cat['links']:
                result_md.append(f"- [{link_text}]({link_url})")
            result_md.append("\n")
    
    return '\n'.join(result_md)


def main():
    try:
        input_file = input("请输入书签HTML文件的完整路径：")
        
        if not os.path.exists(input_file):
            print(f"错误：文件不存在：{input_file}")
            sys.exit(1)
        
        if not input_file.lower().endswith('.html'):
            print("错误：文件类型不是HTML文件。")
            sys.exit(1)

        output_dir = os.path.dirname(input_file)
        input_filename_without_ext = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{input_filename_without_ext}.md")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        converted_md = parse_bookmark_html_to_markdown(html_content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(converted_md)
        
        print(f"转换完成！输出文件已保存到：{output_file}")
    
    except Exception as e:
        print(f"转换过程中发生错误：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


