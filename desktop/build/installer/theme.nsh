; ============================================================================
; Score Trans Installer - Theme Tokens
; 与 desktop/src/renderer/src/App.vue 的 CSS 变量保持一致
; ============================================================================

; ---------------------------------------------------------------------------
; 颜色(RRGGBB 十六进制,不带 #)
; ---------------------------------------------------------------------------
!define COLOR_SIDEBAR_BG       "1a1d23"
!define COLOR_SIDEBAR_BG_DARK  "0e1014"  ; 卸载器专用
!define COLOR_ACCENT           "4c6ef5"
!define COLOR_ACCENT_HOVER     "5c7cfa"
!define COLOR_ACCENT_PRESSED   "3b5bdb"
!define COLOR_BG_BASE          "ffffff"
!define COLOR_BG_SURFACE       "f8f9fa"
!define COLOR_BG_ELEVATED      "ffffff"
!define COLOR_BORDER           "e9ecef"
!define COLOR_BORDER_LIGHT     "f1f3f5"
!define COLOR_TEXT_PRIMARY     "212529"
!define COLOR_TEXT_SECONDARY   "495057"
!define COLOR_TEXT_TERTIARY    "868e96"
!define COLOR_TEXT_SIDEBAR     "adb5bd"
!define COLOR_TEXT_SIDEBAR_ACTIVE "ffffff"
!define COLOR_TEXT_ON_ACCENT   "ffffff"
!define COLOR_SUCCESS          "40c057"
!define COLOR_DANGER           "fa5252"
!define COLOR_DANGER_HOVER     "ff6b6b"
!define COLOR_DANGER_PRESSED   "fa3838"
!define COLOR_WARNING          "fab005"
!define COLOR_TITLEBAR_HOVER   "2c313c"

; BGR COLORREF(0x00BBGGRR)版本 - 供 SetCtlColors / GDI 直接使用
!define BGR_TEXT_PRIMARY_DEF    0x00292521   ; = COLOR_TEXT_PRIMARY
!define BGR_TEXT_SECONDARY_DEF  0x00575049   ; = COLOR_TEXT_SECONDARY
!define BGR_TEXT_SIDEBAR_DEF    0x00bdb5ad   ; = COLOR_TEXT_SIDEBAR
!define BGR_SUCCESS_DEF         0x0057c040   ; = COLOR_SUCCESS
!define BGR_ACCENT_DEF          0x00f56e4c   ; = COLOR_ACCENT
!define BGR_TEXT_ON_ACCENT_DEF  0x00ffffff   ; = COLOR_TEXT_ON_ACCENT
!define BGR_WHITE               0x00ffffff

; ---------------------------------------------------------------------------
; 窗口与布局尺寸(单位:像素,100% DPI)
; ---------------------------------------------------------------------------
!define WINDOW_WIDTH           800
!define WINDOW_HEIGHT          560
!define TITLEBAR_HEIGHT        38
!define SIDEBAR_WIDTH          240
!define CONTENT_WIDTH          560
!define RADIUS_SM              6
!define RADIUS_MD              8
!define RADIUS_LG              10
!define RADIUS_WINDOW          8

; ---------------------------------------------------------------------------
; 字体
; ---------------------------------------------------------------------------
!define FONT_FAMILY            "Microsoft YaHei UI"
!define FONT_SIZE_XS           10
!define FONT_SIZE_SM           12
!define FONT_SIZE_MD           13
!define FONT_SIZE_LG           16
!define FONT_SIZE_XL           20
!define FONT_SIZE_XXL          24
!define FONT_SIZE_DISPLAY      28

; ---------------------------------------------------------------------------
; 步骤指示器(安装器 4 步 / 卸载器 3 步)
; ---------------------------------------------------------------------------
!define STEP_WELCOME           0
!define STEP_DIRECTORY         1
!define STEP_INSTALLING        2
!define STEP_FINISH            3
!define UNSTEP_WELCOME         0
!define UNSTEP_UNINSTALLING    1
!define UNSTEP_FINISH          2

; ---------------------------------------------------------------------------
; 资源 ID 起点(避开 nsDialogs 内部保留 ID)
; ---------------------------------------------------------------------------
!define IDC_TITLEBAR_MIN       5000
!define IDC_TITLEBAR_CLOSE     5001
!define IDC_SIDEBAR            5010
!define IDC_SIDEBAR_LOGO       5011
!define IDC_SIDEBAR_TITLE      5012
!define IDC_SIDEBAR_STEP_BASE  5020
!define IDC_PAGE_TITLE         5100
!define IDC_PAGE_SUBTITLE      5101
!define IDC_PAGE_HERO          5102
!define IDC_BTN_BACK           5200
!define IDC_BTN_NEXT           5201
!define IDC_BTN_CANCEL         5202
!define IDC_BTN_BROWSE         5203
!define IDC_EDIT_DIR           5204
!define IDC_RADIO_PER_USER     5205
!define IDC_RADIO_PER_MACHINE  5206
!define IDC_PROGRESS           5207
!define IDC_PROGRESS_PERCENT   5208
!define IDC_PROGRESS_LABEL     5209
!define IDC_CHECK_RUN_APP      5210
!define IDC_CHECK_DELETE_DATA  5211
!define IDC_DISK_SPACE_LABEL   5212

; ---------------------------------------------------------------------------
; 真实 Logo 图标路径(由 .onInit / un.onInit 释放到 $PLUGINSDIR)
; ---------------------------------------------------------------------------
!define ST_LOGO_PATH           "$PLUGINSDIR\logo.ico"

; ---------------------------------------------------------------------------
; 默认安装路径(与 electron-builder 一致)
; ---------------------------------------------------------------------------
!define DEFAULT_DIR_PER_USER   "$LOCALAPPDATA\Programs\${APP_FILENAME}"
!define DEFAULT_DIR_PER_MACHINE "$PROGRAMFILES64\${APP_FILENAME}"
