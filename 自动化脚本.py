import os
import json
import re

# 配置
ARTICLE_DIR = 'Article'
OUTPUT_JSON = 'articles.json'

def generate_articles_json():
    articles = []
    
    if not os.path.exists(ARTICLE_DIR):
        print(f"Error: 找不到文件夹 {ARTICLE_DIR}")
        return

    # 获取所有 .md 文件
    files = [f for f in os.listdir(ARTICLE_DIR) if f.endswith('.md')]

    for filename in files:
        # 1. 解析文件名：匹配前6位数字 (YYMMDD) + 标题
        # 模式：(6位数字)(标题).md
        match = re.match(r'^(\d{6})(.+)\.md$', filename)
        
        if match:
            date_code = match.group(1)  # e.g., "251221"
            title = match.group(2)     # e.g., "民族创伤评述"
            
            # 转化为 YYYY-MM-DD 格式
            formatted_date = f"20{date_code[0:2]}-{date_code[2:4]}-{date_code[4:6]}"
            
            try:
                with open(os.path.join(ARTICLE_DIR, filename), 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 2. 统计字数 (char_count)
                    # 排除掉空白字符，只计算实际文字内容
                    clean_content = re.sub(r'\s+', '', content)
                    char_count = len(clean_content)

                    # 3. 提取摘要：寻找第一个非空且不是标题或标签的行
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    excerpt = ""
                    for line in lines:
                        if not line.startswith('#') and not re.match(r'^(#[^\s#]+\s*)+$', line):
                            excerpt = line[:80] + "..."
                            break

                    # 4. 提取 Obsidian 风格标签 (#标签)
                    tags = re.findall(r'#([\u4e00-\u9fa5a-zA-Z0-9_-]+)', content)
                    unique_tags = list(set(tags))
                    if not unique_tags:
                        unique_tags = ["未分类"]

                    articles.append({
                        "file": filename,
                        "title": title,
                        "date": formatted_date,
                        "tags": unique_tags,
                        "excerpt": excerpt,
                        "char_count": char_count  # 新增字段用于 D3 渲染
                    })
            except Exception as e:
                print(f"读取 {filename} 出错: {e}")
        else:
            print(f"跳过命名格式不符的文件: {filename} (需要6位日期开头)")

    # 按日期倒序排序
    articles.sort(key=lambda x: x['date'], reverse=True)

    # 写入 JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 成功! 已更新 {OUTPUT_JSON}")
    print(f"📊 总计文章: {len(articles)} 篇")

if __name__ == "__main__":
    generate_articles_json()