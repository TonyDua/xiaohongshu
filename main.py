import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import mimetypes
import requests

DEFAULT_MAX_SCROLLS = 200
DEFAULT_IDLE_WAIT_MS = 1000
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)


def safe_eval(page, script: str, arg=None, retries: int = 3, wait_state: str = 'domcontentloaded'):
    """在页面可能发生导航或上下文重建时，安全执行 evaluate，并做重试。"""
    for attempt in range(retries):
        try:
            if arg is None:
                return page.evaluate(script)
            else:
                return page.evaluate(script, arg)
        except Exception:
            try:
                page.wait_for_load_state(wait_state, timeout=1000)
            except Exception:
                pass
            page.wait_for_timeout(300)
    return None


def try_get_meta(page, prop: str):
    """优先通过 locator 获取 meta，再回退到 evaluate。"""
    try:
        loc = page.locator(f'meta[property="{prop}"]').first
        content = loc.get_attribute('content')
        if content:
            return content
    except Exception:
        pass
    return safe_eval(page, """(p)=>document.querySelector(`meta[property="${p}"]`)?.content || null""", prop) or None


def try_expand_note(page):
    """尝试点击正文区域的“展开/展开全文/更多”等按钮，以显示完整内容。"""
    candidates = ['text=展开全文', 'text=展开', 'text=更多']
    for sel in candidates:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                loc.first.click()
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    return False


def extract_detail_desc_text(page):
    """尽可能获取 #detail-desc .note-text 的完整文本（含隐藏/折叠换行）。"""
    # 先尝试展开
    try_expand_note(page)
    txt = safe_eval(
        page,
        """
() => {
  const root = document.querySelector('#detail-desc');
  if (!root) return null;
  const nt = root.querySelector('.note-text') || root;
  const clone = nt.cloneNode(true);
  // 将 <br> 转为换行，保留结构性换行
  clone.querySelectorAll('br').forEach(br => br.replaceWith(document.createTextNode('\n')));
  const text = (clone.textContent || '').replace(/\u00A0/g, ' ').replace(/\s+$/,'').replace(/^\s+/,'');
  return text && text.trim().length > 0 ? text.trim() : null;
}
"""
    )
    if txt and isinstance(txt, str) and len(txt.strip()) > 0:
        return txt.strip()
    # 回退：使用 innerText 并尝试滚动容器确保可见
    try:
        page.evaluate("""
(() => {
  const scroller = document.querySelector('#note-scroller');
  if (scroller) scroller.scrollTop = scroller.scrollHeight;
})()
""")
        page.wait_for_timeout(200)
    except Exception:
        pass
    txt2 = safe_eval(
        page,
        """
() => {
  const root = document.querySelector('#detail-desc');
  if (!root) return null;
  const nt = root.querySelector('.note-text') || root;
  const t = nt.innerText || root.innerText || '';
  return t && t.trim().length > 0 ? t.trim() : null;
}
"""
    )
    return (txt2 or '')


def is_profile_url(text: str) -> bool:
    return 'xiaohongshu.com' in (text or '')


def build_profile_url(user: str) -> str:
    if is_profile_url(user):
        return user
    # 假定为用户ID
    return f"https://www.xiaohongshu.com/user/profile/{user}"


def load_cookies(path: str | None):
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        print(f"[warn] cookies 文件不存在: {p}", file=sys.stderr)
        return []
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        cookies = []
        if isinstance(data, dict) and 'cookies' in data:
            items = data['cookies']
        elif isinstance(data, list):
            items = data
        else:
            items = []
        def normalize_same_site(val):
            if not val:
                return 'Lax'
            v = str(val).strip().lower()
            mapping = {
                'lax': 'Lax',
                'strict': 'Strict',
                'none': 'None',
                'no_restriction': 'None',
                'unspecified': 'Lax',
                'no-restriction': 'None',
            }
            return mapping.get(v, 'Lax')
        for c in items:
            name = c.get('name') or c.get('key')
            value = c.get('value')
            if not name or value is None:
                continue
            domain = c.get('domain')
            pathv = c.get('path') or '/'
            expires = c.get('expires') or c.get('expirationDate')
            secure = bool(c.get('secure')) if 'secure' in c else False
            httpOnly = bool(c.get('httpOnly')) if 'httpOnly' in c else False
            if domain and domain.startswith('.'):
                domain = domain
            elif not domain:
                domain = '.xiaohongshu.com'
            entry = {
                'name': name,
                'value': value,
                'domain': domain,
                'path': pathv,
                'secure': secure,
                'httpOnly': httpOnly,
                'sameSite': normalize_same_site(c.get('sameSite')),
            }
            if isinstance(expires, (int, float)) and expires > 0:
                entry['expires'] = int(expires)
            cookies.append(entry)
        return cookies
    except Exception as e:
        print(f"[warn] 解析 cookies 失败: {e}", file=sys.stderr)
        return []


def extract_post_links(page) -> list[str]:
    anchors = page.locator('a[href*="/explore/"], a[href*="/discovery/item/"]')
    hrefs = set()
    count = anchors.count()
    for i in range(count):
        href = anchors.nth(i).get_attribute('href')
        if not href:
            continue
        raw = href
        if raw.startswith('/'):
            raw = 'https://www.xiaohongshu.com' + raw
        raw = raw.split('#')[0]
        raw = raw.split('?')[0]
        m1 = re.search(r'https?://www\.xiaohongshu\.com/explore/([0-9A-Za-z_-]{6,})', raw) or \
             re.search(r'^/explore/([0-9A-Za-z_-]{6,})$', raw)
        m2 = re.search(r'https?://www\.xiaohongshu\.com/discovery/item/([0-9A-Za-z_-]{6,})', raw) or \
             re.search(r'^/discovery/item/([0-9A-Za-z_-]{6,})$', raw)
        if m1:
            hrefs.add(f'https://www.xiaohongshu.com/explore/{m1.group(1)}')
        elif m2:
            hrefs.add(f'https://www.xiaohongshu.com/discovery/item/{m2.group(1)}')
    return list(hrefs)


def scroll_to_load_all(page, limit: int | None = None, max_scrolls: int = DEFAULT_MAX_SCROLLS, idle_wait_ms: int = DEFAULT_IDLE_WAIT_MS) -> list[str]:
    collected = set(extract_post_links(page))
    same_count_times = 0
    for i in range(max_scrolls):
        if limit and len(collected) >= limit:
            break
        page.evaluate('window.scrollBy(0, document.body.scrollHeight)')
        page.wait_for_timeout(idle_wait_ms)
        new_links = set(extract_post_links(page))
        before = len(collected)
        collected |= new_links
        after = len(collected)
        if after == before:
            same_count_times += 1
            if same_count_times >= 5:
                break
        else:
            same_count_times = 0
    return list(collected)[:limit] if limit else list(collected)


def extract_post_content(page, url: str) -> dict:
    title = try_get_meta(page, 'og:title') or page.title()
    description = try_get_meta(page, 'og:description')
    # images
    imgs = safe_eval(
        page,
        """
() => Array.from(document.querySelectorAll('img'))
  .map(img => img.getAttribute('src') || img.getAttribute('data-src') || '')
  .filter(src => typeof src === 'string' && src.length > 0 && !src.startsWith('data:'))
"""
    ) or []
    # videos
    videos = safe_eval(
        page,
        """
() => Array.from(document.querySelectorAll('video, source'))
  .map(v => v.getAttribute('src') || '')
  .filter(src => typeof src === 'string' && src.length > 0 && !src.startsWith('data:'))
"""
    ) or []
    # 优先抓取 #detail-desc 内 .note-text 的完整文本
    detail_desc_text = extract_detail_desc_text(page)
    # textual content fallback（当 detail-desc 不可用时）
    text_blocks = [] if detail_desc_text else (safe_eval(
        page,
        """
() => {
  const selectors = ['article', '[class*="content"]', '[class*="note"]', '[class*="RichText"]', '[data-test-id*="content"]'];
  const container = selectors.map(s => document.querySelector(s)).find(Boolean) || document.body;
  return Array.from(container.querySelectorAll('h1, h2, p, span, div'))
    .map(el => el.innerText)
    .filter(t => t && t.trim().length > 0)
    .slice(0, 80);
}
"""
    ) or [])
    content_text = (detail_desc_text or ('\n'.join(dict.fromkeys(text_blocks)) if text_blocks else (description or '')))

    note_id = None
    m = re.search(r'/explore/([0-9a-zA-Z_-]+)', url) or re.search(r'/discovery/item/([0-9a-zA-Z_-]+)', url)
    if m:
        note_id = m.group(1)
    return {
        'url': url,
        'note_id': note_id,
        'title': title or '',
        'description': description or '',
        'content_text': content_text or '',
        'images': list(dict.fromkeys(imgs)) if imgs else [],
        'videos': list(dict.fromkeys(videos)) if videos else [],
        'downloaded_images': [],
    }


def render_post_html(data: dict) -> str:
    title = data.get('title') or '未命名帖子'
    original = data.get('url', '')
    content_text = data.get('content_text', '')
    images = data.get('images', [])
    videos = data.get('videos', [])
    dl_images = data.get('downloaded_images', [])
    head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{html_escape(title)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.6;padding:24px;max-width:860px;margin:0 auto;background:#fafafa;color:#222}}
header{{margin-bottom:16px}}
h1{{font-size:1.6rem;margin:0 0 8px}}
.meta{{font-size:.9rem;color:#666;margin-bottom:16px}}
.content{{white-space:pre-wrap}}
.media-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:16px}}
.media-grid img, .media-grid video{{width:100%;border-radius:8px;background:#eee}}
a.source{{color:#1a73e8;text-decoration:none}}
a.source:hover{{text-decoration:underline}}
footer{{margin-top:28px;font-size:.85rem;color:#888}}
code{{background:#eee;padding:2px 4px;border-radius:4px}}
</style>
</head>
<body>
"""
    media_html = ''
    if videos:
        media_html += '<section><h2>视频</h2><div class="media-grid">' + ''.join(
            f'<video controls src="{html_escape(src)}"></video>'
            for src in videos
        ) + '</div></section>'
    if dl_images:
        media_html += '<section><h2>已下载图片</h2><div class="media-grid">' + ''.join(
            f'<img loading="lazy" src="{html_escape(src)}" alt="image"/>'
            for src in dl_images
        ) + '</div></section>'
    body = f"""
<header>
  <h1>{html_escape(title)}</h1>
  <div class="meta">原帖地址：<a class="source" href="{html_escape(original)}" target="_blank" rel="noreferrer">{html_escape(original)}</a></div>
</header>
<section class="content">{html_escape(content_text)}</section>
{media_html}
<footer>生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}</footer>
</body>
</html>
"""
    return head + body


def render_post_markdown(data: dict) -> str:
    title = data.get('title') or '未命名帖子'
    original = data.get('url', '')
    content_text = data.get('content_text', '')
    images = data.get('images', [])
    videos = data.get('videos', [])
    dl_images = data.get('downloaded_images', [])
    lines = []
    lines.append(f"# {title.replace(' - 小红书', '')}")
    # if original:
    #     lines.append("")
    #     lines.append(f"原帖地址: {original}")
    if content_text:
        lines.append("")
        lines.append(content_text)
    if dl_images:
        lines.append("")
        lines.append("## 图片")
        cols = 4
        header = "| " + " | ".join([f"图{i+1}" for i in range(cols)]) + " |"
        sep = "| " + " | ".join(["---"] * cols) + " |"
        lines.append(header)
        lines.append(sep)
        for i in range(0, len(dl_images), cols):
            batch = dl_images[i:i+cols]
            cells = [f"![image]({src})" for src in batch]
            while len(cells) < cols:
                cells.append(" ")
            lines.append("| " + " | ".join(cells) + " |")
    if videos:
        lines.append("")
        lines.append("## 视频链接")
        for src in videos:
            lines.append(f"- {src}")
    lines.append("")
    lines.append(f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    return "\n".join(lines)


def html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def save_html(html: str, out_dir: str | Path, filename: str) -> str:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(html, encoding='utf-8')
    return str(path)


def save_document(content: str, out_dir: str | Path, filename: str, skip_if_exists: bool = False) -> str | None:
    """保存按格式生成的内容（.html 或 .md）。
    
    Args:
        content: 要保存的内容
        out_dir: 输出目录
        filename: 文件名
        skip_if_exists: 如果文件已存在，是否跳过（返回 None）
    
    Returns:
        保存的文件路径，如果跳过则返回 None
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    if skip_if_exists and path.exists():
        return None
    path.write_text(content, encoding='utf-8')
    return str(path)


def load_existing_index(out_dir: str | Path) -> list[dict]:
    """从已存在的索引文件中加载帖子列表。"""
    out_dir = Path(out_dir)
    existing_items = []
    
    # 尝试从 HTML 索引加载
    index_html = out_dir / 'index.html'
    if index_html.exists():
        try:
            content = index_html.read_text(encoding='utf-8')
            # 简单解析：提取所有链接
            import re
            # 匹配 <a href="文件名">标题</a> 和原帖链接
            pattern = r'<a href="([^"]+)"[^>]*>([^<]+)</a>.*?<a href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, content)
            for match in matches:
                filename, title, url, _ = match
                if filename.endswith(('.html', '.md')) and 'xiaohongshu.com' in url:
                    existing_items.append({
                        'file': filename,
                        'title': title,
                        'url': url,
                    })
        except Exception:
            pass
    
    # 尝试从 Markdown 索引加载
    index_md = out_dir / 'index.md'
    if index_md.exists():
        try:
            content = index_md.read_text(encoding='utf-8')
            import re
            # 匹配 Markdown 链接格式: - [标题](文件)  原帖: URL
            pattern = r'- \[([^\]]+)\]\(([^\)]+)\)\s+原帖:\s+(\S+)'
            matches = re.findall(pattern, content)
            for match in matches:
                title, filename, url = match
                if filename.endswith(('.html', '.md')) and 'xiaohongshu.com' in url:
                    existing_items.append({
                        'file': filename,
                        'title': title,
                        'url': url,
                    })
        except Exception:
            pass
    
    return existing_items


def build_index_html(items: list[dict], out_dir: str | Path, merge_existing: bool = True) -> str:
    """构建索引 HTML，可选择合并已存在的索引。"""
    if merge_existing:
        existing = load_existing_index(out_dir)
        # 按 URL 去重，新项目优先
        seen_urls = {item['url'] for item in items}
        existing_filtered = [item for item in existing if item.get('url') not in seen_urls]
        items = items + existing_filtered
    
    head = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><title>小红书爬取结果索引</title><style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;line-height:1.6;padding:24px;max-width:980px;margin:0 auto;background:#fafafa;color:#222}
h1{font-size:1.8rem;margin:0 0 12px}
ul{list-style:none;padding:0}
li{margin:8px 0;padding:8px;background:#fff;border:1px solid #eee;border-radius:8px}
a{color:#1a73e8;text-decoration:none}
a:hover{text-decoration:underline}
small{color:#666}
</style></head><body><h1>小红书爬取结果索引</h1><ul>"""
    lis = ''.join(
        f'<li><a href="{html_escape(item["file"])}" target="_blank">{html_escape(item["title"] or item.get("note_id") or "未命名帖子")}</a>'
        f' <small>原帖: <a href="{html_escape(item["url"])}" target="_blank">{html_escape(item["url"])}</a></small></li>'
        for item in items
    )
    tail = '</ul></body></html>'
    index_path = Path(out_dir) / 'index.html'
    index_path.write_text(head + lis + tail, encoding='utf-8')
    return str(index_path)


def build_index_markdown(items: list[dict], out_dir: str | Path, merge_existing: bool = True) -> str:
    """构建索引 Markdown，可选择合并已存在的索引。"""
    if merge_existing:
        existing = load_existing_index(out_dir)
        # 按 URL 去重，新项目优先
        seen_urls = {item['url'] for item in items}
        existing_filtered = [item for item in existing if item.get('url') not in seen_urls]
        items = items + existing_filtered
    
    lines = ["# 小红书爬取结果索引", ""]
    for item in items:
        title = item.get('title') or item.get('note_id') or '未命名帖子'
        file = item.get('file')
        url = item.get('url')
        lines.append(f"- [{title}]({file})  原帖: {url}")
    index_path = Path(out_dir) / 'index.md'
    index_path.write_text("\n".join(lines), encoding='utf-8')
    return str(index_path)


def extract_note_id_from_url(url: str) -> str | None:
    """从 URL 中提取 note_id。"""
    m = re.search(r'/explore/([0-9a-zA-Z_-]+)', url) or re.search(r'/discovery/item/([0-9a-zA-Z_-]+)', url)
    return m.group(1) if m else None


def get_existing_note_ids(out_dir: str | Path, out_format: str = 'html') -> set[str]:
    """从输出目录中提取所有已存在的 note_id。"""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return set()
    
    note_ids = set()
    ext = 'html' if out_format == 'html' else 'md'
    
    # 遍历输出目录中的所有文件
    for file_path in out_dir.glob(f'*.{ext}'):
        filename = file_path.stem  # 获取不带扩展名的文件名
        # 文件名格式：note_id_title 或 note_id
        # 提取第一个下划线之前的部分作为 note_id
        parts = filename.split('_', 1)
        if parts:
            potential_id = parts[0]
            # 验证是否是有效的 note_id 格式（长度大于 6 的字母数字组合）
            if len(potential_id) > 6 and re.match(r'^[0-9a-zA-Z_-]+$', potential_id):
                note_ids.add(potential_id)
    
    return note_ids


def deduplicate_and_filter_links(links: list[str], existing_note_ids: set[str] = None, skip_existing: bool = False) -> tuple[list[str], int, int]:
    """去重链接并过滤已存在的 note_id。
    
    Returns:
        (去重后的链接列表, 去重数量, 跳过数量)
    """
    # 按 note_id 去重
    seen_ids = {}
    for url in links:
        note_id = extract_note_id_from_url(url)
        if note_id and note_id not in seen_ids:
            seen_ids[note_id] = url
    
    unique_links = list(seen_ids.values())
    duplicate_count = len(links) - len(unique_links)
    
    # 如果启用跳过已存在，过滤已下载的
    if skip_existing and existing_note_ids:
        filtered_links = []
        skipped_count = 0
        for url in unique_links:
            note_id = extract_note_id_from_url(url)
            if note_id and note_id in existing_note_ids:
                skipped_count += 1
            else:
                filtered_links.append(url)
        return filtered_links, duplicate_count, skipped_count
    
    return unique_links, duplicate_count, 0


def extract_swiper_images(page) -> list[str]:
    """提取轮播区域图片（`.swiper-slide .img-container img`）。"""
    urls = safe_eval(
        page,
        """
() => Array.from(document.querySelectorAll('.swiper-slide .img-container img'))
  .map(img => {
    const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
    const srcset = img.getAttribute('srcset') || '';
    let url = src;
    if ((!url || url.length < 10) && srcset) {
      const parts = srcset.split(',').map(s => s.trim().split(' ')[0]).filter(Boolean);
      url = parts[parts.length - 1] || parts[0] || '';
    }
    return url;
  })
  .filter(u => typeof u === 'string' && /^https?:\/\//.test(u))
"""
    ) or []
    # 去重保序
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def infer_ext_from_content_type(ct: str | None) -> str:
    if not ct:
        return '.jpg'
    ct = ct.split(';')[0].strip().lower()
    mapping = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/gif': '.gif',
    }
    return mapping.get(ct, mimetypes.guess_extension(ct) or '.jpg')


def download_images(urls: list[str], images_dir: Path, prefix: str, referer: str | None = None, user_agent: str | None = None) -> list[str]:
    images_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, u in enumerate(urls, start=1):
        try:
            headers = {
                'User-Agent': user_agent or DEFAULT_USER_AGENT,
                'Referer': referer or 'https://www.xiaohongshu.com/',
                'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
            }
            resp = requests.get(u, headers=headers, timeout=20, stream=True)
            if resp.status_code != 200:
                print(f"[warn] 下载失败({resp.status_code}): {u}")
                continue
            ext = os.path.splitext(urlparse(u).path)[1]
            if not ext or len(ext) > 5:
                ext = infer_ext_from_content_type(resp.headers.get('Content-Type'))
            fname = f"{prefix}_{i}{ext}"
            path = images_dir / fname
            with open(path, 'wb') as f:
                for chunk in resp.iter_content(8192):
                    if chunk:
                        f.write(chunk)
            saved.append(str(path))
        except Exception as e:
            print(f"[warn] 下载异常: {e}")
            continue
    return saved


def run(user: str, out: str, cookies_path: str | None = None, limit: int | None = None, headless: bool = True, timeout_ms: int = 30000, user_agent: str | None = None, out_format: str = 'html', skip_existing: bool = False):
    profile_url = build_profile_url(user)
    print(f"[info] 打开用户主页: {profile_url}")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=user_agent or DEFAULT_USER_AGENT,
            viewport={"width": 1366, "height": 860},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        cookies = load_cookies(cookies_path)
        if cookies:
            print(f"[info] 导入 cookies: {len(cookies)} 条")
            try:
                context.add_cookies(cookies)
            except Exception as e:
                print(f"[warn] 添加 cookies 失败: {e}")
        page = context.new_page()
        page.set_default_navigation_timeout(timeout_ms)
        page.set_default_timeout(timeout_ms)
        try:
            page.goto(profile_url, wait_until='domcontentloaded')
        except PlaywrightTimeoutError:
            print("[warn] 主页加载超时，继续尝试滚动采集。")
        # 初始短等待以加载首屏
        page.wait_for_timeout(2000)
        print("[info] 开始滚动加载帖子列表...")
        links = scroll_to_load_all(page, limit=limit)
        print(f"[info] 收集到帖子链接: {len(links)}")
        
        # 获取已存在的 note_id 并去重、过滤链接
        existing_ids = get_existing_note_ids(out, out_format) if skip_existing else set()
        links, dup_count, skip_count = deduplicate_and_filter_links(links, existing_ids, skip_existing)
        
        if dup_count > 0:
            print(f"[info] 去除重复链接: {dup_count} 个")
        if skip_count > 0:
            print(f"[info] 跳过已存在的帖子: {skip_count} 个")
        print(f"[info] 待处理帖子: {len(links)} 个")
        
        results = []
        for idx, url in enumerate(links, start=1):
            print(f"[info] [{idx}/{len(links)}] 打开帖子: {url}")
            detail = context.new_page()
            detail.set_default_navigation_timeout(timeout_ms)
            detail.set_default_timeout(timeout_ms)
            try:
                detail.goto(url, wait_until='domcontentloaded')
                # 尝试在 SPA 环境下等待更稳定的状态
                try:
                    detail.wait_for_load_state('load')
                except Exception:
                    pass
                try:
                    detail.wait_for_load_state('networkidle', timeout=2000)
                except Exception:
                    pass
            except PlaywrightTimeoutError:
                print(f"[warn] 打开帖子超时: {url}")
            # 等待图片懒加载一些
            detail.wait_for_timeout(1200)
            try:
                data = extract_post_content(detail, url)
            except Exception as e:
                print(f"[warn] 提取帖子内容失败: {e}")
                data = {
                    'url': url,
                    'note_id': None,
                    'title': '提取失败',
                    'description': '',
                    'content_text': '',
                    'images': [],
                    'videos': [],
                    'downloaded_images': [],
                }
            # 提取并下载轮播图片
            try:
                swiper_imgs = extract_swiper_images(detail)
                if swiper_imgs:
                    local_files = download_images(swiper_imgs, Path(out) / 'images', prefix=(data.get('note_id') or f'post-{idx}'), referer=url)
                    data['downloaded_images'] = [f"images/{Path(p).name}" for p in local_files]
            except Exception as e:
                print(f"[warn] 下载轮播图片失败: {e}")
            fname_base = data.get('note_id') or f"post-{idx}"
            safe_title = re.sub(r'[\\/:*?\"<>|]+', '_', data.get('title') or '')
            ext = 'html' if out_format == 'html' else 'md'
            filename = f"{fname_base}_{safe_title[:50]}.{ext}" if safe_title else f"{fname_base}.{ext}"
            if out_format == 'html':
                file_path = save_document(render_post_html(data), out, filename, skip_if_exists=False)
            else:
                file_path = save_document(render_post_markdown(data), out, filename, skip_if_exists=False)
            results.append({'file': os.path.basename(file_path), 'title': data.get('title'), 'url': url, 'note_id': data.get('note_id')})
            detail.close()
        # 合并已存在的索引，因为我们已经在处理前过滤了已存在的帖子
        index_html = build_index_html(results, out, merge_existing=skip_existing)
        index_md = build_index_markdown(results, out, merge_existing=skip_existing) if out_format == 'markdown' else None
        print(f"[done] 已保存 {len(results)} 个帖子。索引: {index_html}{' / ' + index_md if index_md else ''}")
        context.close()
        browser.close()


def load_links_from_csv(csv_path: str) -> list[str]:
    links: list[str] = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return []
        # 检测表头
        header = rows[0]
        start_idx = 0
        col_idx = 0
        if len(header) == 1 and str(header[0]).strip().lower() in ('note_link', 'url', 'link'):
            start_idx = 1
            col_idx = 0
        else:
            # 多列时寻找常见列名
            for i, col in enumerate(header):
                if str(col).strip().lower() in ('note_link', 'url', 'link'):
                    start_idx = 1
                    col_idx = i
                    break
        for row in rows[start_idx:]:
            if not row:
                continue
            url = str(row[col_idx]).strip()
            if not url:
                continue
            if 'xiaohongshu.com/explore/' in url or 'xiaohongshu.com/discovery/item/' in url:
                links.append(url)
        # 去重保序
        seen = set()
        uniq = []
        for u in links:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        return uniq
    except Exception as e:
        print(f"[warn] 读取 CSV 失败: {e}")
        return []


def run_from_csv(csv_path: str, out: str, cookies_path: str | None = None, limit: int | None = None, headless: bool = True, timeout_ms: int = 30000, user_agent: str | None = None, out_format: str = 'html', skip_existing: bool = False):
    links = load_links_from_csv(csv_path)
    if not links:
        print(f"[warn] CSV 未读取到有效链接: {csv_path}")
        return
    
    print(f"[info] CSV 读取到 {len(links)} 个链接")
    
    # 获取已存在的 note_id 并去重、过滤链接
    existing_ids = get_existing_note_ids(out, out_format) if skip_existing else set()
    links, dup_count, skip_count = deduplicate_and_filter_links(links, existing_ids, skip_existing)
    
    if dup_count > 0:
        print(f"[info] 去除重复链接: {dup_count} 个")
    if skip_count > 0:
        print(f"[info] 跳过已存在的帖子: {skip_count} 个")
    
    # 应用 limit 限制
    if limit and len(links) > limit:
        links = links[:limit]
    
    if not links:
        print("[info] 没有需要处理的链接")
        return
    
    print(f"[info] 即将处理 {len(links)} 个链接")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=user_agent or DEFAULT_USER_AGENT,
            viewport={"width": 1366, "height": 860},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        cookies = load_cookies(cookies_path)
        if cookies:
            print(f"[info] 导入 cookies: {len(cookies)} 条")
            try:
                context.add_cookies(cookies)
            except Exception as e:
                print(f"[warn] 添加 cookies 失败: {e}")
        results = []
        for idx, url in enumerate(links, start=1):
            print(f"[info] [{idx}/{len(links)}] 打开帖子: {url}")
            detail = context.new_page()
            detail.set_default_navigation_timeout(timeout_ms)
            detail.set_default_timeout(timeout_ms)
            try:
                detail.goto(url, wait_until='domcontentloaded')
                try:
                    detail.wait_for_load_state('load')
                except Exception:
                    pass
                try:
                    detail.wait_for_load_state('networkidle', timeout=2000)
                except Exception:
                    pass
            except PlaywrightTimeoutError:
                print(f"[warn] 打开帖子超时: {url}")
            detail.wait_for_timeout(1200)
            try:
                data = extract_post_content(detail, url)
            except Exception as e:
                print(f"[warn] 提取帖子内容失败: {e}")
                data = {
                    'url': url,
                    'note_id': None,
                    'title': '提取失败',
                    'description': '',
                    'content_text': '',
                    'images': [],
                    'videos': [],
                    'downloaded_images': [],
                }
            # 提取并下载轮播图片
            try:
                swiper_imgs = extract_swiper_images(detail)
                if swiper_imgs:
                    local_files = download_images(swiper_imgs, Path(out) / 'images', prefix=(data.get('note_id') or f'post-{idx}'), referer=url)
                    data['downloaded_images'] = [f"images/{Path(p).name}" for p in local_files]
            except Exception as e:
                print(f"[warn] 下载轮播图片失败: {e}")
            fname_base = data.get('note_id') or f"post-{idx}"
            safe_title = re.sub(r'[\\/:*?\"<>|]+', '_', data.get('title') or '')
            ext = 'html' if out_format == 'html' else 'md'
            filename = f"{fname_base}_{safe_title[:50]}.{ext}" if safe_title else f"{fname_base}.{ext}"
            if out_format == 'html':
                file_path = save_document(render_post_html(data), out, filename, skip_if_exists=False)
            else:
                file_path = save_document(render_post_markdown(data), out, filename, skip_if_exists=False)
            results.append({'file': os.path.basename(file_path), 'title': data.get('title'), 'url': url, 'note_id': data.get('note_id')})
            detail.close()
        # 合并已存在的索引，因为我们已经在处理前过滤了已存在的帖子
        index_html = build_index_html(results, out, merge_existing=skip_existing)
        index_md = build_index_markdown(results, out, merge_existing=skip_existing) if out_format == 'markdown' else None
        print(f"[done] 已保存 {len(results)} 个帖子。索引: {index_html}{' / ' + index_md if index_md else ''}")
        context.close()
        browser.close()

def parse_args():
    parser = argparse.ArgumentParser(description="小红书用户帖子爬取并保存为本地 HTML")
    parser.add_argument('--user', help='用户主页URL或用户ID，如 5d5cfae6cbe3d90001xxxxxx')
    parser.add_argument('--csv', help='从 CSV 文件读取帖子链接（第一列或 note_link 列）')
    parser.add_argument('--out', default='output', help='输出目录，默认 output')
    parser.add_argument('--cookies', help='可选的 cookies JSON 文件路径，需包含 www.xiaohongshu.com 的登录态')
    parser.add_argument('--limit', type=int, help='最多抓取的帖子数量，默认全部可见')
    parser.add_argument('--no-headless', action='store_true', help='使用有头模式以便观察或手动登录')
    parser.add_argument('--timeout', type=int, default=30000, help='页面加载/选择器超时时间（毫秒）')
    parser.add_argument('--user-agent', help='可选，自定义 User-Agent 字符串以提高稳定性')
    parser.add_argument('--format', choices=['html', 'markdown'], default='html', help='输出格式：html 或 markdown，默认 html')
    parser.add_argument('--skip-existing', action='store_true', help='跳过已存在的文件，不覆盖（会合并到索引中）')
    args = parser.parse_args()
    if not args.user and not args.csv:
        parser.error('必须提供 --user 或 --csv 之一')
    return args


if __name__ == '__main__':
    args = parse_args()
    if args.csv:
        run_from_csv(
            csv_path=args.csv,
            out=args.out,
            cookies_path=args.cookies,
            limit=args.limit,
            headless=not args.no_headless,
            timeout_ms=args.timeout,
            user_agent=args.user_agent,
            out_format=args.format,
            skip_existing=args.skip_existing,
        )
    else:
        run(
            user=args.user,
            out=args.out,
            cookies_path=args.cookies,
            limit=args.limit,
            headless=not args.no_headless,
            timeout_ms=args.timeout,
            user_agent=args.user_agent,
            out_format=args.format,
            skip_existing=args.skip_existing,
        )
