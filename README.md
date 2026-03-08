# 7-Zip-zstd for fnOS

基于 7-Zip-zstd 的 Web 文件管理套件，支持 Zstd、LZ4、Brotli 等现代压缩算法，专为 fnOS 飞牛云盘系统设计。

本项目提供两种部署方式，满足不同用户的需求。

---

## 部署方式

### 方式一：Docker 容器部署（推荐）

适用于希望在 fnOS 上使用 Docker 运行应用的用户。

**项目位置**: [fnos-7zip-zstd](./fnos-7zip-zstd/)

**特点**:
- 快速部署，易于管理
- 隔离运行环境，不影响主机系统
- 支持横向扩展
- 更新升级方便

**快速开始**:

```bash
cd fnos-7zip-zstd
docker compose up -d
```

访问地址: `http://<your-server-ip>:5000`

详细文档请参阅: [fnos-7zip-zstd/README.md](./fnos-7zip-zstd/README.md)

---

### 方式二：fnOS 原生安装包

适用于希望在 fnOS 套件中心直接安装的用户。

**项目位置**: [fnos-7zip-native](./fnos-7zip-native/)

**特点**:
- 集成到 fnOS 套件中心
- 系统级管理，开机自启
- 无需额外安装 Docker
- 与 fnOS 系统深度集成

**安装步骤**:

1. 下载 `.fpk` 安装包
2. 打开 fnOS 应用中心
3. 点击"手动安装"
4. 选择安装包文件
5. 按照提示完成安装

详细文档请参阅: [fnos-7zip-native/README.md](./fnos-7zip-native/README.md)

---

## 功能特性对比

| 功能 | Docker 部署 | 原生安装包 |
|------|-------------|-----------|
| Web 文件浏览器 | ✅ | ✅ |
| 多格式压缩支持 | ✅ | ✅ |
| Zstd/LZ4/Brotli 支持 | ✅ | ✅ |
| 嵌套归档浏览 | ✅ | ✅ |
| 文件搜索 | ✅ | ✅ |
| 中英文界面 | ✅ | ✅ |
| 主题切换 | ✅ | ✅ |
| 目录变化检测 | ✅ | ✅ |
| 部署方式 | Docker 容器 | fnOS 套件 |
| 更新方式 | docker pull | 套件中心更新 |

## 核心功能

### 📁 Web 文件浏览器
直观的可视化界面，支持文件/目录浏览、切换根目录。

### 📦 多格式压缩支持
支持 7z, zip, tar, gz, xz, zst, lz4, brotli 等常见压缩格式。

### 🗜️ 现代压缩算法
支持 Zstd、LZMA2、LZ4、Brotli、Lizard、LZ5 等先进压缩算法，提供更高的压缩率。

### 📂 嵌套归档浏览
自动处理 tar.gz、tar.zst 等嵌套压缩格式，无需手动解压即可浏览。

### 🔍 高级搜索
支持正则表达式和递归搜索，可对搜索结果进行批量压缩操作。

### 🔄 目录变化检测
当用户在 fnOS 中修改共享目录设置时，自动同步更新到应用程序。

## 项目结构

```
7zip-zs/
├── fnos-7zip-zstd/      # Docker 部署版本
│   ├── app.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── bin/7zz         # 7-Zip Zstd 二进制
│   ├── templates/
│   ├── static/
│   └── README.md
│
├── fnos-7zip-native/    # fnOS 原生安装包
│   ├── app/            # 应用程序
│   ├── cmd/            # 生命周期脚本
│   ├── config/         # 配置目录
│   ├── manifest        # 安装包清单
│   └── README.md
│
└── README.md           # 本文件
```

## 技术栈

- **后端**: Python 3.10+ / Flask
- **前端**: HTML5 + Bootstrap 5 + Font Awesome
- **压缩工具**: 7-Zip Zstd (7zz)
- **容器化**: Docker + Docker Compose

## 许可证

- 7-Zip-zstd: LGPL
- 7-Zip: LGPL
- Zstandard: BSD/GPL

## 相关资源

- [7-Zip-zstd 官方仓库](https://github.com/igor Pavlov/7-zip-zstd)
- [Zstandard 官网](https://facebook.github.io/zstd/)
- [fnOS 飞牛云盘](https://www.fnnas.com/)