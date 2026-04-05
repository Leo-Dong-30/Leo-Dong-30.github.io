import os
import json
import re
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


# --- 配置 ---
ARTICLE_DIR = 'Article'
OUTPUT_JSON = 'articles.json'
CACHE_FILE = 'embeddings_cache.json' 
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2' 
SIMILARITY_THRESHOLD = 0.60  

# 分段配置
CHUNK_SIZE = 450   # 每一段的字数，建议在 400-500 之间
CHUNK_OVERLAP = 50 # 段落重叠字数，保证语义连贯

def get_text_chunks(article):
    """将文章内容切分为多个片段，以克服模型输入长度限制"""
    tags_str = " ".join(article.get('tags', []))
    title = article['title']
    # 拿到全文内容，去掉多余换行
    full_content = article.get('fullContent', '').replace('\n', ' ')
    
    # 组合待处理的完整文本
    full_text = f"{title} {tags_str} {full_content}".lower()
    
    # 如果文本很短，直接返回
    if len(full_text) <= CHUNK_SIZE:
        return [full_text]
    
    # 滚动窗口切分
    chunks = []
    for i in range(0, len(full_text), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = full_text[i : i + CHUNK_SIZE]
        if len(chunk) > 10:  # 过滤掉无意义的微小末尾
            chunks.append(chunk)
    return chunks

def generate_articles_json():
    if not os.path.exists(ARTICLE_DIR):
        print(f"❌ Error: 找不到文件夹 {ARTICLE_DIR}")
        return

    # 1. 基础解析
    articles = []
    files = [f for f in os.listdir(ARTICLE_DIR) if f.endswith('.md')]
    
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except:
            cache = {}

    new_cache = {}
    
    # 预先扫描所有文件信息
    for filename in files:
        match = re.match(r'^(\d{6})(.+)\.md$', filename)
        if match:
            date_code, title = match.group(1), match.group(2)
            formatted_date = f"20{date_code[0:2]}-{date_code[2:4]}-{date_code[4:6]}"
            
            try:
                filepath = os.path.join(ARTICLE_DIR, filename)
                mtime = os.path.getmtime(filepath)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    clean_content = re.sub(r'\s+', '', content)
                    
                    # 摘要提取
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    excerpt = ""
                    for line in lines:
                        if not line.startswith('#') and not re.match(r'^(#[^\s#]+\s*)+$', line):
                            excerpt = line[:100].replace('"', "'") + "..."
                            break

                    tags = re.findall(r'#([\u4e00-\u9fa5a-zA-Z0-9_-]+)', content)
                    unique_tags = list(set(tags)) if tags else ["未分类"]

                    articles.append({
                        "file": filename,
                        "title": title,
                        "date": formatted_date,
                        "tags": unique_tags,
                        "excerpt": excerpt,
                        "char_count": len(clean_content),
                        "fullContent": content,
                        "mtime": mtime
                    })
            except Exception as e:
                print(f"读取 {filename} 出错: {e}")

    # 2. 语义嵌入 (分段平均法)
    print(f"正在加载语义模型 {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    all_embeddings = []
    for a in articles:
        # 缓存命中校验
        if a['file'] in cache and cache[a['file']]['mtime'] == a['mtime']:
            emb = np.array(cache[a['file']]['embedding'])
            new_cache[a['file']] = cache[a['file']]
        else:
            print(f"正在分段处理长文本: {a['title']}")
            chunks = get_text_chunks(a)
            
            # 对所有分段批量编码
            chunk_embs = model.encode(chunks) 
            
            # 对多个段落向量取平均值 (Mean Pooling)
            combined_emb = np.mean(chunk_embs, axis=0)
            
            # 归一化处理（使单位向量化，余弦相似度更稳定）
            norm = np.linalg.norm(combined_emb)
            emb = combined_emb / norm if norm > 0 else combined_emb
            
            new_cache[a['file']] = {
                "mtime": a['mtime'],
                "embedding": emb.tolist()
            }
        
        all_embeddings.append(emb)

    # 保存缓存
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_cache, f)

    # 3. 计算余弦相似度
    print("正在计算全局语义关联...")
    links = []
    if len(all_embeddings) > 1:
        sim_matrix = cosine_similarity(all_embeddings)
        print('要画图了')
        plot_similarity_heatmap(sim_matrix, articles)
        for i in range(len(articles)):
            for j in range(i + 1, len(articles)):
                score = float(sim_matrix[i][j])
                if score > SIMILARITY_THRESHOLD:
                    links.append({
                        "source": articles[i]['file'],
                        "target": articles[j]['file'],
                        "weight": round(score, 3)
                    })

    # 4. 输出
    articles.sort(key=lambda x: x['date'], reverse=True)
    
    final_data = {
        "nodes": articles,
        "links": links
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 处理完成！")
    print(f"📊 统计：{len(articles)} 篇文章 | {len(links)} 条跨文本关联")

def plot_similarity_heatmap(sim_matrix, articles, output_file='similarity_heatmap.png'):
    # 设置字体以支持中文（匹配你喜欢的楷体风格）
    plt.rcParams['font.sans-serif'] = ['STKaiti', 'KaiTi', 'SimHei'] 
    plt.rcParams['axes.unicode_minus'] = False

    titles = [a['title'] for a in articles]
    
    plt.figure(figsize=(12, 10))
    # 使用自然色调的调色板 (YlGnBu)
    sns.heatmap(sim_matrix, 
                xticklabels=titles, 
                yticklabels=titles, 
                cmap="YlGnBu", 
                annot=False, # 如果文章太多，建议关闭数字标注
                cbar_kws={'label': 'Cosine Similarity'})
    
    plt.title("LeoBlog 全局语义关联热力图", fontsize=15)
    plt.xticks(rotation=45, ha='right', fontsize=9)
    plt.yticks(fontsize=9)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"✅ 全量热力图已生成：{output_file}")

if __name__ == "__main__":
    generate_articles_json()
    
