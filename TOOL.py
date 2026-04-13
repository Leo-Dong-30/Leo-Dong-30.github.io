import os
import json
import re
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# --- 配置 ---
ARTICLE_DIR = 'Article'
OUTPUT_JSON = 'articles.json'
CACHE_FILE = 'embeddings_cache.json' 
MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2' 
SIMILARITY_THRESHOLD = 0.60  

# 语义分段配置
CHUNK_SIZE = 450    # 每个 Block 的理想最大字数
CHUNK_OVERLAP = 50  # 块之间重叠的字数，保持上下文连贯

def clean_text_for_chinese(text):
    """针对中文环境的精细化预处理"""
    # 去除 Markdown 链接语法 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 合并多余空格和换行
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_semantic_chunks(article):
    """
    语义化分段核心算法：
    1. 优先按段落切分
    2. 超长段落按句子(。！？)切分
    3. 智能合并，并注入标题信息增强语义
    """
    title = article['title']
    tags_str = " ".join(article.get('tags', []))
    content = article.get('fullContent', '')
    
    # 清洗后的正文
    clean_content = clean_text_for_chinese(content)
    
    # 1. 初始切分单位：段落
    paragraphs = content.split('\n')
    
    chunks = []
    # 初始元数据注入：让每个分段都带有标题和标签的信息，增强检索质量
    header_info = f"{title} {tags_str} " 
    current_chunk = header_info
    
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        
        # 如果单段内容过长，进一步按句子切分
        if len(para) > CHUNK_SIZE:
            sub_units = re.split(r'(?<=[。！？])', para)
        else:
            sub_units = [para]
            
        for unit in sub_units:
            unit = unit.strip()
            if not unit: continue
            
            # 检查加入当前单位后是否溢出
            if len(current_chunk) + len(unit) > CHUNK_SIZE:
                chunks.append(current_chunk.lower())
                # 保持 Overlap 重叠，并重新注入标题元数据
                overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else ""
                current_chunk = header_info + overlap_text + unit
            else:
                current_chunk += " " + unit
                
    # 补齐最后一个块
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
        # 正则匹配日期和标题 (格式需为: YYMMDD标题.md)
        match = re.match(r'^(\d{6})(.+)\.md$', filename)
        if match:
            date_code, title = match.group(1), match.group(2)
            formatted_date = f"20{date_code[0:2]}-{date_code[2:4]}-{date_code[4:6]}"
            
            try:
                filepath = os.path.join(ARTICLE_DIR, filename)
                mtime = os.path.getmtime(filepath)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 统计字数（去除空白符）
                    clean_content_len = len(re.sub(r'\s+', '', content))
                    
                    # 摘要提取：跳过标题行和标签行，取第一段有效文本
                    lines = [l.strip() for l in content.split('\n') if l.strip()]
                    excerpt = ""
                    for line in lines:
                        if not line.startswith('#'):
                            excerpt = line[:100].replace('"', "'") + "..."
                            break

                    # 标签提取
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
                        "mtime": mtime
                    })
            except Exception as e:
                print(f"读取 {filename} 出错: {e}")

    # 2. 语义嵌入 (语义分段平均法)
    print(f"🚀 正在加载语义模型 {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)

    all_embeddings = []
    for a in articles:
        # 缓存校验：如果文件未修改，直接读取旧向量
        if a['file'] in cache and cache[a['file']]['mtime'] == a['mtime']:
            emb = np.array(cache[a['file']]['embedding'])
            new_cache[a['file']] = cache[a['file']]
        else:
            print(f"✨ 语义切分并计算向量: {a['title']}")
            chunks = get_semantic_chunks(a)
            
            # 对所有分段批量编码
            chunk_embs = model.encode(chunks) 
            
            # Mean Pooling：对多个段落向量取平均值，代表全文语义
            combined_emb = np.mean(chunk_embs, axis=0)
            
            # 归一化处理（确保余弦相似度计算更准确）
            norm = np.linalg.norm(combined_emb)
            emb = combined_emb / norm if norm > 0 else combined_emb
            
            new_cache[a['file']] = {
                "mtime": a['mtime'],
                "embedding": emb.tolist()
            }
        
        all_embeddings.append(emb)

    # 持久化缓存
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_cache, f)

    # 3. 计算余弦相似度构建关联
    print("🧠 正在计算全局语义关联...")
    links = []
    if len(all_embeddings) > 1:
        sim_matrix = cosine_similarity(all_embeddings)
        for i in range(len(articles)):
            for j in range(i + 1, len(articles)):
                score = float(sim_matrix[i][j])
                if score > SIMILARITY_THRESHOLD:
                    links.append({
                        "source": articles[i]['file'],
                        "target": articles[j]['file'],
                        "weight": round(score, 3)
                    })

    # 4. 最终排序输出
    articles.sort(key=lambda x: x['date'], reverse=True)

    final_data = {
        "nodes": articles,
        "links": links,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 处理完成！")
    print(f"📊 统计：{len(articles)} 篇文章 | {len(links)} 条语义关联 | 阈值: {SIMILARITY_THRESHOLD}")

if __name__ == "__main__":
    generate_articles_json()