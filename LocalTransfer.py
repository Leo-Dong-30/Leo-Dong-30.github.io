import os
import socket
import logging
import qrcode
from flask import Flask, request, render_template_string, send_from_directory, redirect, url_for

# 1. 基础配置
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# 2. HTML 模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>局域网文件互传</title>
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f7f6; color: #333; display: flex; flex-direction: column; align-items: center; padding: 20px; }
        .card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); width: 100%; max-width: 500px; margin-bottom: 20px; }
        h3 { margin-top: 0; color: #1a73e8; border-bottom: 1px solid #eee; padding-bottom: 10px; }
        .ip-tag { font-size: 12px; color: #888; margin-bottom: 15px; display: block; }
        
        /* 上传区域 */
        .upload-section { text-align: center; }
        input[type="file"] { margin: 15px 0; width: 100%; }
        button { background: #1a73e8; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; width: 100%; font-size: 16px; font-weight: 500; }
        #status { margin-top: 10px; font-size: 13px; min-height: 1.5em; }

        /* 文件列表区域 */
        .file-list { list-style: none; padding: 0; margin: 0; max-height: 300px; overflow-y: auto; }
        .file-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
        .file-item:last-child { border-bottom: none; }
        .file-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; padding-right: 10px; }
        .download-btn { color: #1a73e8; text-decoration: none; font-weight: bold; font-size: 12px; border: 1px solid #1a73e8; padding: 2px 8px; border-radius: 4px; }
        .empty-hint { color: #999; text-align: center; padding: 20px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="card">
        <h3>⬆️ 上传文件到电脑</h3>
        <span class="ip-tag">服务器地址: {{ server_ip }}</span>
        <div class="upload-section">
            <input type="file" id="fileInput" multiple>
            <button onclick="uploadFiles()">开始上传</button>
            <div id="status">等待操作...</div>
        </div>
    </div>

    <div class="card">
        <h3>📂 电脑上的文件 (点击下载)</h3>
        <ul class="file-list" id="fileList">
            {% if files %}
                {% for file in files %}
                <li class="file-item">
                    <span class="file-name" title="{{ file }}">{{ file }}</span>
                    <a href="/download/{{ file }}" class="download-btn">下载</a>
                </li>
                {% endfor %}
            {% else %}
                <div class="empty-hint">暂无文件，快从手机传一个吧！</div>
            {% endif %}
        </ul>
    </div>

    <script>
        function uploadFiles() {
            const fileInput = document.getElementById('fileInput');
            const status = document.getElementById('status');
            const files = fileInput.files;

            if (files.length === 0) {
                status.innerText = "❌ 请先选择文件";
                status.style.color = "#d93025";
                return;
            }

            const formData = new FormData();
            // 关键点 2: 循环将所有选中的文件加入 FormData
            for (let i = 0; i < files.length; i++) {
                formData.append('files', files[i]);
            }

            status.innerText = `⏳ 正在传输 ${files.length} 个文件...`;
            status.style.color = "#1a73e8";
            
            fetch('/upload', { method: 'POST', body: formData })
            .then(res => res.json())
            .then(data => {
                status.style.color = "#188038";
                status.innerText = `✅ 成功上传 ${files.length} 个文件！`;
                fileInput.value = '';
                // 上传成功后刷新页面以更新文件列表
                setTimeout(() => location.reload(), 1500);
            })
            .catch(err => {
                status.style.color = "#d93025";
                status.innerText = "❌ 传输失败，请检查网络";
            });
        }
    </script>
</body>
</html>
"""

# 3. 路由逻辑
@app.route('/')
def index():
    # 获取上传目录下的所有文件并按时间倒序排列（新文件在上）
    files = sorted(os.listdir(app.config['UPLOAD_FOLDER']), 
                   key=lambda x: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], x)), 
                   reverse=True)
    return render_template_string(HTML_TEMPLATE, server_ip=get_local_ip(), files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    # 关键点 3: 获取多个文件对象
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return {"status": "error", "message": "No files"}, 400
    
    for file in uploaded_files:
        if file.filename:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file.filename))
            print(f"成功接收: {file.filename}")
            
    return {"status": "success", "count": len(uploaded_files)}

@app.route('/download/<filename>')
def download_file(filename):
    # 关键点 4: 提供文件下载功能
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# 4. 启动入口
if __name__ == '__main__':
    local_ip = get_local_ip()
    port = 5000
    target_url = f"http://{local_ip}:{port}"
    
    print("="*50)
    print(f"全功能互传服务启动！")
    print("-" * 50)
    
    qr = qrcode.QRCode(version=1, border=1)
    qr.add_data(target_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    
    print("-" * 50)
    print(f"手机扫码访问: {target_url}")
    print("="*50)
    
    app.run(host='0.0.0.0', port=port, debug=False)