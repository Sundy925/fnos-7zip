# fnos-7zip-native

基于 7-Zip-zstd 的 Web 文件管理套件，专为 fnOS 飞牛云盘系统设计的原生安装包版本。

## 插件信息

| 属性 | 值 |
|------|------|
| 插件名称 | 7zip-ZS |
| 版本 | 0.0.1 |
| 架构 | x86_64 |
| 依赖 | python312 |

## 功能特性

- 📁 **Web 文件浏览器** - 直观的可视化界面，支持文件/目录浏览
- 📦 **多格式压缩支持** - 7z, zip, tar, gz, xz, zst, lz4, brotli 等
- 🗜️ **现代压缩算法** - Zstd, LZMA2, LZ4, Brotli, Lizard, LZ5
- 🔍 **文件搜索** - 支持正则表达式和递归搜索
- 📂 **嵌套归档浏览** - tar.gz, tar.zst 等嵌套格式自动解压浏览
- 🌐 **中英文界面** - 国际化支持
- 🖥️ **浅色/深色主题** - 主题切换功能
- 🔄 **目录变化检测** - 共享目录新增/移除自动同步

## 安装说明

### 系统要求

- fnOS 飞牛云盘系统
- Python 3.12 或更高版本
- x86_64 架构

### 安装步骤

1. 打开 fnOS 应用中心
2. 点击"手动安装"
3. 选择本地的 `.fpk` 安装包文件
4. 按照提示完成安装

### 安装包结构

```
fnos-7zip-native/
├── app/               # 应用程序目录
│   ├── app.py        # Flask 主应用
│   ├── bin/          # 7-Zip 二进制文件
│   ├── libs/         # Python 依赖库
│   └── ui/           # 前端界面资源
├── cmd/              # 生命周期脚本
│   ├── install_init  # 安装前脚本
│   ├── install_callback # 安装后脚本
│   ├── uninstall_init   # 卸载前脚本
│   ├── uninstall_callback # 卸载后脚本
│   ├── upgrade_init     # 升级前脚本
│   ├── upgrade_callback  # 升级后脚本
│   ├── config_init      # 配置修改前脚本
│   └── config_callback  # 配置修改后脚本
├── config/           # 配置文件目录
├── wizard/           # 安装向导资源
├── manifest          # 插件清单文件
├── ICON.PNG         # 插件图标
└── ICON_256.PNG    # 高清插件图标
```

## 配置说明

### 环境变量

| 变量 | 说明 |
|------|------|
| `TRIM_PKGTMP` | 临时文件目录 |
| `TRIM_PKGVAR` | 数据存储目录 |
| `TRIM_DATA_ACCESSIBLE_PATHS` | 用户可访问的共享目录 |

### 生命周期脚本

#### 安装脚本

- `install_init`: 安装前检查
- `install_callback`: 安装后初始化

#### 卸载脚本

- `uninstall_init`: 卸载前清理
- `uninstall_callback`: 卸载后清理

#### 升级脚本

- `upgrade_init`: 升级前备份
- `upgrade_callback`: 升级后恢复

#### 配置脚本

- `config_init`: 用户修改共享目录前执行，记录当前配置
- `config_callback`: 用户修改共享目录后执行，同步配置到应用

## 目录变化检测

本插件支持共享目录变化检测功能，当用户在 fnOS 中修改共享目录设置时，能够自动同步到应用程序。

### 工作流程

```
用户修改共享目录设置
        ↓
系统触发 config_init 脚本（修改前）
        ↓
系统更新环境变量 TRIM_DATA_ACCESSIBLE_PATHS
        ↓
系统触发 config_callback 脚本（修改后）
        ↓
脚本调用 reload-config API
        ↓
应用程序更新配置并同步界面
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

- **后端**：Python 3.12 + Flask
- **前端**：HTML5 + Bootstrap 5 + Font Awesome
- **压缩工具**：7-Zip Zstd (7zz)

## 许可证

- 7-Zip-zstd: LGPL
- 7-Zip: LGPL
- Zstandard: BSD/GPL