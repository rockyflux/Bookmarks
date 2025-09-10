
def parse_bookmark_html(html_content):
    """解析书签HTML文件并转换为指定格式"""
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 从原始HTML中提取标题
    original_title = soup.title.string if soup.title else "书签导航"

    # 找到所有的DT元素
    all_dt_tags = soup.find_all('dt')

    categories = []
    processed_links = set() # 用于存储已处理的链接，格式为 (text, href)
    processed_category_titles = set() # 用于存储已处理的分类标题

    # 遍历所有DT标签
    for dt_tag in all_dt_tags:
        h3_tag = dt_tag.find('h3')
        a_tag = dt_tag.find('a')
        
        if h3_tag:
            title = h3_tag.get_text().strip()
            
            # 跳过顶层无意义的收藏夹标题
            if title.lower() in ["bookmarks", "收藏夹", "收藏栏", "书签栏"]:
                continue
            
            # 检查分类是否重复
            if title not in processed_category_titles:
                # 简化逻辑：所有H3都视为一级分类
                current_category = {
                    'title': title,
                    'links': []
                }
                categories.append(current_category)
                processed_category_titles.add(title)
                
        elif a_tag:
            href = a_tag.get('href', '')
            text = a_tag.get_text().strip()
            if href and text:
                link_tuple = (text, href)
                if link_tuple not in processed_links:
                    if categories: # 确保有分类可以添加链接
                        categories[-1]['links'].append(link_tuple)
                        processed_links.add(link_tuple)

    # 生成导航HTML
    nav_html = '<ul>'
    for cat in categories:
        anchor_id = re.sub(r'[^\w\u4e00-\u9fff]', '', cat["title"])
        nav_html += f'<li><a href="#{anchor_id}">{cat["title"]}</a></li>'
    nav_html += '</ul>'
    
    # 生成内容HTML
    content_html = ''
    for cat in categories:
        anchor_id = re.sub(r'[^\w\u4e00-\u9fff]', '', cat["title"])
        content_html += f'<h2 id="{anchor_id}">{cat["title"]}</h2>'
        if cat['links']:
            content_html += '<ol>'
            for link_text, link_url in cat['links']:
                content_html += f'<li>{link_text}：<a href="{link_url}" target="_blank">{link_url}</a></li>'
            content_html += '</ol>'

    # 构建完整的HTML
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{original_title}</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #ffffff;
            height: 100vh;
            overflow: hidden;
        }}
        
        /* 固定头部样式 */
        .header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            align-items: center;
            padding: 0 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
        }}
        
        .header .icon {{
            margin-right: 12px;
            font-size: 24px;
        }}
        
        .container {{
            display: flex;
            width: 100%;
            height: 100vh;
            padding-top: 60px; /* 为固定头部留出空间 */
        }}
        
        .navigation-panel {{
            width: 300px;
            flex-shrink: 0;
            background: #f8f9fa;
            padding: 20px;
            box-sizing: border-box;
            overflow-y: auto;
            border-right: 1px solid #e9ecef;
            box-shadow: 2px 0 4px rgba(0,0,0,0.1);
            height: calc(100vh - 60px);
        }}
        
        .navigation-panel h2 {{
            margin-top: 0;
            color: #212529;
            border-bottom: 2px solid #007bff;
            padding-bottom: 8px;
            margin-bottom: 20px;
            font-size: 18px;
            font-weight: 600;
        }}
        
        #nav-search {{
            width: 100%;
            padding: 10px 12px;
            margin-bottom: 20px;
            border: 1px solid #ced4da;
            border-radius: 6px;
            box-sizing: border-box;
            font-size: 14px;
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }}
        
        #nav-search:focus {{
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25);
        }}
        
        .nav-tree ul {{
            list-style: none;
            padding-left: 0;
            margin: 0;
        }}
        
        .nav-tree li {{
            margin: 3px 0;
        }}
        
        .nav-tree li a {{
            text-decoration: none;
            color: #495057;
            display: block;
            padding: 8px 12px;
            border-radius: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 14px;
            transition: all 0.2s ease;
        }}
        
        .nav-tree li a:hover {{
            background-color: #e9ecef;
            color: #007bff;
            text-decoration: none;
        }}
        
        .nav-tree li.hidden {{
            display: none;
        }}
        
        .content-panel {{
            flex-grow: 1;
            padding: 30px;
            box-sizing: border-box;
            overflow-y: auto;
            background-color: #ffffff;
            height: calc(100vh - 60px);
        }}
        
        .content-panel h2, .content-panel h3, .content-panel h4, .content-panel h5, .content-panel h6 {{
            color: #212529;
            border-bottom: 2px solid #007bff;
            padding-bottom: 8px;
            margin-top: 40px;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        
        .content-panel h2:first-child {{
            margin-top: 0;
        }}
        
        .content-panel ol {{
            margin-bottom: 25px;
            padding-left: 20px;
        }}
        
        .content-panel li {{
            margin-bottom: 8px;
            line-height: 1.6;
        }}
        
        .content-panel li a {{
            color: #007bff;
            text-decoration: none;
            word-break: break-all;
        }}
        
        .content-panel li a:hover {{
            text-decoration: underline;
        }}
        
        #scrollToTopBtn {{
            display: none;
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 99;
            border: none;
            outline: none;
            background-color: #007bff;
            color: white;
            cursor: pointer;
            padding: 15px;
            border-radius: 10px;
            font-size: 18px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: background-color 0.3s, transform 0.3s;
        }}
        
        #scrollToTopBtn:hover {{
            background-color: #0056b3;
            transform: translateY(-2px);
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 16px;
            }}
            
            .header .icon {{
                font-size: 20px;
                margin-right: 8px;
            }}
            
            .container {{
                flex-direction: column;
            }}
            
            .navigation-panel {{
                width: 100%;
                height: auto;
                max-height: 40vh; /* Limit height on mobile */
                border-right: none;
                border-bottom: 1px solid #e9ecef;
            }}
            
            .content-panel {{
                padding: 20px;
                height: auto;
            }}
            
            #scrollToTopBtn {{
                bottom: 20px;
                right: 20px;
                padding: 12px;
                font-size: 16px;
            }}
        }}
        
        .navigation-panel::-webkit-scrollbar, .content-panel::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .navigation-panel::-webkit-scrollbar-track, .content-panel::-webkit-scrollbar-track {{
            background: #f1f1f1;
        }}
        
        .navigation-panel::-webkit-scrollbar-thumb, .content-panel::-webkit-scrollbar-thumb {{
            background: #c1c1c1;
            border-radius: 3px;
        }}
        
        .navigation-panel::-webkit-scrollbar-thumb:hover, .content-panel::-webkit-scrollbar-thumb:hover {{
            background: #a8a8a8;
        }}
    </style>
</head>
<body>
    <!-- 固定头部 -->
    <div class="header">
        <h1>
            <span class="icon">📚</span>
            {original_title}
        </h1>
    </div>
    
    <div class="container">
        <div class="navigation-panel">
            <h2>📚 目录导航</h2>
            <input type="text" id="nav-search" placeholder="🔍 搜索导航...">
            <div class="nav-tree">
                {nav_html}
            </div>
        </div>
        <div class="content-panel">
            {content_html}
        </div>
    </div>
    <button onclick="scrollToTop()" id="scrollToTopBtn" title="回到顶部">⬆️</button>

    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            const navSearch = document.getElementById("nav-search");
            const navTree = document.querySelector(".nav-tree");
            const navLinks = navTree.querySelectorAll("a");
            const contentPanel = document.querySelector(".content-panel");
            const scrollToTopBtn = document.getElementById("scrollToTopBtn");

            // 搜索功能
            navSearch.addEventListener("keyup", function() {{
                const searchTerm = navSearch.value.toLowerCase().trim();

                // Show all if search term is empty
                if (searchTerm === "") {{
                    navTree.querySelectorAll("li").forEach(li => li.classList.remove("hidden"));
                    return;
                }}

                // Hide all initially
                navTree.querySelectorAll("li").forEach(li => li.classList.add("hidden"));

                navLinks.forEach(link => {{
                    const text = link.textContent.toLowerCase();
                    const listItem = link.closest("li");

                    if (text.includes(searchTerm)) {{
                        listItem.classList.remove("hidden");
                        // Show parent categories as well (not strictly needed with simplified menu, but good for robustness)
                        let parent = listItem.parentElement.closest("li");
                        while(parent) {{
                            parent.classList.remove("hidden");
                            parent = parent.parentElement.closest("li");
                        }}
                    }}
                }});
            }});

            // 平滑滚动导航
            navLinks.forEach(link => {{
                link.addEventListener("click", function(e) {{
                    e.preventDefault();
                    const targetId = this.getAttribute("href").substring(1);
                    const targetElement = document.getElementById(targetId);
                    if (targetElement) {{
                        contentPanel.scrollTo({{
                            top: targetElement.offsetTop - contentPanel.offsetTop, 
                            behavior: "smooth"
                        }});
                        
                        // 高亮当前选中的导航项
                        navLinks.forEach(l => {{
                            l.style.backgroundColor = "";
                            l.style.color = "";
                        }});
                        this.style.backgroundColor = "#007bff";
                        this.style.color = "#ffffff";
                        
                        // 3秒后恢复原样
                        setTimeout(() => {{
                            this.style.backgroundColor = "";
                            this.style.color = "";
                        }}, 3000);
                    }}
                }});
            }});

            // Scroll to Top button logic
            contentPanel.addEventListener("scroll", function() {{
                if (contentPanel.scrollTop > 20) {{
                    scrollToTopBtn.style.display = "block";
                }} else {{
                    scrollToTopBtn.style.display = "none";
                }}
            }});

            window.scrollToTop = function() {{
                contentPanel.scrollTo({{
                    top: 0, 
                    behavior: "smooth" 
                }});
            }};

            // 键盘快捷键支持
            document.addEventListener("keydown", function(e) {{
                if (e.ctrlKey && e.key === "f") {{
                    e.preventDefault();
                    navSearch.focus();
                }}
            }});
        }});
    </script>
</body>
</html>"""

    return html_template

def main():
    try:
        import os
        
        # 提示用户输入HTML文件路径
        input_file = input("请输入HTML书签文件的完整路径（例如：C:\\Users\\YourUser\\Downloads\\bookmarks.html）：")
        
        # 确保路径在Windows上也能正确处理
        input_file = os.path.normpath(input_file)

        # 获取输入文件所在的目录
        output_dir = os.path.dirname(input_file)
        # 构造输出文件名，在原文件名后添加_converted
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_tree.html")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        converted_html = parse_bookmark_html(html_content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(converted_html)
        
        print(f"转换完成！输出文件已保存到：{output_file}")
        print("功能特性：")
        print("- 左右分栏布局，类似Word文档导航")
        print("- 支持导航搜索功能")
        print("- 平滑滚动定位")
        print("- 响应式设计，支持移动设备")
        print("- 现代化UI设计")
        print("- 键盘快捷键支持（Ctrl+F 聚焦搜索框）")
        print("- 新增回到顶部按钮")
        print("- 头部标题显示书签文件名")
        print("- 链接去重")
        print("- 简化左侧菜单，只显示一级分类")
        print("- 目录去重")
    
    except Exception as e:
        import sys
        print(f"转换过程中发生错误：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


