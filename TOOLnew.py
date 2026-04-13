import os
import json
import re
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- 配置 ---
ARTICLE_DIR = 'Article'
DATA_DIR = 'data'  # 所有输出文件存放的文件夹
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2' 
SIMILARITY_THRESHOLD = 0.60  

# 确保输出目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# 动态拼接输出路径
OUTPUT_JSON = os.path.join(DATA_DIR, 'articles.json')
CACHE_FILE = os.path.join(DATA_DIR, 'embeddings_cache.json') 

# 语义分段配置
CHUNK_SIZE = 450    # 每个 Block 的理想最大字数
CHUNK_OVERLAP = 50  # 块之间重叠的字数，保持上下文连贯

def clean_text_for_chinese(text):
    """针对中文环境的精细化预处理"""
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_semantic_chunks(article):
    """
    语义化分段算法：注入标题元数据增强检索质量
    """
    title = article['title']
    tags_str = " ".join(article.get('tags', []))
    content = article.get('fullContent', '')
    
    paragraphs = content.split('\n')
    chunks = []
    header_info = f"{title} {tags_str} " 
    current_chunk = header_info
    
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        
        if len(para) > CHUNK_SIZE:
            sub_units = re.split(r'(?<=[。！？])', para)
        else:
            sub_units = [para]
            
        for unit in sub_units:
            unit = unit.strip()
            if not unit: continue
            
            if len(current_chunk) + len(unit) > CHUNK_SIZE:
                chunks.append(current_chunk.lower())
                overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else ""
                current_chunk = header_info + overlap_text + unit
            else:
                current_chunk += " " + unit
                
    if len(current_chunk) > len(header_info) + 5:
        chunks.append(current_chunk.lower())
        
    return chunks if chunks else [f"{title} {tags_str}".lower()]

def generate_articles_json():
    if not os.path.exists(ARTICLE_DIR):
        print(f"❌ Error: 找不到文件夹 {ARTICLE_DIR}")
        return

    # 1. 基础解析与元数据提取
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
    print(f"🔍 正在解析 {len(files)} 个 Markdown 文件...")

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
                    clean_content_len = len(re.sub(r'\s+', '', content))
                    
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    excerpt = ""
                    for line in lines:
                        if not line.startswith('#'):
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
                        "char_count": clean_content_len,
                        "fullContent": content,
                        "mtime": mtime,
                        "recommendations": [] # 预留推荐位
                    })
            except Exception as e:
                print(f"读取 {filename} 出错: {e}")

    # 2. 语义嵌入
    print(f"🚀 正在加载语义模型 {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    all_embeddings = []
    for a in articles:
        if a['file'] in cache and cache[a['file']]['mtime'] == a['mtime']:
            emb = np.array(cache[a['file']]['embedding'])
            new_cache[a['file']] = cache[a['file']]
        else:
            print(f"✨ 计算向量: {a['title']}")
            chunks = get_semantic_chunks(a)
            chunk_embs = model.encode(chunks) 
            combined_emb = np.mean(chunk_embs, axis=0)
            norm = np.linalg.norm(combined_emb)
            emb = combined_emb / norm if norm > 0 else combined_emb
            
            new_cache[a['file']] = {
                "mtime": a['mtime'],
                "embedding": emb.tolist()
            }
        all_embeddings.append(emb)

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_cache, f)

    # 3. 计算全局关联 & 生成节点专属推荐
    print("🧠 正在构建语义关联矩阵...")
    links = []
    if len(all_embeddings) > 1:
        sim_matrix = cosine_similarity(all_embeddings)
        
        for i in range(len(articles)):
            current_article_scores = []
            
            for j in range(len(articles)):
                if i == j: continue  # 不推荐自己
                
                score = float(sim_matrix[i][j])
                
                # 记录到全局 links (用于星图连线，需满足阈值)
                if j > i and score > SIMILARITY_THRESHOLD:
                    links.append({
                        "source": articles[i]['file'],
                        "target": articles[j]['file'],
                        "weight": round(score, 3)
                    })
                
                # 记录该文章的所有关联得分，用于后续 Top 5 排序
                current_article_scores.append({
                    "file": articles[j]['file'],
                    "title": articles[j]['title'],
                    "date": articles[j]['date'],
                    "excerpt": articles[j]['excerpt'],
                    "weight": round(score, 3)
                })
            
            # 排序并取前 5 个最相关的
            articles[i]['recommendations'] = sorted(
                current_article_scores, 
                key=lambda x: x['weight'], 
                reverse=True
            )[:5]

    # 4. 最终排序与保存
    articles.sort(key=lambda x: x['date'], reverse=True)

    final_data = {
        "nodes": articles,
        "links": links,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 处理完成！推荐数据已注入节点。")
    print(f"📊 统计：{len(articles)} 篇文章 | {len(links)} 条语义关联")

if __name__ == "__main__":
    generate_articles_json()