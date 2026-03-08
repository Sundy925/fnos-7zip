# 7-Zip Zstd for fnOS

基于 7-Zip-zstd 的 Web 文件管理套件，支持 Zstd、LZ4、Brotli 等压缩算法。

## 环境要求

| 软件 | 版本 |
|------|------|
| Docker | 28.1.1 |
| Docker Compose | v2.35.1 |
| fnOS 飞牛云存储 | 0.0.1 |

## 功能特性

- 📁 Web 文件浏览器
- 📦 支持压缩格式：7z, zip, tar, gz, xz, zst, lz4, brotli 等
- 🗜️ 支持压缩算法：Zstd, LZMA2, LZ4, Brotli, Lizard, LZ5
- 🔍 文件搜索（支持正则表达式）
- 📂 嵌套归档浏览（tar.gz, tar.zst 等）
- 🌐 中英文界面支持
- 🖥️ 浅色/深色主题

## 快速开始

### 构建并启动容器

```bash
cd fnos-7zip-zstd
docker compose up -d
```

### 访问服务

服务启动后，通过以下地址访问：

```
http://<your-server-ip>:5000
```

## 配置说明

### 端口映射

默认映射端口为 `5000:5000`，可在 `docker-compose.yml` 中修改：

```yaml
ports:
  - "5000:5000"
```

### 配置目录

配置文件默认保存在 `/config` 目录（容器内），对应宿主机上的 `./config` 目录。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PKG_CONFIG_PATH` | 配置文件路径 | `/config/config.json` |
| `DOCKER_MOUNT_PATHS` | 挂载路径配置 | `/host_fs:/Root` |
| `FLASK_ENV` | Flask 运行模式 | `production` |

### 文件浏览器根目录

默认显示宿主机根目录 `/host_fs`，可在 `docker-compose.yml` 中修改 `DOCKER_MOUNT_PATHS` 环境变量来添加更多挂载点。

## 项目结构

```
fnos-7zip-zstd/
├── app.py              # Flask 主应用
├── Dockerfile          # Docker 镜像构建文件
├── docker-compose.yml  # 容器编排配置
├── requirements.txt    # Python 依赖
├── bin/
│   └── 7zz            # 7-Zip 二进制文件
├── static/
│   └── images/        # 静态资源文件
├── templates/
│   └── index.html    # 前端页面
└── config/           # 配置目录（运行时生成）
```

## 使用说明

### 文件浏览

- 点击左侧导航栏切换根目录
- 点击文件夹进入目录
- 点击文件查看或解压

### 压缩文件

1. 选择要压缩的文件或文件夹
2. 点击"压缩"按钮
3. 选择压缩格式、算法和压缩等级
4. 设置目标路径和文件名
5. 点击"创建压缩包"

### 解压文件

1. 选择压缩文件
2. 点击"解压"按钮
3. 选择目标路径
4. 点击"解压"

### 高级搜索

1. 点击"高级"按钮
2. 设置搜索路径、模式、是否递归
3. 点击"预览"查看搜索结果
4. 可直接对搜索结果进行批量压缩

## 技术栈

- **后端**：Python 3.10 + Flask
- **前端**：HTML5 + Bootstrap 5 + Font Awesome
- **压缩工具**：7-Zip Zstd (7zz)
- **容器化**：Docker + Docker Compose

## 许可证

- 7-Zip-zstd: LGPL
- 7-Zip: LGPL
- Zstandard: BSD/GPL
