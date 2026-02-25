[app]
title = 运输明细
package.name = transport_detail
package.domain = org.example
source.dir = .
source.include_exts = py,kv,json,ttf,otf,ttc,txt
version = 0.1.0

requirements = python3,kivy==2.3.1

orientation = portrait
fullscreen = 0

# 建议首次打包先用 debug
# buildozer -v android debug

[buildozer]
log_level = 2

[android]
minapi = 23
ndk_api = 23

# 如果你后续要把“导出 CSV 到 Downloads/分享”做成原生 Intent，
# 再按需增加权限与 Java 依赖（当前实现导出到应用私有目录即可满足离线要求）。

