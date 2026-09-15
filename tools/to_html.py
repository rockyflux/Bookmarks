def parse_bookmark_html(html_content, page_title=None, home_href="../index.html"):
    """解析书签 HTML，生成 Pintree / LoloNav 风格的多级树导航页面。

    page_title: 侧栏品牌名 / 页面标题；缺省时从书签目录树推断。
    home_href: 点击品牌区返回的首页链接。
    """
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse
    import html as html_lib
    import json
    import re

    soup_title = BeautifulSoup(html_content, 'html.parser')
    raw_doc_title = soup_title.title.string if soup_title.title else ""
    raw_doc_title = str(raw_doc_title).strip() if raw_doc_title else ""

    SKIP_TITLES = {
        "bookmarks", "bookmarks bar", "收藏夹", "收藏栏", "书签栏", "收藏夹栏",
        "其他书签", "other bookmarks", "mobile bookmarks",
        "从html文件导入", "从 html 文件导入",
    }

    GENERIC_TITLES = {
        "", "bookmarks", "bookmark", "书签", "书签导航", "favorites", "favourite",
    }

    def host_of(url):
        if url.startswith(('javascript:', 'data:', 'about:')):
            return ''
        try:
            return urlparse(url).netloc or url
        except Exception:
            return url

    def favicon_url(href, icon):
        if icon and (icon.startswith('data:') or icon.startswith('http')):
            return icon
        host = host_of(href)
        if not host:
            return ''
        return f'https://icons.duckduckgo.com/ip3/{html_lib.escape(host)}.ico'

    def slug(title):
        s = re.sub(r'[^\w\u4e00-\u9fff]', '', title)
        return s or 'cat'

    def plain(text):
        # 去掉标签与实体，避免对纯文本/URL 触发 BeautifulSoup 警告
        text = re.sub(r'<[^>]+>', '', text)
        return html_lib.unescape(text).strip()

    def separator_host(href):
        if not href:
            return ''
        try:
            return (urlparse(href).netloc or '').lower()
        except Exception:
            return ''

    def separator_kind(href):
        """
        书签分隔符类型：
        - folder: separator.site → 提升为虚拟子分类
        - inline: separator.mayastudios.com 等 → 通栏分组标题
        """
        host = separator_host(href)
        if not host:
            return None
        if host == 'separator.site' or host.endswith('.separator.site'):
            return 'folder'
        if host == 'separator.mayastudios.com' or host.startswith('separator.'):
            return 'inline'
        return None

    def is_folder_separator(href):
        return separator_kind(href) == 'folder'

    def separator_title(text):
        """去掉 ═ / ─ / — 等装饰边框，得到可读分类名；纯装饰则返回空。"""
        # 含 box-drawing、em/en dash、全角连字符等常见分隔符字符
        t = re.sub(
            r'^[\s\-_=═─—–―－]+|[\s\-_=═─—–―－]+$',
            '',
            text or '',
        ).strip()
        return t

    # Netscape 书签格式：用事件栈解析（BeautifulSoup 会弄乱 DL/DT 层级）
    events = []
    for m in re.finditer(
        r'<DL\b[^>]*>|</DL>|<DT>\s*<H3\b[^>]*>.*?</H3>|<DT>\s*<A\s+[^>]*>.*?</A>',
        html_content,
        re.I | re.S,
    ):
        s = m.group(0)
        if re.match(r'<DL\b', s, re.I):
            events.append(('dl_open',))
        elif re.match(r'</DL>', s, re.I):
            events.append(('dl_close',))
        elif re.match(r'<DT>\s*<H3', s, re.I):
            title = plain(re.search(r'<H3\b[^>]*>(.*?)</H3>', s, re.I | re.S).group(1))
            events.append(('folder', title))
        else:
            am = re.search(r'<A\s+([^>]*)>(.*?)</A>', s, re.I | re.S)
            attrs, text = am.group(1), plain(am.group(2))
            href_m = re.search(r'HREF\s*=\s*"([^"]*)"', attrs, re.I)
            href = href_m.group(1) if href_m else ''
            icon_m = re.search(r'ICON\s*=\s*"([^"]*)"', attrs, re.I)
            icon = icon_m.group(1) if icon_m else ''
            events.append(('link', text, href, icon))

    # items 保留文件夹与链接的原始顺序，便于把 separator 提升为子分类
    root = {'title': 'root', 'items': []}
    stack = [root]
    i = 0
    while i < len(events):
        e = events[i]
        if e[0] == 'folder':
            node = {'title': e[1], 'items': []}
            stack[-1]['items'].append(('folder', node))
            if i + 1 < len(events) and events[i + 1][0] == 'dl_open':
                stack.append(node)
                i += 2
                continue
            i += 1
        elif e[0] == 'dl_open':
            i += 1
        elif e[0] == 'dl_close':
            if len(stack) > 1:
                stack.pop()
            i += 1
        else:
            text, href, icon = e[1], e[2], e[3]
            if href and text:
                stack[-1]['items'].append(('link', {'text': text, 'href': href, 'icon': icon}))
            i += 1

    def expand_separators(node):
        """将 separator.site 书签提升为虚拟子目录，收纳其后直到下一个命名 folder 分隔符的同级项。"""
        items = node.get('items') or []
        for kind, payload in items:
            if kind == 'folder':
                expand_separators(payload)

        out = []
        i = 0
        while i < len(items):
            kind, payload = items[i]
            if kind == 'link' and is_folder_separator(payload['href']):
                title = separator_title(payload['text'])
                i += 1
                if not title:
                    continue  # 纯装饰线，丢弃
                group_items = []
                while i < len(items):
                    k2, p2 = items[i]
                    if k2 == 'link' and is_folder_separator(p2['href']):
                        if separator_title(p2['text']):
                            break  # 下一个命名分隔符
                        i += 1  # 组内装饰线跳过
                        continue
                    group_items.append(items[i])
                    i += 1
                if not group_items:
                    continue
                group = {'title': title, 'items': group_items}
                expand_separators(group)
                out.append(('folder', group))
            else:
                out.append(items[i])
                i += 1
        node['items'] = out

    def materialize(node):
        """items → children / links，供导航与卡片渲染使用。"""
        children, links = [], []
        for kind, payload in node.get('items') or []:
            if kind == 'folder':
                materialize(payload)
                children.append(payload)
            elif kind == 'link':
                sk = separator_kind(payload['href'])
                if sk == 'folder':
                    continue  # 已在 expand 中处理；残留则丢弃
                if sk == 'inline':
                    title = separator_title(payload['text'])
                    if title:
                        links.append({
                            'text': title,
                            'href': payload['href'],
                            'icon': '',
                            'kind': 'heading',
                        })
                    continue
                links.append(payload)
        node['children'] = children
        node['links'] = links

    expand_separators(root)
    materialize(root)

    def unwrap_skip(nodes):
        """跳过书签栏等根目录，提升其子节点。"""
        result = []
        for n in nodes:
            if n['title'].lower() in SKIP_TITLES:
                result.extend(unwrap_skip(n['children']) if n['children'] else [])
                # 根目录自身链接并入未分类（少见）
                if n['links']:
                    result.append({
                        'title': n['title'] or '未分类',
                        'children': [],
                        'links': n['links'],
                    })
            else:
                result.append(n)
        return result

    tree = unwrap_skip(root['children'])

    # 一级只有一个且无直属链接时，连续提升子目录（去掉空壳包装层，如 玩机→软件相关）
    # 同时记录被剥掉的外壳名，用作品牌标题
    shell_titles = []
    while len(tree) == 1 and tree[0]['children'] and not tree[0]['links']:
        shell_titles.append(tree[0]['title'])
        tree = tree[0]['children']

    def pick_brand_title():
        if page_title and str(page_title).strip():
            return str(page_title).strip()
        if shell_titles:
            return shell_titles[-1]
        if len(tree) == 1 and tree[0]['title']:
            return tree[0]['title']
        if raw_doc_title and raw_doc_title.lower() not in GENERIC_TITLES:
            return raw_doc_title
        return "书签导航"

    brand_title = pick_brand_title()
    brand_title_esc = html_lib.escape(brand_title)
    home_href_esc = html_lib.escape(home_href or "../index.html", quote=True)

    # 链接去重（全局），保留首次出现
    seen = set()

    def dedupe(nodes):
        for n in nodes:
            kept = []
            for link in n['links']:
                if link.get('kind') == 'heading':
                    kept.append(link)
                    continue
                key = (link['text'], link['href'])
                if key in seen:
                    continue
                seen.add(key)
                kept.append(link)
            n['links'] = kept
            dedupe(n['children'])

    dedupe(tree)

    # 分配稳定 id
    def assign_ids(nodes, prefix):
        for idx, n in enumerate(nodes):
            n['id'] = f"{prefix}-{idx}-{slug(n['title'])}"
            assign_ids(n['children'], n['id'])

    assign_ids(tree, 'n')

    def real_link_count(links):
        return sum(1 for link in links if link.get('kind') != 'heading')

    def count_links(node):
        return real_link_count(node['links']) + sum(count_links(c) for c in node['children'])

    def flatten(nodes, parent_id=None, depth=0, acc=None):
        if acc is None:
            acc = []
        for n in nodes:
            acc.append({**n, 'parent_id': parent_id, 'depth': depth})
            flatten(n['children'], n['id'], depth + 1, acc)
        return acc

    flat = flatten(tree)

    # 默认选中：一级仅一个且有子目录时选中它（侧栏自动展开二级）
    default_id = None
    if len(tree) == 1 and tree[0]['children']:
        default_id = tree[0]['id']
    else:
        for n in flat:
            if n['children']:
                default_id = n['id']
                break
    if default_id is None and flat:
        default_id = flat[0]['id']

    # 一级仅一项时，强制侧栏展开其二级
    force_expand_root_ids = {tree[0]['id']} if len(tree) == 1 and tree[0]['children'] else set()

    def contains_id(node, target):
        if node['id'] == target:
            return True
        return any(contains_id(c, target) for c in node['children'])

    folder_svg = (
        '<svg viewBox="0 0 20 20" fill="currentColor">'
        '<path d="M2 6a2 2 0 012-2h4l2 2h6a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"/>'
        '</svg>'
    )
    chevron_svg = (
        '<svg class="nav-chevron" viewBox="0 0 20 20" fill="currentColor">'
        '<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 '
        '7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" '
        'clip-rule="evenodd"/></svg>'
    )

    def render_nav(nodes, depth=0):
        items = []
        for i, n in enumerate(nodes):
            safe_title = html_lib.escape(n['title'])
            has_children = bool(n['children'])
            total = count_links(n)
            expand = has_children and (
                n['id'] in force_expand_root_ids
                or (contains_id(n, default_id) if default_id else (depth == 0 and i == 0))
            )
            open_cls = ' is-open' if expand else ''
            active_cls = ' is-active' if n['id'] == default_id else ''
            parent_cls = ' has-children' if has_children else ''

            children_html = (
                f'<ul class="nav-children">{render_nav(n["children"], depth + 1)}</ul>'
                if has_children else ''
            )
            chevron = (
                f'<button type="button" class="nav-toggle" aria-label="展开/折叠" tabindex="-1">'
                f'{chevron_svg}</button>'
                if has_children else '<span class="nav-toggle-spacer"></span>'
            )
            nid = html_lib.escape(n['id'])
            items.append(
                f'<li class="nav-item{parent_cls}{open_cls}{active_cls}" '
                f'data-id="{nid}" data-title="{safe_title.lower()}" data-depth="{depth}">'
                f'<div class="nav-row">{chevron}'
                f'<button type="button" class="nav-link" data-target="{nid}" title="{safe_title}">'
                f'<span class="nav-icon" aria-hidden="true">{folder_svg}</span>'
                f'<span class="nav-text">{safe_title}</span>'
                f'<span class="nav-count">{total}</span>'
                f'</button></div>{children_html}</li>'
            )
        return '\n'.join(items)

    nav_html = render_nav(tree)

    def render_link_cards(links):
        cards = []
        for link in links:
            text = html_lib.escape(link['text'])
            if link.get('kind') == 'heading':
                cards.append(
                    f'<div class="card-heading" role="heading" aria-level="3" '
                    f'data-title="{text.lower()}">'
                    f'<span class="card-heading-text">{text}</span></div>'
                )
                continue
            href = html_lib.escape(link['href'], quote=True)
            host = html_lib.escape(host_of(link['href']))
            fav = favicon_url(link['href'], link['icon'])
            if fav:
                fav_esc = html_lib.escape(fav, quote=True)
                icon_html = (
                    f'<img class="card-icon" src="{fav_esc}" alt="" loading="lazy" '
                    f'referrerpolicy="no-referrer" '
                    f'onerror="this.classList.add(\'is-fallback\');this.src=\'\';">'
                )
            else:
                icon_html = '<span class="card-icon is-fallback" aria-hidden="true"></span>'
            display_host = host or text
            cards.append(
                f'<a class="bookmark-card" href="{href}" target="_blank" rel="noopener noreferrer" '
                f'data-title="{text.lower()}" data-host="{display_host.lower()}">'
                f'{icon_html}<span class="card-body">'
                f'<span class="card-title">{text}</span>'
                f'<span class="card-host">{display_host}</span>'
                f'</span></a>'
            )
        return '\n'.join(cards)

    def render_folder_cards(children):
        cards = []
        for ch in children:
            safe = html_lib.escape(ch['title'])
            total = count_links(ch)
            cards.append(
                f'<button type="button" class="folder-card" data-target="{html_lib.escape(ch["id"])}">'
                f'<span class="folder-glyph" aria-hidden="true"></span>'
                f'<span class="folder-label">{safe}</span>'
                f'<span class="folder-meta">{total} 链接</span>'
                f'</button>'
            )
        return '\n'.join(cards)

    sections = []
    for n in flat:
        nid = html_lib.escape(n['id'])
        safe_title = html_lib.escape(n['title'])
        parts = []
        if n['children']:
            parts.append(
                f'<div class="section-block">'
                f'<div class="section-head"><h3 class="section-label">子分类</h3>'
                f'<span class="section-meta">{len(n["children"])} 个</span></div>'
                f'<div class="folder-grid">{render_folder_cards(n["children"])}</div></div>'
            )
        if n['links']:
            link_n = real_link_count(n['links'])
            parts.append(
                f'<div class="section-block">'
                f'<div class="section-head"><h3 class="section-label">书签</h3>'
                f'<span class="section-meta">{link_n} 个</span></div>'
                f'<div class="card-grid">{render_link_cards(n["links"])}</div></div>'
            )
        if not parts:
            parts.append('<p class="empty-hint">该分类暂无内容</p>')

        hidden = '' if n['id'] == default_id else ' hidden'
        parent_attr = html_lib.escape(n['parent_id'] or '')
        sections.append(
            f'<section class="category-section{hidden}" id="{nid}" '
            f'data-title="{safe_title.lower()}" data-parent="{parent_attr}" data-depth="{n["depth"]}">'
            f'<div class="section-head main-head">'
            f'<h2 class="section-title">{safe_title}</h2>'
            f'<span class="section-meta">{count_links(n)} 个链接</span></div>'
            f'{"".join(parts)}</section>'
        )

    content_html = '\n'.join(sections)
    first_title = html_lib.escape(
        next((n['title'] for n in flat if n['id'] == default_id), '书签')
    )
    total_links = sum(real_link_count(n['links']) for n in flat)
    top_count = len(tree)
    default_id_js = json.dumps(default_id)

    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand_title_esc}</title>
    <style>
        :root {{
            --bg: #ffffff;
            --bg-muted: #f9fafb;
            --bg-hover: #f3f4f6;
            --bg-sidebar: #ffffff;
            --border: #e5e7eb;
            --text: #111827;
            --text-secondary: #6b7280;
            --text-muted: #9ca3af;
            --accent: #16a34a;
            --accent-soft: rgba(22, 163, 74, 0.12);
            --ring: rgba(17, 24, 39, 0.06);
            --shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            --sidebar-w: 280px;
            --header-h: 56px;
            --radius: 10px;
            --folder: #22c55e;
            --font: ui-sans-serif, system-ui, -apple-system, "Segoe UI", "PingFang SC",
                    "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        }}
        html.dark {{
            --bg: #111827;
            --bg-muted: #0f172a;
            --bg-hover: #1f2937;
            --bg-sidebar: #111827;
            --border: #1f2937;
            --text: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent: #22c55e;
            --accent-soft: rgba(34, 197, 94, 0.18);
            --ring: rgba(255, 255, 255, 0.06);
            --shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
            --folder: #4ade80;
        }}
        * {{ box-sizing: border-box; }}
        html, body {{ height: 100%; margin: 0; font-family: var(--font); background: var(--bg); color: var(--text); }}
        body {{ overflow: hidden; }}
        a {{ color: inherit; text-decoration: none; }}
        button {{ font: inherit; color: inherit; background: none; border: none; cursor: pointer; }}
        .app {{ display: flex; height: 100vh; width: 100%; }}
        .sidebar {{
            width: var(--sidebar-w); flex-shrink: 0; display: flex; flex-direction: column;
            background: var(--bg-sidebar); height: 100vh; z-index: 40;
        }}
        .resizer {{
            width: 5px; flex-shrink: 0; cursor: col-resize; position: relative;
            background: transparent; border-left: 1px solid var(--border); z-index: 45;
            touch-action: none;
        }}
        .resizer::after {{
            content: ""; position: absolute; top: 0; bottom: 0; left: -3px; right: -3px;
        }}
        .resizer:hover, .resizer.is-dragging {{
            background: var(--accent-soft); border-left-color: var(--accent);
        }}
        body.is-resizing {{ cursor: col-resize; user-select: none; }}
        body.is-resizing * {{ cursor: col-resize !important; user-select: none !important; }}
        .brand {{
            display: flex; align-items: center; gap: 10px; height: var(--header-h);
            padding: 0 16px; border-bottom: 1px solid var(--border); flex-shrink: 0;
            color: inherit; text-decoration: none; min-width: 0;
        }}
        .brand:hover .brand-title {{ color: var(--accent); }}
        .brand:focus-visible {{
            outline: 2px solid var(--accent); outline-offset: -2px;
        }}
        .brand-mark {{
            width: 28px; height: 28px; border-radius: 8px; background: var(--accent-soft);
            color: var(--accent); display: grid; place-items: center; flex-shrink: 0;
        }}
        .brand-mark svg {{ width: 18px; height: 18px; }}
        .brand-title {{
            font-size: 16px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            transition: color 0.15s;
        }}
        .nav-scroll {{ flex: 1; overflow-y: auto; padding: 10px 8px 20px; }}
        .nav-list, .nav-children {{
            list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1px;
        }}
        .nav-children {{
            display: none; padding-left: 8px; margin: 2px 0 4px 18px;
            border-left: 1px solid var(--border);
        }}
        .nav-item.is-open > .nav-children {{ display: flex; }}
        .nav-row {{ display: flex; align-items: center; gap: 2px; }}
        .nav-toggle, .nav-toggle-spacer {{
            width: 22px; height: 28px; flex-shrink: 0; display: grid; place-items: center;
            color: var(--text-muted); border-radius: 6px;
        }}
        .nav-toggle:hover {{ background: var(--bg-hover); color: var(--accent); }}
        .nav-chevron {{ width: 14px; height: 14px; transition: transform 0.15s ease; }}
        .nav-item.is-open > .nav-row > .nav-toggle .nav-chevron {{ transform: rotate(90deg); }}
        .nav-link {{
            flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px;
            padding: 7px 8px; border-radius: 8px; color: var(--text-secondary); text-align: left;
        }}
        .nav-link:hover {{ background: var(--bg-hover); color: var(--accent); }}
        .nav-item.is-active > .nav-row > .nav-link {{
            background: var(--accent-soft); color: var(--accent); font-weight: 600;
        }}
        .nav-icon {{ width: 16px; height: 16px; flex-shrink: 0; display: grid; place-items: center; }}
        .nav-icon svg {{ width: 15px; height: 15px; }}
        .nav-text {{
            flex: 1; min-width: 0; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}
        .nav-count {{ font-size: 11px; color: var(--text-muted); flex-shrink: 0; }}
        .nav-item.is-active > .nav-row > .nav-link .nav-count {{ color: var(--accent); }}
        .nav-item.hidden {{ display: none; }}

        .main {{ flex: 1; min-width: 0; display: flex; flex-direction: column; height: 100vh; }}
        .topbar {{
            height: var(--header-h); flex-shrink: 0; display: flex; align-items: center;
            gap: 12px; padding: 0 20px; border-bottom: 1px solid var(--border);
        }}
        .menu-toggle {{
            display: none; width: 36px; height: 36px; border-radius: 999px;
            align-items: center; justify-content: center; color: var(--text-secondary);
        }}
        .menu-toggle:hover {{ background: var(--bg-hover); }}
        .search-wrap {{ position: relative; flex: 1; max-width: 320px; margin: 0 auto; }}
        .search-wrap svg {{
            position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
            width: 16px; height: 16px; color: var(--text-muted); pointer-events: none;
        }}
        #global-search {{
            width: 100%; height: 36px; padding: 0 12px 0 36px; border: none; border-radius: 999px;
            background: var(--bg-muted); color: var(--text); outline: none; font-size: 14px;
        }}
        #global-search::placeholder {{ color: var(--text-muted); }}
        #global-search:focus {{ box-shadow: 0 0 0 2px var(--accent-soft); }}
        .theme-toggle {{
            width: 36px; height: 36px; border-radius: 999px; display: grid; place-items: center;
            color: var(--text-secondary); flex-shrink: 0;
        }}
        .theme-toggle:hover {{ background: var(--bg-hover); color: var(--accent); }}
        .theme-toggle svg {{ width: 18px; height: 18px; }}
        .icon-moon {{ display: none; }}
        html.dark .icon-sun {{ display: none; }}
        html.dark .icon-moon {{ display: block; }}

        .content {{ flex: 1; overflow-y: auto; padding: 8px 0 40px; }}
        .breadcrumb {{
            padding: 12px 24px 4px; font-size: 13px; color: var(--text-muted);
            display: flex; align-items: center; flex-wrap: wrap; gap: 6px;
        }}
        .breadcrumb .sep {{ opacity: 0.6; }}
        .breadcrumb a:hover,
        .breadcrumb button:hover {{ color: var(--accent); text-decoration: underline; }}
        .breadcrumb .current {{ color: var(--text-secondary); }}

        .category-section {{ padding: 8px 24px 28px; }}
        .category-section.hidden {{ display: none; }}
        .section-block {{ margin-top: 8px; margin-bottom: 20px; }}
        .section-head {{ display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; }}
        .main-head .section-title {{ font-size: 16px; color: var(--text); margin: 0; font-weight: 600; }}
        .section-label {{ margin: 0; font-size: 13px; font-weight: 600; color: var(--text-secondary); }}
        .section-meta {{ font-size: 12px; color: var(--text-muted); }}

        .card-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
        @media (min-width: 640px) {{ .card-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }} }}
        @media (min-width: 1024px) {{ .card-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }} }}
        @media (min-width: 1536px) {{ .card-grid {{ grid-template-columns: repeat(6, minmax(0, 1fr)); }} }}

        .folder-grid {{
            display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px 10px;
        }}
        @media (min-width: 640px) {{ .folder-grid {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }} }}
        @media (min-width: 1024px) {{ .folder-grid {{ grid-template-columns: repeat(7, minmax(0, 1fr)); }} }}
        @media (min-width: 1536px) {{ .folder-grid {{ grid-template-columns: repeat(9, minmax(0, 1fr)); }} }}

        .folder-card {{
            display: flex; flex-direction: column; align-items: center; gap: 6px;
            padding: 10px 6px; border-radius: 12px; transition: background 0.15s;
        }}
        .folder-card:hover {{ background: var(--bg-hover); }}
        .folder-glyph {{
            width: 48px; height: 36px; border-radius: 4px 4px 6px 6px;
            background: linear-gradient(180deg, #4ade80 0%, var(--folder) 100%);
            position: relative; box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
        }}
        .folder-glyph::before {{
            content: ""; position: absolute; left: 0; top: -6px; width: 18px; height: 8px;
            border-radius: 3px 3px 0 0; background: #86efac;
        }}
        .folder-label {{
            font-size: 13px; font-weight: 500; text-align: center;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
        }}
        .folder-meta {{ font-size: 11px; color: var(--text-muted); }}

        .bookmark-card {{
            display: flex; align-items: center; gap: 14px; padding: 14px 16px;
            border-radius: var(--radius); background: var(--bg);
            box-shadow: var(--shadow), 0 0 0 1px var(--ring); min-width: 0;
            transition: background 0.15s, box-shadow 0.15s;
        }}
        .bookmark-card:hover {{
            background: var(--bg-hover);
            box-shadow: 0 2px 8px rgba(0,0,0,0.06), 0 0 0 1px var(--ring);
        }}
        .bookmark-card.hidden {{ display: none; }}
        .card-heading {{
            grid-column: 1 / -1;
            display: flex;
            align-items: center;
            gap: 14px;
            margin: 6px 0 2px;
            min-width: 0;
        }}
        .card-heading.hidden {{ display: none; }}
        .card-heading-text {{
            flex-shrink: 0;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            letter-spacing: 0.02em;
        }}
        .card-heading::before,
        .card-heading::after {{
            content: "";
            flex: 1;
            height: 1px;
            background: var(--border);
            min-width: 12px;
        }}
        .card-icon {{
            width: 32px; height: 32px; border-radius: 999px; flex-shrink: 0;
            object-fit: contain; background: var(--bg-muted);
        }}
        .card-icon.is-fallback {{
            background: radial-gradient(circle at 30% 30%, #86efac, transparent 55%),
                        linear-gradient(135deg, #16a34a, #166534);
        }}
        .card-body {{ min-width: 0; display: flex; flex-direction: column; gap: 2px; }}
        .card-title {{ font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .card-host {{ font-size: 12px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .empty-hint, .no-result {{ color: var(--text-muted); font-size: 14px; padding: 24px 0; }}
        #no-result {{ display: none; padding: 40px 24px; text-align: center; }}
        .footer {{
            margin: 8px 24px 0; padding-top: 16px; border-top: 1px solid var(--border);
            display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--text-muted);
        }}
        .sidebar-backdrop {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 30; }}
        @media (max-width: 768px) {{
            .sidebar {{
                position: fixed; left: 0; top: 0; transform: translateX(-100%);
                transition: transform 0.2s ease; box-shadow: 4px 0 24px rgba(0,0,0,0.12);
            }}
            body.sidebar-open .sidebar {{ transform: translateX(0); }}
            body.sidebar-open .sidebar-backdrop {{ display: block; }}
            .resizer {{ display: none; }}
            .menu-toggle {{ display: inline-flex; }}
            .search-wrap {{ max-width: none; }}
            .category-section, .breadcrumb {{ padding-left: 16px; padding-right: 16px; }}
            .footer {{ margin-left: 16px; margin-right: 16px; flex-wrap: wrap; }}
        }}
        .nav-scroll::-webkit-scrollbar, .content::-webkit-scrollbar {{ width: 6px; }}
        .nav-scroll::-webkit-scrollbar-thumb, .content::-webkit-scrollbar-thumb {{
            background: var(--border); border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
    <div class="app">
        <aside class="sidebar" id="sidebar">
            <a class="brand" href="{home_href_esc}" title="返回首页">
                <span class="brand-mark" aria-hidden="true">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8 6 6 9.5 6 12.5a6 6 0 0012 0C18 9.5 16 6 12 2zm0 14.5a2.5 2.5 0 110-5 2.5 2.5 0 010 5z"/></svg>
                </span>
                <span class="brand-title">{brand_title_esc}</span>
            </a>
            <nav class="nav-scroll" aria-label="分类导航">
                <ul class="nav-list" id="nav-list">{nav_html}</ul>
            </nav>
        </aside>
        <div class="resizer" id="sidebar-resizer" title="拖拽调整宽度" role="separator" aria-orientation="vertical" aria-label="调整侧栏宽度"></div>
        <div class="main">
            <header class="topbar">
                <button type="button" class="menu-toggle" id="menu-toggle" aria-label="打开目录">
                    <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20"><path fill-rule="evenodd" d="M3 5h14a1 1 0 110 2H3a1 1 0 110-2zm0 4h14a1 1 0 110 2H3a1 1 0 110-2zm0 4h14a1 1 0 110 2H3a1 1 0 110-2z" clip-rule="evenodd"/></svg>
                </button>
                <div class="search-wrap">
                    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/></svg>
                    <input type="search" id="global-search" placeholder="Search..." autocomplete="off">
                </div>
                <button type="button" class="theme-toggle" id="theme-toggle" aria-label="切换主题">
                    <svg class="icon-sun" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"/></svg>
                    <svg class="icon-moon" viewBox="0 0 20 20" fill="currentColor"><path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"/></svg>
                </button>
            </header>
            <div class="content" id="content">
                <div class="breadcrumb" id="breadcrumb">
                    <a href="{home_href_esc}">{brand_title_esc}</a><span class="sep">&gt;</span>
                    <span class="current">{first_title}</span>
                </div>
                <div id="no-result" class="no-result">没有匹配的书签</div>
                {content_html}
                <div class="footer">
                    <span>共 {top_count} 个一级分类 · {total_links} 个链接</span>
                    <span>Ctrl+K 搜索</span>
                </div>
            </div>
        </div>
    </div>
    <script>
        (function () {{
            const root = document.documentElement;
            const searchInput = document.getElementById("global-search");
            const navItems = [...document.querySelectorAll(".nav-item")];
            const sections = [...document.querySelectorAll(".category-section")];
            const cards = [...document.querySelectorAll(".bookmark-card")];
            const headings = [...document.querySelectorAll(".card-heading")];
            const breadcrumb = document.getElementById("breadcrumb");
            const noResult = document.getElementById("no-result");
            const content = document.getElementById("content");
            const byId = Object.fromEntries(navItems.map(i => [i.dataset.id, i]));
            const homeHref = {json.dumps(home_href or "../index.html")};
            const brandTitle = {json.dumps(brand_title)};
            let activeId = {default_id_js};

            const savedTheme = localStorage.getItem("bookmark-theme");
            if (savedTheme === "dark" || (!savedTheme && matchMedia("(prefers-color-scheme: dark)").matches)) {{
                root.classList.add("dark");
            }}
            document.getElementById("theme-toggle").addEventListener("click", () => {{
                root.classList.toggle("dark");
                localStorage.setItem("bookmark-theme", root.classList.contains("dark") ? "dark" : "light");
            }});

            const menuToggle = document.getElementById("menu-toggle");
            const backdrop = document.getElementById("sidebar-backdrop");
            function closeSidebar() {{ document.body.classList.remove("sidebar-open"); }}
            menuToggle.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
            backdrop.addEventListener("click", closeSidebar);

            // 侧栏宽度拖拽
            const resizer = document.getElementById("sidebar-resizer");
            const SIDEBAR_MIN = 180;
            const SIDEBAR_MAX = 560;
            const savedWidth = parseInt(localStorage.getItem("bookmark-sidebar-w") || "", 10);
            if (savedWidth >= SIDEBAR_MIN && savedWidth <= SIDEBAR_MAX) {{
                root.style.setProperty("--sidebar-w", savedWidth + "px");
            }}
            let resizing = false;
            function clampSidebar(w) {{
                return Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, w));
            }}
            function onResizeMove(clientX) {{
                const w = clampSidebar(clientX);
                root.style.setProperty("--sidebar-w", w + "px");
            }}
            function stopResize() {{
                if (!resizing) return;
                resizing = false;
                resizer.classList.remove("is-dragging");
                document.body.classList.remove("is-resizing");
                const w = parseInt(getComputedStyle(root).getPropertyValue("--sidebar-w"), 10);
                if (w) localStorage.setItem("bookmark-sidebar-w", String(w));
            }}
            resizer.addEventListener("mousedown", (e) => {{
                e.preventDefault();
                resizing = true;
                resizer.classList.add("is-dragging");
                document.body.classList.add("is-resizing");
            }});
            document.addEventListener("mousemove", (e) => {{
                if (!resizing) return;
                onResizeMove(e.clientX);
            }});
            document.addEventListener("mouseup", stopResize);
            resizer.addEventListener("touchstart", (e) => {{
                resizing = true;
                resizer.classList.add("is-dragging");
                document.body.classList.add("is-resizing");
            }}, {{ passive: true }});
            document.addEventListener("touchmove", (e) => {{
                if (!resizing || !e.touches[0]) return;
                onResizeMove(e.touches[0].clientX);
            }}, {{ passive: true }});
            document.addEventListener("touchend", stopResize);

            function ancestorsOf(id) {{
                const chain = [];
                let sec = document.getElementById(id);
                while (sec && sec.dataset.parent) {{
                    const pid = sec.dataset.parent;
                    if (!pid) break;
                    chain.unshift(pid);
                    sec = document.getElementById(pid);
                }}
                return chain;
            }}

            function openAncestors(id) {{
                ancestorsOf(id).forEach(pid => {{
                    const item = byId[pid];
                    if (item) item.classList.add("is-open");
                }});
                const self = byId[id];
                if (self && self.classList.contains("has-children")) self.classList.add("is-open");
            }}

            function updateBreadcrumb(id) {{
                const html = [`<a href="${{homeHref}}">${{brandTitle}}</a>`];
                ancestorsOf(id).forEach(pid => {{
                    const item = byId[pid];
                    if (!item) return;
                    const title = item.querySelector(".nav-text").textContent;
                    html.push('<span class="sep">&gt;</span>');
                    html.push(`<button type="button" data-target="${{pid}}">${{title}}</button>`);
                }});
                const cur = byId[id];
                const title = cur ? cur.querySelector(".nav-text").textContent : "";
                html.push('<span class="sep">&gt;</span>');
                html.push(`<span class="current">${{title}}</span>`);
                breadcrumb.innerHTML = html.join("");
                breadcrumb.querySelectorAll("button[data-target]").forEach(btn => {{
                    btn.addEventListener("click", () => showCategory(btn.dataset.target));
                }});
            }}

            function setActiveNav(id) {{
                navItems.forEach(item => item.classList.toggle("is-active", item.dataset.id === id));
                updateBreadcrumb(id);
            }}

            function showCategory(id) {{
                activeId = id;
                searchInput.value = "";
                cards.forEach(c => c.classList.remove("hidden"));
                headings.forEach(h => h.classList.remove("hidden"));
                sections.forEach(sec => sec.classList.toggle("hidden", sec.id !== id));
                navItems.forEach(item => item.classList.remove("hidden"));
                noResult.style.display = "none";
                openAncestors(id);
                setActiveNav(id);
                content.scrollTop = 0;
                closeSidebar();
            }}

            navItems.forEach(item => {{
                const toggle = item.querySelector(":scope > .nav-row > .nav-toggle");
                if (toggle) {{
                    toggle.addEventListener("click", (e) => {{
                        e.stopPropagation();
                        item.classList.toggle("is-open");
                    }});
                }}
                item.querySelector(":scope > .nav-row > .nav-link").addEventListener("click", () => {{
                    showCategory(item.dataset.id);
                }});
            }});

            content.addEventListener("click", (e) => {{
                const folder = e.target.closest(".folder-card");
                if (folder) showCategory(folder.dataset.target);
            }});

            function runSearch(term) {{
                term = term.trim().toLowerCase();
                if (!term) {{
                    if (activeId) showCategory(activeId);
                    return;
                }}
                let any = false;
                const matchedSec = new Set();
                cards.forEach(card => {{
                    const hit = (card.dataset.title || "").includes(term)
                        || (card.dataset.host || "").includes(term)
                        || (card.getAttribute("href") || "").toLowerCase().includes(term);
                    card.classList.toggle("hidden", !hit);
                    if (hit) {{
                        any = true;
                        matchedSec.add(card.closest(".category-section").id);
                    }}
                }});
                // 搜索时：标题命中则显示；否则仅当同网格内有可见卡片时保留分组标题
                headings.forEach(h => {{
                    const titleHit = (h.dataset.title || "").includes(term);
                    let keep = titleHit;
                    if (!keep) {{
                        const grid = h.closest(".card-grid");
                        if (grid) {{
                            let el = h.nextElementSibling;
                            while (el && !el.classList.contains("card-heading")) {{
                                if (el.classList.contains("bookmark-card") && !el.classList.contains("hidden")) {{
                                    keep = true;
                                    break;
                                }}
                                el = el.nextElementSibling;
                            }}
                        }}
                    }}
                    h.classList.toggle("hidden", !keep);
                    if (titleHit) {{
                        any = true;
                        matchedSec.add(h.closest(".category-section").id);
                    }}
                }});
                navItems.forEach(item => {{
                    if ((item.dataset.title || "").includes(term)) {{
                        matchedSec.add(item.dataset.id);
                        any = true;
                    }}
                }});
                sections.forEach(sec => sec.classList.toggle("hidden", !matchedSec.has(sec.id)));
                const keep = new Set(matchedSec);
                matchedSec.forEach(id => ancestorsOf(id).forEach(pid => keep.add(pid)));
                navItems.forEach(item => {{
                    const show = keep.has(item.dataset.id);
                    item.classList.toggle("hidden", !show);
                    if (show && item.classList.contains("has-children")) item.classList.add("is-open");
                }});
                noResult.style.display = any ? "none" : "block";
                breadcrumb.innerHTML = `<a href="${{homeHref}}">${{brandTitle}}</a><span class="sep">&gt;</span><span class="current">搜索结果</span>`;
                content.scrollTop = 0;
            }}

            searchInput.addEventListener("input", () => runSearch(searchInput.value));
            document.addEventListener("keydown", (e) => {{
                if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "f")) {{
                    e.preventDefault();
                    searchInput.focus();
                    searchInput.select();
                }}
            }});

            if (activeId) openAncestors(activeId);
        }})();
    </script>
</body>
</html>"""

    return html_template


def main():
    try:
        import os

        input_file = input("请输入HTML书签文件的完整路径（例如：C:\\Users\\YourUser\\Downloads\\bookmarks.html）：")
        input_file = os.path.normpath(input_file)

        output_dir = os.path.dirname(input_file)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(output_dir, f"{base_name}_tree.html")

        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        converted_html = parse_bookmark_html(html_content)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(converted_html)

        print(f"转换完成！输出文件已保存到：{output_file}")
        print("功能特性：")
        print("- 左侧一 / 二级（多级）树形目录，可展开折叠")
        print("- 点击一级显示子分类文件夹；点击二级显示书签卡片")
        print("- 顶部全局搜索、浅色/深色主题、响应式布局")

    except Exception as e:
        import sys
        print(f"转换过程中发生错误：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
