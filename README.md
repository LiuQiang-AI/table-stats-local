# 运输明细规制（安卓 App / Python-Kivy）

这是一个**离线**“运输明细”录入 App，固定 11 列表头，自动连续日期、下拉选择、金额自动计算、汇总、导出 CSV。

数据全部保存在本机/手机应用私有目录（不会上传网络）。

## 功能（按规制）

- 固定表头 11 列：装车日期、装车地、车辆、产品型号、装车净重、卸车日期、卸货地、卸车数（吨）、运费、结算吨数、金额
- 装车日期：从开始日期起每行 +1 天，**只读**
- 装车地/卸货地：下拉选择（来自 `config.json`）
- 默认值：车辆默认“蒙J87721”，产品型号默认“PAC”（来自 `config.json`）
- 金额自动计算：填写/修改 运费 与 结算吨数 时，自动计算 \(金额 = 运费 \times 结算吨数\)
- 打开表格：支持“最近打开 / 所有表格”列表
- 删除表格：一键删除，删除后不可恢复（有确认弹窗）
- 新表按钮：保存当前表后，快速创建下一张表（开始日期=上一表最后一行日期+1）
- 汇总：
  - 回填每行金额
  - 统计总金额并弹窗显示
  - 自动把表名从 `开始日期-` 更新为 `开始日期-结束日期`（结束日期取最后一行装车日期）
- 下载：导出当前表格为 CSV（含中文表头，UTF-8 BOM，Excel 可打开）

## 桌面运行（先验证逻辑）

```bash
cd E:\table-stats-local
run.bat
```

也可以手动运行（如果你电脑的 pip 被配置成公司/学校镜像，镜像里没有 Kivy，会安装失败。可临时对本项目指定官方源）：

```bash
python -m venv .venv
.\.venv\Scripts\pip install -i https://pypi.org/simple -r requirements.txt
.\.venv\Scripts\python main.py
```

## 运行测试（冒烟测试）

```bash
.\run_tests.bat
```

或在 PowerShell：

```powershell
.\run_tests.ps1
```

## 配置文件

首次运行会在应用数据目录创建 `config.json`，可修改：

- `loadPlaces`: 装车地下拉列表
- `unloadPlaces`: 卸货地下拉列表
- `defaultVehicle`: 默认车辆
- `defaultModel`: 默认产品型号
- `initialRows`: 新建表默认行数
- `recentLimit`: 最近打开数量

你也可以参考项目里的 `config.template.json`。

## 中文显示（方块/乱码）的处理

如果你在 **Android 或某些 Windows 环境**看到中文变成方块/乱码，这是因为默认字体不含中文字形。

处理方式：

1. 把一个中文字体文件放到 `assets/fonts/`（项目已提供 `assets/fonts/README.txt`）
2. 重启 App

推荐字体（任选其一）：`NotoSansSC-Regular.otf` / `SourceHanSansCN-Regular.otf` 等。

## Android 打包（Buildozer）

Buildozer 通常在 Linux 环境使用。Windows 推荐走 WSL2/Ubuntu：

1. 安装 WSL2 + Ubuntu（管理员 PowerShell 执行：`wsl.exe --install`，装完重启；首次打开 Ubuntu 完成初始化）
   - 如果你已经有 `wsl.exe` 但没有安装任何发行版，执行：`wsl.exe --install -d Ubuntu`
2. 在 Ubuntu 中安装依赖（参考 Buildozer 文档）
3. `pip install buildozer`
4. `buildozer init`
5. 修改 `buildozer.spec`：
   - `requirements = python3,kivy==2.3.1`
   - `package.name = transport_detail`
   - `source.include_exts = py,kv,json`
6. `buildozer -v android debug`

生成的 APK 在 `bin/` 目录。

项目内提供了 `buildozer.spec.example`，可以直接拷贝后再按需微调。

### Windows 一键打包（WSL2）

```powershell
.\build_android_wsl.ps1
```

如需指定发行版（例如 Ubuntu）：

```powershell
.\build_android_wsl.ps1 -Distro Ubuntu
```

### 使用 GitHub Actions 打包（推荐：不装 WSL 也能打包）

项目已内置工作流：`.github/workflows/android-apk.yml`

使用方式：

1. 把代码推到 GitHub 仓库（建议仓库根目录就是本项目）
2. 打开仓库页面 → **Actions**
3. 选择 **Build Android APK (Kivy/Buildozer)** → **Run workflow**
4. 等构建完成后，在该次运行页面的 **Artifacts** 下载 `apk`（里面是 `bin/*.apk`）
