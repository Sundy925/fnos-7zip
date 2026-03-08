import os
import sys
import subprocess
import fnmatch
import re
import shutil
import struct


# 将 libs 目录添加到系统路径，以便导入依赖库
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, 'libs'))

from flask import Flask, render_template, request, jsonify

import json

app = Flask(__name__)

# 7zz 可执行文件的路径，位于当前目录下的 bin 目录中
SEVEN_ZIP_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bin', '7zz')

def load_config():
    """
    加载应用程序配置。
    优先从环境变量 PKG_CONFIG_PATH 指定的路径加载 config.json。
    如果配置文件不存在，则创建默认配置。
    支持 Docker 环境变量 DOCKER_MOUNT_PATHS 配置多个挂载路径。
    """
    config_path = os.environ.get('PKG_CONFIG_PATH', 'config.json')
    
    pkg_var = os.environ.get('TRIM_PKGVAR')
    if pkg_var:
        if not os.path.exists(pkg_var):
            try:
                os.makedirs(pkg_var, exist_ok=True)
            except:
                pass
        config_path = os.path.join(pkg_var, 'config.json')
    
    config_dir = os.path.dirname(config_path)
    if config_dir and not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
        except:
            pass
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get('roots', []), data.get('settings', {}), config_path
        except Exception as e:
            print(f"Error loading config: {e}")
            return [], {}, config_path
            
    roots = []
    
    # Docker 环境变量 DOCKER_MOUNT_PATHS 用于配置挂载路径，格式: /path1:/name1,/path2:/name2
    # 或者使用冒号分隔的路径格式: /path1:/path2
    docker_paths = os.environ.get('DOCKER_MOUNT_PATHS')
    if docker_paths:
        # 支持两种格式：
        # 1. /path1:/name1,/path2:/name2 (逗号分隔，path:name)
        # 2. /path1:/path2 (冒号分隔的多个路径)
        if ',' in docker_paths:
            for item in docker_paths.split(','):
                if ':' in item:
                    path, name = item.split(':', 1)
                    path = path.strip()
                    name = name.strip()
                    if path and os.path.isdir(path):
                        roots.append({'name': name, 'path': path})
        else:
            for path in docker_paths.split(':'):
                path = path.strip()
                if path and os.path.isdir(path):
                    roots.append({'name': os.path.basename(path) or path, 'path': path})
    
    # 如果没有从环境变量获取到路径，使用默认路径
    if not roots:
        # 检查常见的挂载点
        default_paths = [
            ('/host_fs', 'Host Root'),
            ('/config', 'Config'),
            ('/home', 'Home'),
            ('/', 'Root'),
        ]
        for path, name in default_paths:
            if os.path.isdir(path):
                roots.append({'name': name, 'path': path})
                break
        else:
            roots = [{'name': 'Root', 'path': '/'}]
    
    settings = {}
    
    try:
        with open(config_path, 'w') as f:
            json.dump({'roots': roots, 'settings': settings}, f, indent=4)
    except Exception as e:
        print(f"Error saving default config: {e}")
        
    return roots, settings, config_path

@app.route('/')
def index():
    """渲染主页 HTML 模板"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """
    API: 获取当前配置
    返回根目录列表、设置项以及配置文件路径。
    如果根目录列表为空，则默认返回系统根目录 '/'。
    """
    roots, settings, config_path = load_config()
    # 如果配置为空（例如文件为空或 roots 数组为空），回退到系统根目录
    if not roots:
        roots = [{'name': 'Root', 'path': '/'}]
    return jsonify({'roots': roots, 'settings': settings, 'config_path': config_path})

@app.route('/api/save-settings', methods=['POST'])
def save_settings():
    """
    API: 保存用户设置
    接收 JSON 格式的设置项并更新到配置文件中。
    """
    new_settings = request.json
    roots, current_settings, config_path = load_config()
    
    # 更新设置字典
    current_settings.update(new_settings)
    
    try:
        with open(config_path, 'w') as f:
            json.dump({'roots': roots, 'settings': current_settings}, f, indent=4)
        return jsonify({'success': True, 'settings': current_settings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/list-files', methods=['GET'])
def list_files():
    """
    API: 列出文件或目录内容
    支持列出本地文件系统的目录内容，以及浏览归档文件（如 zip, tar.gz）的内部结构（虚拟路径）。
    """
    path = request.args.get('path', '/')
    
    # 1. 检查是否为真实存在的文件系统路径
    if os.path.exists(path):
        # 如果浏览的是真实路径，清理之前的归档解压缓存
        cleanup_archive_cache()
        
        # 如果是文件，返回文件信息
        if os.path.isfile(path):
            return jsonify({
                'current_path': path, 
                'is_file': True,
                'parent': os.path.dirname(path),
                'name': os.path.basename(path)
            })
        
        # 如果是目录，列出目录内容
        try:
            items = []
            with os.scandir(path) as it:
                for entry in it:
                    try:
                        stat = entry.stat()
                        items.append({
                            'name': entry.name,
                            'is_dir': entry.is_dir(),
                            'path': entry.path,
                            'size': stat.st_size if not entry.is_dir() else 0,
                            'mtime': stat.st_mtime
                        })
                    except OSError:
                        continue # 跳过无法访问的文件
                        
            # 排序：目录在前，然后按文件名排序
            items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            return jsonify({'current_path': path, 'items': items})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # 2. 如果路径不存在，检查是否为归档文件内部的虚拟路径
    # 尝试找到路径中的归档文件部分
    archive_path, internal_path = find_archive_path(path)
    
    if archive_path:
        return list_archive_content(archive_path, internal_path, path)
    
    return jsonify({'error': 'Path does not exist'}), 404

def find_archive_path(virtual_path):
    """
    辅助函数：查找路径中的归档文件。
    向上遍历路径，检查父级是否为一个存在的归档文件。
    返回 (归档文件路径, 归档内部路径) 或 (None, None)。
    """
    parent = virtual_path
    internal_parts = []
    
    # 限制递归深度，防止死循环
    depth = 0
    while parent != '/' and parent != '' and depth < 20:
        if os.path.isfile(parent):
            # 找到潜在的归档文件
            return parent, "/".join(internal_parts)
            
        internal_parts.insert(0, os.path.basename(parent))
        parent = os.path.dirname(parent)
        depth += 1
        
    return None, None

def list_archive_content(archive_path, internal_path, full_virtual_path, origin_path=None):
    """
    核心函数：列出归档文件内容。
    处理归档文件的列表获取、前缀剥离、以及嵌套归档（如 tar.gz）的自动进入逻辑。
    """
    if origin_path is None:
        origin_path = archive_path

    try:
        # 加载配置以获取临时解压大小限制
        _, settings, _ = load_config()
        try:
            max_mb = int(settings.get('temp_extract_max_mb', 100))
        except:
            max_mb = 100
        threshold_bytes = max_mb * 1024 * 1024

        # 获取归档内的所有条目
        all_items = get_archive_items(archive_path)
        
        # 剥离公共前缀（例如压缩包内所有文件都在一个顶级目录下，直接显示该目录内容）
        all_items = strip_common_prefix_from_archive(all_items, archive_path)
        
        if isinstance(all_items, dict) and 'error' in all_items:
            return jsonify(all_items), 500
            
        # 规范化内部路径
        internal_path = internal_path.strip('/')
        
        # 1. 处理 .tar.gz / .tgz / .tar.zst / .zip.zst 等嵌套归档的特殊情况
        # 扩展通用逻辑：任何单一文件压缩格式（如 gz, zst, xz, bz2, lz4 等），
        # 如果内部没有文件名信息（7zz l 仅显示 Type, Size, 且 Path 与外层相同或为空），
        # 或者我们知道它是常见双重扩展名（如 tar.gz），我们都尝试推断内部文件名并进入。
        
        parts = []
        lower_archive = archive_path.lower()
        
        # 常见嵌套归档扩展名
        nested_exts = ('.tar.gz', '.tgz', '.tar.zst', '.tar.xz', '.tar.bz2', '.tar.br', '.tar.lz4', '.tar.lz', '.zip.zst', '.gz', '.zst', '.xz', '.bz2', '.lz4', '.br', '.lz')
        
        if lower_archive.endswith(nested_exts):
             # 查找内部的 .tar 或其他被压缩文件
             # 优先查找 .tar
            tar_items = [x for x in all_items if x['path'].lower().endswith('.tar')]
            
            # 如果没有显式的 .tar，但这是已知压缩格式，且列表为空或没有有效文件名
            # 我们尝试构造一个推断的内部项
            
            # 推断内部文件名
            base = os.path.basename(archive_path)
            inferred_name = None
            
            # 处理双重扩展名
            double_exts = {
                '.tar.gz': '.tar', '.tgz': '.tar',
                '.tar.zst': '.tar', '.tzst': '.tar',
                '.tar.xz': '.tar', '.txz': '.tar',
                '.tar.bz2': '.tar', '.tbz2': '.tar',
                '.tar.br': '.tar',
                '.tar.lz4': '.tar',
                '.tar.lz': '.tar',
                '.zip.zst': '.zip' 
            }
            
            for ext, inner in double_exts.items():
                if lower_archive.endswith(ext):
                    inferred_name = base[:-len(ext)] + inner
                    break
            
            # 如果不是已知双重扩展，尝试去除最后一个扩展名
            if not inferred_name:
                if '.' in base:
                    inferred_name = os.path.splitext(base)[0]
                else:
                    inferred_name = base + '.out' # Fallback

            if not tar_items:
                 # 检查是否是 "无文件名" 的情况
                 # 7zz l 对 zst/gz 等 raw 流，往往没有内部文件名
                 # 或者 all_items 只有一项且名字和压缩包一样？
                 
                 # 构造一个虚拟项
                 # 只有当 all_items 为空（7zz l 没有输出内部文件）或者没有有意义的文件名时才添加
                 # 7zz l zstd 输出通常没有文件项
                 # 或者 all_items 不为空，但没有包含文件名（有些版本的 7zip 可能会输出？）
                 # 实际上 get_archive_items 解析时，如果没有 Path 字段，就不会添加 item
                 # 所以如果 7zz l 输出没有 Path = ... 的块，all_items 就是空的。
                 
                 if not all_items:
                     # 大小未知，设为 0
                     tar_items = [{
                         'path': inferred_name,
                         'name': inferred_name,
                         'is_dir': False,
                         'size': 0, # Unknown size
                         'mtime': 0
                     }]
                 elif len(all_items) == 1 and (all_items[0]['name'] == base or not all_items[0]['name']):
                      # 只有一个文件，且名字与压缩包相同（可能解析错误？）或者名字为空
                      tar_items = [{
                         'path': inferred_name,
                         'name': inferred_name,
                         'is_dir': False,
                         'size': all_items[0]['size'], # Use reported size if any
                         'mtime': all_items[0]['mtime']
                      }]

            if tar_items:
                # ... existing selection logic ...
                # 简化选择逻辑：如果有显式的 .tar，优先用；否则用推断的
                # 但要注意 tar_items 现在可能包含我们构造的虚拟项
                
                # 如果 all_items 里有真实的 tar，优先用真实的
                real_tars = [x for x in all_items if x['path'].lower().endswith('.tar')]
                if real_tars:
                     chosen = real_tars[0]
                else:
                     chosen = tar_items[0]
                
                # 通用策略：
                # 1. 如果 size <= threshold: 临时解压 (Extract)
                # 2. 如果 size > threshold: 流式列表 (Pipe List)
       
                try:
                    outer_size = os.path.getsize(archive_path)
                except:
                    outer_size = float('inf')
                
                # 判断是否应该使用 Pipe
                # 条件：outer_size > threshold 
                # 或者 internal item size (if known) > threshold
                
                use_pipe = False
                if outer_size > threshold_bytes:
                    use_pipe = True
                elif chosen.get('size', 0) > threshold_bytes:
                    use_pipe = True
                else:
                    use_pipe = False
                
                # 如果决定 Extract (use_pipe = False)
                if not use_pipe:
                    item = chosen
                    current_check = item['path'] # 这是推断的或真实的文件名
                    
                    # ... Extract logic ...
                    # 注意：对于推断的文件名，解压时可能不需要指定 current_check，
                    # 而是直接 x archive_path -o...
                    # 因为 7zz x archive.zst 会自动解压出内容，文件名由 7zz 决定或我们重命名。
                    
                    # 发现嵌套归档，准备解压到临时目录
                    temp_dir = os.environ.get('TRIM_PKGTMP', '/tmp')
                    cache_dir = os.path.join(temp_dir, 'archive_cache')
                    os.makedirs(cache_dir, exist_ok=True)
                    
                    import hashlib
                    unique_str = f"{archive_path}:{current_check}"
                    unique_hash = hashlib.md5(unique_str.encode()).hexdigest()
                    # 使用推断的扩展名或默认
                    ext = os.path.splitext(item['name'])[1]
                    temp_archive_path = os.path.join(cache_dir, f"{unique_hash}{ext}")
                    
                    need_extract = True
                    if os.path.exists(temp_archive_path):
                        if item['size'] > 0:
                            if os.path.getsize(temp_archive_path) == item['size']:
                                need_extract = False
                        elif os.path.getsize(temp_archive_path) > 0:
                             need_extract = False
                    
                    if need_extract:
                        extract_tmp = os.path.join(cache_dir, f"tmp_{unique_hash}")
                        if os.path.exists(extract_tmp):
                            shutil.rmtree(extract_tmp)
                        
                        # 构建解压命令
                        # 如果是 known single file formats without internal names (zst, gz, etc)
                        # 直接 x archive -o
                        # 怎么判断？如果 item.size == 0 且我们是在处理 nested_exts
                        # 或者 tar_items 是我们构造的
                        
                        is_constructed = (item.get('size') == 0 and item['name'] == inferred_name)
                        
                        if is_constructed:
                             cmd = [SEVEN_ZIP_BIN, 'x', archive_path, f'-o{extract_tmp}', '-y']
                        else:
                             cmd = [SEVEN_ZIP_BIN, 'x', archive_path, f'-o{extract_tmp}', current_check, '-y']
                             
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        out, err = proc.communicate()
                        
                        if proc.returncode != 0:
                            # Extract failed? Try Pipe fallback?
                            # return jsonify({'error': ...})
                            # 暂时报错
                            return jsonify({'error': f"Failed to extract nested archive: {err}"}), 500
                            
                        # 移动文件
                        # 逻辑同前：找提取出的文件
                        found_file = None
                        extracted_target = os.path.join(extract_tmp, current_check)
                        
                        if os.path.exists(extracted_target) and os.path.isfile(extracted_target):
                            found_file = extracted_target
                        else:
                             # 遍历寻找
                             for root, dirs, files in os.walk(extract_tmp):
                                 if files:
                                     found_file = os.path.join(root, files[0])
                                     break
                        
                        if found_file:
                            shutil.move(found_file, temp_archive_path)
                            shutil.rmtree(extract_tmp)
                        else:
                             return jsonify({'error': f"Extracted file not found in {extract_tmp}"}), 500
                    
                    return list_archive_content(temp_archive_path, internal_path, full_virtual_path, origin_path=origin_path)
                
                else:
                    # use_pipe = True
                    # 流式处理
                    item = chosen
                    current_check = item['path']
                    
                    try:
                        # 构造 pipe 命令
                        # 1. 解压流
                        # 对于 zst/gz 等，直接 x -so 输出内容
                        # 对于 tar 中包含的 tar，需要指定文件名
                        
                        is_constructed = (item.get('size') == 0 and item.get('name') == inferred_name)
                        
                        if is_constructed:
                             cmd1 = [SEVEN_ZIP_BIN, 'x', archive_path, '-so']
                        else:
                             cmd1 = [SEVEN_ZIP_BIN, 'x', archive_path, current_check, '-so']
                        
                        # 2. 列表流
                        # 这里的关键是 -ttar。如果内部不是 tar 怎么办？
                        # 比如 zip.zst -> zip。我们需要 -tzip 吗？
                        # 7zz l -si 默认会自动检测格式吗？
                        # 7zz l -si 需要指定类型吗？
                        # 7-Zip help: "l (List) command ... -si switch ... checks for signature"
                        # 通常 -si 需要 -tType 指定类型，因为 stdin 不可 seek，无法从末尾读 central directory (zip)。
                        # 但 tar 可以。
                        # 对于 zip，7zz l -si 可能不支持？因为 zip 目录在最后。
                        # 这是一个限制。7zip 支持从 stdin 解压 zip (x -si)，但 list (l -si) 可能不行？
                        # 验证：7zz l -si -tzip < test.zip
                        # 如果不行，那 zip.zst 大文件流式浏览就无法实现。
                        # 
                        # 假设用户主要关注 tar.zst。
                        # 对于 zip.zst，如果 7zz 不支持 l -si，我们只能报错或强行解压（但这违反了阈值）。
                        # 
                        # 让我们尝试不加 -t 参数，让 7zz 自己猜？或者根据 inferred name 猜？
                        
                        type_switch = []
                        if item['name'].endswith('.tar'):
                            type_switch = ['-ttar']
                        elif item['name'].endswith('.zip'):
                            type_switch = ['-tzip']
                        
                        # 修正：zip 格式不支持流式列表（因为 index 在尾部）。
                        # 如果是 zip，必须解压到临时文件？
                        # 或者：如果 outer_size > threshold，我们也没办法，只能试一下 pipe。
                        # 如果 pipe 失败，那也没辙。
                        
                        cmd2 = [SEVEN_ZIP_BIN, 'l', '-si'] + type_switch + ['-slt']
                        
                        p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # 特殊处理 zip 格式：7zz l -si 不支持 zip，使用 Python 自定义解析
                        if type_switch == ['-tzip']:
                            nested_items = list_zip_stream(p1.stdout)
                            p1.stdout.close()
                            # 既然我们手动解析了，就不需要运行 p2 (7zz l)
                            # 但需要确保 p1 结束
                            p1.wait()
                            
                            # 构造 filter_children 需要的格式
                            # list_zip_stream 返回的 items 已经包含了 path, name, is_dir, size, mtime
                            
                            remaining_path = internal_path
                            filtered_items = filter_children(nested_items, remaining_path, full_virtual_path)
                            filtered_items = [x for x in filtered_items if x['name'] and x['name'].strip()]
                            
                            return jsonify({
                                'current_path': full_virtual_path, 
                                'items': filtered_items,
                                'is_archive': True,
                                'archive_path': archive_path,
                                'origin_path': origin_path,
                                'internal_path': internal_path
                            })
                        
                        p2 = subprocess.Popen(cmd2, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                        p1.stdout.close()
                        stdout, stderr = p2.communicate()
                        
                        if p2.returncode == 0:
                            nested_items = []
                            current_block = {}
                            lines = stdout.split('\n')
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    if current_block and 'Path' in current_block:
                                        parse_block(current_block, nested_items)
                                    current_block = {}
                                    continue
                                
                                if ' = ' in line:
                                    key, value = line.split(' = ', 1)
                                    current_block[key] = value
                            
                            if current_block and 'Path' in current_block:
                                parse_block(current_block, nested_items)
                            
                            # 过滤子项
                            remaining_path = internal_path
                            
                            filtered_items = filter_children(nested_items, remaining_path, full_virtual_path)
                            filtered_items = [x for x in filtered_items if x['name'] and x['name'].strip()]
                            
                            return jsonify({
                                'current_path': full_virtual_path, 
                                'items': filtered_items,
                                'is_archive': True,
                                'archive_path': archive_path,
                                'origin_path': origin_path,
                                'internal_path': internal_path
                            })
                        else:
                            # Pipe 失败
                            print(f"Pipe listing failed: {stderr}")
                            pass
                            
                    except Exception as e:
                        pass
                        
                    # ... Return result ...

        if internal_path:
            parts = internal_path.split('/')

        current_check = ""
        
        # 遍历路径部分，处理嵌套归档的解压和递归浏览
        for i, part in enumerate(parts):
            current_check = os.path.join(current_check, part) if current_check else part
            # 在所有条目中查找当前路径对应的项
            item = next((x for x in all_items if x['path'] == current_check), None)
            
            if item and not item['is_dir']:
                # 如果是文件，检查是否为支持的归档格式
                ext = item['name'].split('.').pop().lower() if '.' in item['name'] else ''
                
                supported_exts = ['7z', 'zip', 'tar', 'gz', 'xz', 'bz2', 'zst', 'lz4', 'br', 'lz', 'rar', 'tgz']
                if any(item['name'].lower().endswith('.' + e) for e in supported_exts):
                    # 如果文件超过大小阈值，尝试使用流式读取（Pipe）获取列表，而不解压到磁盘
                    if item.get('size', 0) > threshold_bytes:
                        try:
                            # 仅对 tar 等适合流式处理的格式尝试 pipe
                            # 这里的 item 是归档内的一个文件，例如 file.tar
                            # 我们要读取 archive_path 中的 current_check 文件
                            
                            # 构建 pipe 命令： 7zz x archive_path current_check -so | 7zz l -si -ttar -slt
                            # 注意：对于非 tar 格式，可能不需要 -ttar 或者需要其他类型，这里主要针对 tar
                            
                            is_tar = item['name'].lower().endswith('.tar')
                            if is_tar:
                                cmd1 = [SEVEN_ZIP_BIN, 'x', archive_path, current_check, '-so']
                                cmd2 = [SEVEN_ZIP_BIN, 'l', '-si', '-ttar', '-slt']
                                
                                p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                                p2 = subprocess.Popen(cmd2, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                                p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
                                stdout, stderr = p2.communicate()
                                
                                if p2.returncode == 0:
                                    nested_items = []
                                    current_block = {}
                                    lines = stdout.split('\n')
                                    for line in lines:
                                        line = line.strip()
                                        if not line:
                                            if current_block and 'Path' in current_block:
                                                # 对于 pipe 输入，Path 通常是内部路径
                                                # 我们不需要过滤 archive_path，因为是从流读取
                                                parse_block(current_block, nested_items)
                                            current_block = {}
                                            continue
                                        
                                        if ' = ' in line:
                                            key, value = line.split(' = ', 1)
                                            current_block[key] = value
                                    
                                    if current_block and 'Path' in current_block:
                                        parse_block(current_block, nested_items)
                                    
                                    # 成功获取列表，处理子路径过滤
                                    # 此时 internal_path 是到 item 的路径（如 file.tar）
                                    # 但我们需要浏览的是 file.tar 内部
                                    # 如果当前请求就是 file.tar，则显示 file.tar 根目录
                                    # 如果当前请求是 file.tar/sub，则显示 sub
                                    
                                    # 计算相对于 item 的剩余路径
                                    # parts 是 internal_path split 出来的
                                    # i 是当前 item 在 parts 中的索引
                                    
                                    if i < len(parts) - 1:
                                        remaining_path = "/".join(parts[i+1:])
                                    else:
                                        remaining_path = ""
                                        
                                    # 过滤子项
                                    # nested_items 的 path 是相对于 tar 根的
                                    # remaining_path 也是相对于 tar 根的
                                    
                                    # 对于流式读取，nested_items 包含了所有文件。
                                    # filter_children 需要处理层级。
                                    
                                    # 注意：filter_children 使用 filter_children(all_items, parent_path, base_virtual_path)
                                    # 这里的 all_items 是 nested_items
                                    # parent_path 是 remaining_path
                                    # base_virtual_path 是 full_virtual_path
                                    
                                    # 但是，filter_children 期望 all_items 中的 path 是完整的相对路径
                                    # 我们的 nested_items 的 path 确实是 tar 内的路径
                                    # 所以可以直接调用
                                    
                                    filtered_items = filter_children(nested_items, remaining_path, full_virtual_path)
                                    
                                    # 修正 item 的 extract_path
                                    # 对于流式读取的列表，我们无法直接解压，因为没有临时文件
                                    # 前端如果请求解压，需要后端支持从大文件中提取特定文件（复杂）
                                    # 或者提示不支持。
                                    # 目前暂不处理解压路径修正，让其保持原样或由前端处理
                                    
                                    # 过滤掉名称为空的无效项
                                    filtered_items = [x for x in filtered_items if x['name'] and x['name'].strip()]
                                    
                                    # 对于流式列表，我们需要标记这些 item 属于"虚拟"归档，
                                    # 这样前端如果尝试解压，可能需要特殊处理
                                    # 但最重要的是，我们需要返回列表。
                                    
                                    return jsonify({
                                        'current_path': full_virtual_path, 
                                        'items': filtered_items,
                                        'is_archive': True,
                                        'archive_path': archive_path,
                                        'origin_path': origin_path,
                                        'internal_path': internal_path
                                    })
                                    
                                else:
                                    # pipe failed, maybe not a tar or password protected?
                                    print(f"Pipe failed with code {p2.returncode}: {stderr}")
                                    pass

                        except Exception as e:
                            print(f"Pipe listing failed: {e}")
                            # Fallback to break (show empty or parent)
                            pass
                            
                        break
                        
                    # 发现嵌套归档，准备解压到临时目录
                    temp_dir = os.environ.get('TRIM_PKGTMP', '/tmp')
                    cache_dir = os.path.join(temp_dir, 'archive_cache')
                    os.makedirs(cache_dir, exist_ok=True)
                    
                    # 生成唯一的哈希名，避免冲突
                    import hashlib
                    unique_str = f"{archive_path}:{current_check}"
                    unique_hash = hashlib.md5(unique_str.encode()).hexdigest()
                    ext = os.path.splitext(item['name'])[1]
                    temp_archive_path = os.path.join(cache_dir, f"{unique_hash}{ext}")
                    
                    # 如果临时文件不存在或大小不一致，则执行解压
                    if not os.path.exists(temp_archive_path) or os.path.getsize(temp_archive_path) != item['size']:
                        extract_tmp = os.path.join(cache_dir, f"tmp_{unique_hash}")
                        if os.path.exists(extract_tmp):
                            shutil.rmtree(extract_tmp)
                        
                        # 使用 7zz 解压特定文件
                        cmd = [SEVEN_ZIP_BIN, 'x', archive_path, f'-o{extract_tmp}', current_check, '-y']
                        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        out, err = proc.communicate()
                        
                        if proc.returncode != 0:
                            return jsonify({'error': f"Failed to extract nested archive: {err}"}), 500
                            
                        # 移动解压出的文件到缓存路径
                        extracted_file = os.path.join(extract_tmp, current_check)
                        if os.path.exists(extracted_file):
                            shutil.move(extracted_file, temp_archive_path)
                            shutil.rmtree(extract_tmp)
                        else:
                             return jsonify({'error': f"Extracted file not found: {extracted_file}"}), 500
                    
                    # 递归调用：继续列出这个临时解压的归档内容
                    if i < len(parts):
                         remaining_path = "/".join(parts[i+1:])
                    else:
                         remaining_path = ""
                         
                    return list_archive_content(temp_archive_path, remaining_path, full_virtual_path, origin_path=origin_path)

        # 如果没有嵌套归档或已到达目标层级
        # 筛选当前内部路径下的子项
        items = filter_children(all_items, internal_path, full_virtual_path)
        
        # 过滤掉名称为空的无效项
        items = [x for x in items if x['name'] and x['name'].strip()]
        
        return jsonify({
            'current_path': full_virtual_path, 
            'items': items,
            'is_archive': True,
            'archive_path': archive_path,
            'origin_path': origin_path,
            'internal_path': internal_path
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def list_zip_stream(stream):
    """
    从流中解析 Zip 文件列表（仅支持 Local File Header 中包含大小信息的标准 Zip）。
    不支持 Data Descriptor (bit 3 set) 的流式解析。
    """
    items = []
    while True:
        # Read Local File Header (30 bytes)
        # 注意：stream.read() 可能会阻塞或返回较少字节，但在 pipe 中通常没事
        # 为了稳健，应确保读够
        header = stream.read(30)
        if len(header) < 30:
            break
            
        # Check signature: PK\x03\x04 (0x04034b50 little endian)
        sig = struct.unpack('<I', header[0:4])[0]
        if sig != 0x04034b50:
            # Not a local file header. Could be Central Directory (PK\x01\x02) or End of CD.
            break
            
        # Parse fields
        flags = struct.unpack('<H', header[6:8])[0]
        # compression = struct.unpack('<H', header[8:10])[0]
        mod_time = struct.unpack('<H', header[10:12])[0]
        mod_date = struct.unpack('<H', header[12:14])[0]
        # crc32 = struct.unpack('<I', header[14:18])[0]
        comp_size = struct.unpack('<I', header[18:22])[0]
        uncomp_size = struct.unpack('<I', header[22:26])[0]
        name_len = struct.unpack('<H', header[26:28])[0]
        extra_len = struct.unpack('<H', header[28:30])[0]
        
        # Read Name and Extra
        name_bytes = stream.read(name_len)
        extra_bytes = stream.read(extra_len)
        
        try:
            name = name_bytes.decode('utf-8')
        except:
            name = name_bytes.decode('cp437', errors='ignore')
            
        # 判断目录：以 / 结尾
        is_dir = name.endswith('/') or (uncomp_size == 0 and comp_size == 0 and name.endswith('/'))
        
        # Parse DOS time
        mtime = 0
        try:
            sec = (mod_time & 0x1F) * 2
            min = (mod_time >> 5) & 0x3F
            hour = (mod_time >> 11) & 0x1F
            
            day = mod_date & 0x1F
            month = (mod_date >> 5) & 0x0F
            year = ((mod_date >> 9) & 0x7F) + 1980
            
            import datetime
            dt = datetime.datetime(year, month, day, hour, min, sec)
            mtime = dt.timestamp()
        except:
            pass
        
        items.append({
            'path': name,
            'original_path': name, # Compatible with filter_children
            'name': name.strip('/').split('/')[-1],
            'is_dir': is_dir,
            'size': uncomp_size,
            'mtime': mtime
        })
        
        # Check for Data Descriptor
        if flags & 0x08:
            # Bit 3 set: sizes are 0 in header. They follow the data.
            # We cannot parse this easily without scanning for signature.
            # Log warning and break? Or try to continue?
            # Continuing is impossible without knowing size.
            print(f"Warning: Data Descriptor present for {name}. Cannot parse stream without scanning.")
            break
            
        # Skip compressed data
        if comp_size > 0:
            remaining = comp_size
            while remaining > 0:
                chunk_size = min(remaining, 1024*1024) # 1MB chunks
                data = stream.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                
    return items

def get_archive_items(archive_path):
    """
    使用 7zz l -slt 命令获取归档文件的详细列表。
    解析输出并返回包含文件信息的列表。
    """
    cmd = [SEVEN_ZIP_BIN, 'l', '-slt', archive_path]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        return {'error': f'Failed to list archive: {stderr or stdout}'}

    items = []
    current_block = {}
    # 解析 7zz 的输出块
    lines = stdout.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            if current_block and 'Path' in current_block:
                # 过滤掉原压缩文件名
                path = current_block.get('Path', '').replace('\\', '/')
                if path and path != archive_path:
                    parse_block(current_block, items)
            current_block = {}
            continue
        
        if ' = ' in line:
            key, value = line.split(' = ', 1)
            current_block[key] = value

    if current_block and 'Path' in current_block:
            parse_block(current_block, items)
        
    return items

def parse_block(block, items):
    """
    解析 7zz 输出的单个文件块信息，并添加到 items 列表中。
    """
    # 规范化路径分隔符
    path = block.get('Path', '').replace('\\', '/').lstrip('/')
    
    # 综合判断是否为目录：
    # 1. Attributes 包含 'D' (常见于 zip/7z)
    # 2. Folder 字段为 '+' (常见于 tar)
    # 3. Mode 字段以 'd' 开头 (常见于 tar)
    attributes = block.get('Attributes', '')
    folder = block.get('Folder', '')
    mode = block.get('Mode', '')
    
    is_dir = 'D' in attributes or folder == '+' or mode.startswith('d')
    
    size = block.get('Size', '0')
    modified = block.get('Modified', '')
    
    try:
        size = int(size)
    except:
        size = 0
        
    mtime = 0
    try:
        import datetime
        # 尝试解析时间格式
        try:
             dt = datetime.datetime.strptime(modified.split('.')[0], '%Y-%m-%d %H:%M:%S')
        except:
             dt = datetime.datetime.strptime(modified, '%Y-%m-%d %H:%M')
        mtime = dt.timestamp()
    except:
        pass
    
    name = os.path.basename(path)
    # 忽略无效名称（. 或 ..）
    if not name or name in ('.', '..'):
        return
        
    items.append({
        'path': path,
        'original_path': path,
        'name': name,
        'is_dir': is_dir,
        'size': size,
        'mtime': mtime
    })

def filter_children(all_items, parent_path, base_virtual_path):
    """
    根据父路径筛选归档中的子项。
    处理目录层级，将扁平的归档列表转换为层级结构。
    """
    children = {}
    
    # 记录所有显式存在的路径
    existing_paths = set(item['path'] for item in all_items)
    
    for item in all_items:
        path = item['path']
        
        # 检查是否为 parent_path 的后代
        if parent_path:
            if not path.startswith(parent_path + '/'):
                continue
            relative = path[len(parent_path)+1:]
        else:
            relative = path
            
        if not relative: continue
        
        # 获取直接子组件名称
        parts = relative.split('/')
        child_name = parts[0]
        if not child_name or child_name in ('.', '..'):
            continue
        
        is_direct = (len(parts) == 1)
        
        # Calculate extract_path (original internal path)
        original_path = item.get('original_path', item['path'])
        extract_path = original_path
        
        if not is_direct:
             # Implied directory: derive prefix from original_path
             # relative starts with child_name/
             # We want extract_path to be the prefix corresponding to child_name
             suffix_len = len(relative) - len(child_name)
             if suffix_len > 0 and len(original_path) > suffix_len:
                 extract_path = original_path[:-suffix_len].rstrip('/')
        
        if child_name not in children:
            if is_direct:
                # 这是一个直接的子文件或目录
                children[child_name] = {
                    'name': child_name,
                    'is_dir': item['is_dir'],
                    'path': os.path.join(base_virtual_path, child_name),
                    'extract_path': extract_path,
                    'size': item['size'],
                    'mtime': item['mtime']
                }
            else:
                # 这是一个隐含的中间目录（归档中没有显式记录该目录条目）
                children[child_name] = {
                    'name': child_name,
                    'is_dir': True,
                    'path': os.path.join(base_virtual_path, child_name),
                    'extract_path': extract_path,
                    'size': 0,
                    'mtime': 0 # 隐含目录没有修改时间
                }
        else:
            # 如果之前创建了隐含目录，现在找到了真实的条目，则更新信息
            if is_direct:
                children[child_name].update({
                    'is_dir': item['is_dir'],
                    'size': item['size'],
                    'mtime': item['mtime'],
                    'extract_path': extract_path
                })
                
    # 转换为列表并排序
    result = list(children.values())
    result.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    return result
 
def strip_common_prefix_from_archive(all_items, archive_path):
    """
    剥离归档内容的公共路径前缀。
    例如：如果所有文件都在 'vol1/folder/' 下，则剥离该前缀，直接显示 folder 内容。
    """
    try:
        paths = [i['path'] for i in all_items if i.get('path')]
        if not paths:
            return all_items
            
        # 计算所有路径的公共前缀组件
        parts_list = [p.split('/') for p in paths]
        prefix = parts_list[0][:]
        for parts in parts_list[1:]:
            j = 0
            max_j = min(len(prefix), len(parts))
            while j < max_j and prefix[j] == parts[j]:
                j += 1
            prefix = prefix[:j]
            if not prefix:
                break
        
        if not prefix:
            return all_items
            
        # 剥离前缀并重建条目
        stripped = []
        for item in all_items:
            p = item.get('path', '')
            parts = p.split('/')
            new_parts = parts[len(prefix):]
            new_path = '/'.join(new_parts)
            if not new_path:
                continue
            new_item = dict(item)
            new_item['path'] = new_path
            new_item['name'] = os.path.basename(new_path)
            stripped.append(new_item)
        return stripped or all_items
    except:
        return all_items
 
def cleanup_archive_cache():
    """
    清理归档解压的临时缓存目录。
    """
    try:
        temp_dir = os.environ.get('TRIM_PKGTMP', '/tmp')
        cache_dir = os.path.join(temp_dir, 'archive_cache')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
    except:
        pass

@app.route('/api/delete', methods=['POST'])
def delete_files():
    """
    API: 删除文件或目录
    """
    data = request.json
    files = data.get('files', [])
    
    if not files:
        return jsonify({'error': 'No files specified'}), 400

    deleted = []
    errors = []
    
    for file_path in files:
        try:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
            deleted.append(file_path)
        except Exception as e:
            errors.append(f"{file_path}: {str(e)}")
            
    if errors:
        return jsonify({'success': False, 'deleted': deleted, 'errors': errors}), 207 # Multi-Status
    else:
        return jsonify({'success': True, 'deleted': deleted})

@app.route('/api/mkdir', methods=['POST'])
def create_directory():
    """
    API: 创建新目录
    """
    data = request.json
    path = data.get('path')
    name = data.get('name')
    
    if not path or not name:
        return jsonify({'error': 'Missing path or name'}), 400
        
    full_path = os.path.join(path, name)
    
    try:
        if os.path.exists(full_path):
            return jsonify({'error': 'Directory already exists'}), 400
            
        os.makedirs(full_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/find', methods=['POST'])
def find_files():
    """
    API: 搜索文件
    支持基本通配符模式、正则表达式模式，以及自定义 Shell 命令模式。
    """
    data = request.json
    base_path = data.get('path', '/')
    pattern = data.get('pattern', '*')
    recursive = data.get('recursive', False)
    use_regex = data.get('use_regex', False)
    custom_command = data.get('custom_command', '')
    
    if not os.path.exists(base_path):
        return jsonify({'error': 'Path does not exist'}), 404

    found_files = []
    try:
        if custom_command:
            # 执行自定义查找命令
            # 安全警告：在公共环境中使用 shell=True 存在风险，此处假设为受限环境
            cmd = f"cd '{base_path}' && {custom_command}"
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                 return jsonify({'error': stderr or stdout}), 400
                 
            lines = stdout.strip().split('\n')
            for line in lines:
                if line:
                    full_path = line if os.path.isabs(line) else os.path.join(base_path, line)
                    if os.path.exists(full_path):
                        found_files.append(full_path)
                        
        else:
            # 使用 Python 内置的遍历和匹配
            regex = None
            if use_regex:
                try:
                    regex = re.compile(pattern)
                except re.error as e:
                    return jsonify({'error': f'Invalid regex: {str(e)}'}), 400

            if recursive:
                for root, dirs, files in os.walk(base_path):
                    for name in files:
                        if use_regex:
                            if regex.search(name):
                                found_files.append(os.path.join(root, name))
                        else:
                            if fnmatch.fnmatch(name, pattern):
                                found_files.append(os.path.join(root, name))
            else:
                with os.scandir(base_path) as it:
                    for entry in it:
                        if entry.is_file():
                            if use_regex:
                                if regex.search(entry.name):
                                    found_files.append(entry.path)
                            else:
                                if fnmatch.fnmatch(entry.name, pattern):
                                    found_files.append(entry.path)
                        
        return jsonify({'files': found_files, 'count': len(found_files)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/compress', methods=['POST'])
def compress():
    """
    API: 压缩文件
    支持多种格式（7z, zip 等）、压缩算法（zstd, lzma2 等）和压缩级别。
    """
    data = request.json
    source_files = data.get('files', [])
    destination = data.get('destination')
    archive_name = data.get('archive_name')
    format = data.get('format', '7z')
    level = data.get('level', 5)
    method = data.get('method', 'zstd')
    mode = data.get('mode', 'pack') #获取压缩模式

    if not source_files or not destination:
        return jsonify({'error': 'Missing required parameters'}), 400

    if not os.path.exists(destination):
        try:
            os.makedirs(destination, exist_ok=True)
        except Exception as e:
             return jsonify({'error': f'Failed to create destination: {str(e)}'}), 500
    #打包模式，所有文件打包为一个文件
    if mode == 'pack':
        if not archive_name:
             return jsonify({'error': 'Archive name is required for pack mode'}), 400

        output_path = os.path.join(destination, archive_name)
        if not output_path.endswith(f'.{format}'):
            output_path += f'.{format}'

        cmd = [SEVEN_ZIP_BIN, 'a', output_path]
        
        # 添加压缩参数
        if format == '7z':
            if method == 'zstd':
                cmd.append(f'-m0=zstd')
                cmd.append(f'-mx={level}')
            else:
                cmd.append(f'-m0={method}')
                cmd.append(f'-mx={level}')
        elif format == 'zst':
            cmd.append(f'-mx={level}')
        
        # 使用列表文件处理大量源文件，避免命令行过长
        list_file_path = os.path.join(destination, f'.filelist_{os.getpid()}.txt')
        try:
            with open(list_file_path, 'w', encoding='utf-8') as f:
                for file_path in source_files:
                    f.write(f'{file_path}\n')
            
            cmd.append(f'@{list_file_path}')
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                return jsonify({'success': True, 'output': stdout})
            else:
                return jsonify({'success': False, 'error': stderr or stdout})
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except:
                    pass
    #遍历模式，为每一个文件进行压缩，格式支持7z、zstd
    elif mode == 'each':
        results = []
        errors = []
        
        for file_path in source_files:
            try:
                basename = os.path.basename(file_path)
                # User requirement: original file name + compressed suffix
                output_filename = f"{basename}.{format}"
                output_path = os.path.join(destination, output_filename)
                
                cmd = [SEVEN_ZIP_BIN, 'a', output_path]
                
                # Add params
                if format == '7z':
                    # Default to zstd for 7z in this mode if not specified, but we use 'method' param
                    if method == 'zstd':
                        cmd.append(f'-m0=zstd')
                        cmd.append(f'-mx={level}')
                    else:
                        cmd.append(f'-m0={method}')
                        cmd.append(f'-mx={level}')
                elif format == 'zst':
                    cmd.append(f'-mx={level}')
                
                cmd.append(file_path)
                
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    results.append(f"Compressed {basename} -> {output_filename}")
                else:
                    errors.append(f"Failed {basename}: {stderr or stdout}")
            except Exception as e:
                errors.append(f"Error {basename}: {str(e)}")
        
        if errors:
            return jsonify({'success': False, 'error': '\n'.join(errors), 'output': '\n'.join(results)})
        else:
            return jsonify({'success': True, 'output': '\n'.join(results)})
            
    else:
        return jsonify({'error': 'Invalid mode'}), 400

@app.route('/api/decompress', methods=['POST'])
def decompress():
    """
    API: 解压文件
    支持解压整个归档或部分指定文件。
    支持嵌套归档的流式解压（pipe）。
    """
    data = request.json
    archive_file = data.get('archive_file')
    destination = data.get('destination')
    files = data.get('files', []) # 指定要解压的内部路径列表
    
    if not archive_file or not destination:
        return jsonify({'error': 'Missing required parameters'}), 400

    # 检查是否需要处理流式解压（嵌套归档）
    # 如果 archive_file 是一个虚拟路径（即在某个真实归档内部），我们需要流式处理
    # 通过 find_archive_path 判断 archive_file 是否包含归档路径
    
    real_archive, internal_path = find_archive_path(archive_file)
    
    # 如果 find_archive_path 返回了 real_archive，且 internal_path 不为空，说明 archive_file 本身就是嵌套在归档里的文件
    # 例如 archive_file = /path/to/outer.tar.gz/inner.tar
    # 此时我们需要从 real_archive (/path/to/outer.tar.gz) 中流式提取 internal_path (inner.tar) 中的 files
    
    if real_archive and internal_path:
        # 这是一个嵌套归档解压请求
        # 我们需要构建管道：
        # 7zz x real_archive internal_path -so | 7zz x -si -ttar -o{destination} files...
        
        # 注意：这里假设嵌套的都是 tar 格式（因为目前只有 tar 做了流式列表优化）
        # 如果将来支持其他格式流式，需要调整 -ttar 参数
        
        cmd1 = [SEVEN_ZIP_BIN, 'x', real_archive, internal_path, '-so']
        cmd2 = [SEVEN_ZIP_BIN, 'x', '-si', '-ttar', f'-o{destination}', '-y']
        
        # 如果指定了特定文件
        if files:
            # 7zip 从 stdin 读取时，文件名参数依然有效
            # 但是不能使用 @listfile，因为 stdin 已经被占用了？
            # 实际上 7zip 支持 -si 同时指定文件名，但是要注意文件名是相对于 inner.tar 的
            
            # 安全起见，为了避免文件名包含空格等问题，使用 @listfile
            # 7zip 的 -si 和 @listfile 是可以混用的
            list_file_path = os.path.join(destination, f'.extract_list_{os.getpid()}.txt')
            try:
                with open(list_file_path, 'w', encoding='utf-8') as f:
                    for file_path in files:
                        f.write(f'{file_path}\n')
                # 注意：这里我们使用 -- 标记 switch 参数结束，然后传递 listfile
                # 但对于 -si 模式，7zip 可能对参数解析有特殊要求
                # 尝试直接把 @listfile 放在命令末尾
                cmd2.append(f'@{list_file_path}')
            except Exception as e:
                return jsonify({'error': f'Failed to create list file: {str(e)}'}), 500
            
        try:
            print(f"Streaming decompression: {cmd1} | {cmd2}")
            p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p2 = subprocess.Popen(cmd2, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p1.stdout.close() 
            stdout, stderr = p2.communicate()
            
            # 清理列表文件
            if files and os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except:
                    pass

            # 构建详细输出
            output_msg = f"Command 1: {' '.join(cmd1)}\nCommand 2: {' '.join(cmd2)}\n\nOutput:\n{stdout}"

            if p2.returncode == 0:
                return jsonify({'success': True, 'output': output_msg})
            else:
                # 检查 p1 是否出错
                if p1.poll() != 0:
                     _, err1 = p1.communicate()
                     return jsonify({'success': False, 'error': f"Command 1 failed: {' '.join(cmd1)}\nError: {err1}\n\nInner Error: {stderr}"})
                return jsonify({'success': False, 'error': f"Command 2 failed: {' '.join(cmd2)}\nError: {stderr or stdout}"})
                
        except Exception as e:
            # 异常清理
            if files and os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except:
                    pass
            return jsonify({'error': str(e)}), 500

    elif archive_file.lower().endswith(('.tar.gz', '.tgz')) and os.path.isfile(archive_file) and files:
        # 特殊情况：直接从 .tar.gz 中解压特定文件
        # 虽然它不是虚拟路径嵌套，但 tar.gz 的物理结构决定了我们需要流式处理才能提取内部 tar 里的文件
        # 否则 7zip 只能看到一个 .tar 文件
        
        real_archive = archive_file
        # 对于 tar.gz，直接 x -so 就会输出 tar 流，不需要指定内部文件名
        cmd1 = [SEVEN_ZIP_BIN, 'x', real_archive, '-so']
        cmd2 = [SEVEN_ZIP_BIN, 'x', '-si', '-ttar', f'-o{destination}', '-y']
        
        # 安全起见，为了避免文件名包含空格等问题，使用 @listfile
        list_file_path = os.path.join(destination, f'.extract_list_{os.getpid()}.txt')
        try:
            with open(list_file_path, 'w', encoding='utf-8') as f:
                for file_path in files:
                    f.write(f'{file_path}\n')
            cmd2.append(f'@{list_file_path}')
        except Exception as e:
            return jsonify({'error': f'Failed to create list file: {str(e)}'}), 500
        
        try:
            print(f"Streaming decompression (direct tar.gz): {cmd1} | {cmd2}")
            p1 = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            p2 = subprocess.Popen(cmd2, stdin=p1.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p1.stdout.close() 
            stdout, stderr = p2.communicate()
            
            # 清理列表文件
            if files and os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except:
                    pass

            # 构建详细输出
            output_msg = f"Command 1: {' '.join(cmd1)}\nCommand 2: {' '.join(cmd2)}\n\nOutput:\n{stdout}"

            if p2.returncode == 0:
                return jsonify({'success': True, 'output': output_msg})
            else:
                # 检查 p1 是否出错
                if p1.poll() != 0:
                     _, err1 = p1.communicate()
                     return jsonify({'success': False, 'error': f"Command 1 failed: {' '.join(cmd1)}\nError: {err1}\n\nInner Error: {stderr}"})
                return jsonify({'success': False, 'error': f"Command 2 failed: {' '.join(cmd2)}\nError: {stderr or stdout}"})
                
        except Exception as e:
             # 异常清理
            if files and os.path.exists(list_file_path):
                try:
                    os.remove(list_file_path)
                except:
                    pass
            return jsonify({'error': str(e)}), 500

    # 常规解压逻辑（本地文件）
    cmd = [SEVEN_ZIP_BIN, 'x', archive_file, f'-o{destination}', '-y']
    
    # 如果指定了特定文件
    if files:
        # 创建包含文件列表的临时文件
        list_file_path = os.path.join(destination, f'.extract_list_{os.getpid()}.txt')
        try:
            with open(list_file_path, 'w', encoding='utf-8') as f:
                for file_path in files:
                    f.write(f'{file_path}\n')
            cmd.append(f'@{list_file_path}')
        except Exception as e:
             return jsonify({'error': f'Failed to create list file: {str(e)}'}), 500
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        
        # 清理列表文件
        if files and os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except:
                pass

        # 构建详细输出
        output_msg = f"Command: {' '.join(cmd)}\n\nOutput:\n{stdout}"

        if process.returncode == 0:
            return jsonify({'success': True, 'output': output_msg})
        else:
            return jsonify({'success': False, 'error': f"Command failed: {' '.join(cmd)}\nError: {stderr or stdout}"})
    except Exception as e:
        # 异常清理
        if files and os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/reload-config', methods=['POST'])
def reload_config():
    """
    API: 重新加载配置
    接收新的根路径列表，更新配置文件。
    检测目录变化（新增/移除），返回变化信息。
    """
    data = request.json
    paths_str = data.get('paths', '')
    
    roots = [{'name': 'Root', 'path': '/'},{'name': 'Home', 'path': '/home'}]
    
    if paths_str:
        for path in paths_str.split(':'):
            path = path.strip()
            if path:
                roots.append({'name': os.path.basename(path), 'path': path})
    
    _, current_settings, config_path = load_config()
    
    previous_roots = current_settings.get('previous_roots', [])
    current_paths_set = set(r['path'] for r in roots if r['path'] not in ['/', '/home'])
    previous_paths_set = set(r.get('path', '') for r in previous_roots if r.get('path', '') not in ['/', '/home'])
    
    added_paths = current_paths_set - previous_paths_set
    removed_paths = previous_paths_set - current_paths_set
    
    added_roots = [r for r in roots if r['path'] in added_paths]
    removed_roots = [r for r in previous_roots if r.get('path', '') in removed_paths]
    
    current_settings['previous_roots'] = roots
    
    try:
        with open(config_path, 'w') as f:
            json.dump({'roots': roots, 'settings': current_settings}, f, indent=4)
        return jsonify({
            'success': True, 
            'roots': roots, 
            'settings': current_settings,
            'changes': {
                'added': added_roots,
                'removed': removed_roots,
                'added_count': len(added_roots),
                'removed_count': len(removed_roots)
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
