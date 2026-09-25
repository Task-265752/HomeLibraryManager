# 第三方组件

本项目的**自有代码**已捐献至公有领域，见 [LICENSE](LICENSE)。
但它使用并分发了若干第三方库，**这些库保留各自的许可证，不被本项目的公有领域声明覆盖**。

分发包里的 `licenses\` 目录已包含下列全部许可证原文。

| 组件 | 版本 | 许可证 | 在分发包中的位置 | 许可证文件 |
|---|---|---|---|---|
| Qt | 5.15.2 | **LGPL v3** | `PySide2\Qt5*.dll`、`PySide2\plugins\` | `licenses\LICENSE.LGPLv3` |
| PySide2 | 5.15.2.1 | **LGPL v3** | `PySide2\*.pyd`、`pyside2.abi3.dll` | 同上 |
| Shiboken2 | 5.15.2.1 | **LGPL v3** | `shiboken2\shiboken2.abi3.dll` | 同上 |
| Python | 3.8.10 | PSF License | `python38.dll`、`python3.dll` | `licenses\LICENSE.txt` |
| OpenSSL | 1.1.1 | OpenSSL + SSLeay | `libcrypto-1_1.dll`、`libssl-1_1.dll` | 同上 |
| MSVC 运行时 | 14.x | 微软可再发行条款 | `VCRUNTIME140*.dll`、`PySide2\ucrtbase.dll` | 同上 |
| bzip2 / libffi / expat / zlib | — | 各自许可证 | `_bz2.pyd`、`_hashlib.pyd` 等 | 同上 |

> **为什么只有一个 `LICENSE.txt`？** CPython 的 `LICENSE.txt` 是**聚合许可证**：
> 它同时包含 PSF 许可证、微软可再发行代码条款、OpenSSL/SSLeay 许可证，
> 以及 bzip2、libffi、expat、zlib 的许可证。打包脚本会把**构建所用 Python 的
> 这一份文件**原样放进分发包，因此上述所有组件的署名义务一次结清。

---

## 最需要注意的：LGPL v3（Qt / PySide2）

其余组件的许可证基本只要求"保留许可证原文"，而 LGPL v3 额外要求**可替换性**。

**自己用：没有任何义务。**

**分发二进制（把 ZIP 发给别人、传到 GitHub Releases 等），LGPL v3 要求三件事：**

**① 随附许可证文本** —— 分发包 `licenses\` 已包含完整的 LGPL v3 与 GPL v3 文本。

**② 允许接收者替换这些库** —— 本项目**动态链接** Qt，接收者直接替换
`PySide2\Qt5Core.dll` 之类的文件即可，**不需要重新编译本程序**。这满足 LGPL 的"可替换"要求。

**③ 若修改了 Qt 本身，修改部分需按 LGPL 公开** —— 本项目没有修改 Qt 的任何代码。

### 获取 Qt / PySide2 的源代码

LGPL 允许接收者获取库的源代码。本项目分发的是**未经修改**的官方二进制：

- 二进制来源：PyPI 上的 `PySide2==5.15.2.1` 官方 wheel
- PySide2 源码：<https://code.qt.io/cgit/pyside/pyside-setup.git/>
- Qt 5.15 源码：<https://download.qt.io/archive/qt/5.15/5.15.2/single/>

---

## 为什么 Qt 不能被放进公有领域

Qt 的著作权属于 The Qt Company 及其他贡献者。**任何人都无权代替他们重新授权。**
本项目的 Unlicense 声明**只覆盖本项目自己编写的代码**。

如果你需要不受 LGPL 约束地分发，有两条路：

1. 向 Qt 官方购买商业许可证；
2. 换掉 PySide2 依赖（例如改用 tkinter 等许可更宽松的绑定）——但那会放弃 Windows 7 支持，
   因为支持 Win7 的最后一代 Qt 是 5.15。

---

## 许可证原文索引

| 许可证 | 位置 |
|---|---|
| 本项目（Unlicense） | `LICENSE` |
| Qt / PySide2（LGPL v3 等 6 份） | `licenses\LICENSE.*` |
| Python / OpenSSL / MSVC / bzip2 / libffi | `licenses\LICENSE.txt` |
| LGPL v3 官方 | <https://www.gnu.org/licenses/lgpl-3.0.html> |
| Python 许可证官方 | <https://docs.python.org/3/license.html> |
