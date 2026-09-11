; ============================================================================
; Score Trans Installer - UI Primitives
; 策略:
;   - 按钮/静态控件: uxtheme.SetWindowTheme(hwnd, "", "") 禁用主题 + SetCtlColors
;   - 窗口: 无边框 WS_POPUP + DWM 圆角
;   - 标题栏: 自绘 STATIC + 2 个 BUTTON
;   - 进度条: nsDialogs 的 ProgressBar 控件(用 SetCtlColors 改色)
;
; NSIS 规则: 卸载 Section/Function 里只能 Call 以 "un." 开头的函数。
; 因此公共函数以宏实现(ST_*Impl),分别展开到安装版(Function ST_*)和
; 卸载版(Function un.ST_*)。
; ============================================================================

!include "nsDialogs.nsh"
!include "WinMessages.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; ---------------------------------------------------------------------------
; Win32 常量(用 !ifndef 防御重复定义)
; ---------------------------------------------------------------------------
!ifndef WS_POPUP
  !define WS_POPUP             0x80000000
!endif
!ifndef WS_VISIBLE
  !define WS_VISIBLE           0x10000000
!endif
!ifndef WS_CHILD
  !define WS_CHILD             0x40000000
!endif
!ifndef WS_CLIPSIBLINGS
  !define WS_CLIPSIBLINGS      0x04000000
!endif
!ifndef GWL_STYLE
  !define GWL_STYLE            -16
!endif
!ifndef GWL_EXSTYLE
  !define GWL_EXSTYLE          -20
!endif
!ifndef SWP_NOMOVE
  !define SWP_NOMOVE           0x0002
!endif
!ifndef SWP_NOSIZE
  !define SWP_NOSIZE           0x0001
!endif
!ifndef SWP_NOZORDER
  !define SWP_NOZORDER         0x0004
!endif
!ifndef SWP_FRAMECHANGED
  !define SWP_FRAMECHANGED     0x0020
!endif
!ifndef HTCAPTION
  !define HTCAPTION            2
!endif
!ifndef HTCLIENT
  !define HTCLIENT             1
!endif
!ifndef WM_NCLBUTTONDOWN
  !define WM_NCLBUTTONDOWN     0x00A1
!endif
!ifndef TRANSPARENT
  !define TRANSPARENT          1
!endif
!define DWMWA_WINDOW_CORNER_PREFERENCE 33
!define DWMWCP_ROUND         2
!define DWMWA_USE_IMMERSIVE_DARK_MODE 20
!ifndef PBS_SMOOTH
  !define PBS_SMOOTH           0x01
!endif

; ---------------------------------------------------------------------------
; 全局变量
; ---------------------------------------------------------------------------
Var ST_HWND
Var ST_OUTER_HWND
Var ST_TITLEBAR
Var ST_TITLEBAR_TITLE
Var ST_BTN_MIN
Var ST_BTN_CLOSE
Var ST_CURRENT_PAGE
Var ST_IS_UNINSTALLER
Var ST_BRUSH_SIDEBAR
Var ST_BRUSH_BG
Var ST_BRUSH_SURFACE
Var ST_FONT_TITLE
Var ST_FONT_SUBTITLE
Var ST_FONT_BODY
Var ST_FONT_SM
Var ST_FONT_XS
Var ST_FONT_BTN
Var ST_FONT_DISPLAY
Var ST_FONT_SIDEBAR_TITLE
Var ST_FONT_STEP
Var ST_SCALE            ; 界面缩放百分比, 取 max(系统DPI缩放, 125)
Var ST_WIN_W            ; 缩放后的窗口宽(布局时读取, 避免取整误差留缝)
Var ST_WIN_H            ; 缩放后的窗口高
Var ST_TITLE_H          ; 缩放后的标题栏高
Var ST_DRAG_HELD        ; 标题栏拖拽移动进行标志
Var ST_ACTION_HELD      ; 托管页原生按钮按下状态
Var ST_ACTION_DOWN      ; 托管页按下时命中的控件
Var ST_MANAGED_PRIMARY  ; 托管页主按钮（完成页使用）
Var ST_S0               ; 坐标缩放暂存(供各创建宏使用)

; instfiles 页原生控件句柄(chrome + 内容, 安装器/卸载器共用变量, 分进程运行互不影响)
Var ST_IP_CONTENT
Var ST_IP_SIDEBAR
Var ST_IP_TITLEBAR
Var ST_IP_LOGO
Var ST_IP_TITLE
Var ST_IP_PAGETITLE
Var ST_IP_PAGEMSG
Var ST_IP_STEP_DOT
Var ST_IP_STEP_LBL
Var ST_IP_STEP_Y
Var ST_IP_SIDEBAR_LOGO
Var ST_IP_SIDEBAR_NAME
Var ST_IP_SIDEBAR_VER
Var ST_IP_PARENT
Var ST_S1
Var ST_S2
Var ST_S3
Var ST_STYLE            ; CreateWindowEx 样式暂存(见 ST_RawStatic 注释, 必须 IntOp 预计算)

; BGR 颜色常量(SetCtlColors 与 GDI 都用 COLORREF = 0x00BBGGRR)
!define BGR_SIDEBAR_BG       0x00231d1a
!define BGR_SIDEBAR_BG_DARK  0x0014100e
!define BGR_ACCENT           0x00f56e4c
!define BGR_ACCENT_HOVER     0x00fa7c5c
!define BGR_ACCENT_PRESSED   0x00db5b3b
!define BGR_BG_BASE          0x00ffffff
!define BGR_BG_SURFACE       0x00faf9f8
!define BGR_BORDER           0x00efece9
!define BGR_TEXT_PRIMARY     0x00292521
!define BGR_TEXT_SECONDARY   0x00575049
!define BGR_TEXT_TERTIARY    0x00968e86
!define BGR_TEXT_SIDEBAR     0x00bdb5ad
!define BGR_TEXT_ON_ACCENT   0x00ffffff
!define BGR_SUCCESS          0x0057c040
!define BGR_DANGER           0x005252fa

; ---------------------------------------------------------------------------
; Hover 注册表(每页最多 6 个可悬浮控件: 4 按钮 + 标题栏 2 按钮)
; 类型: 0=Primary 1=Secondary 2=Danger 3=TitleMin 4=TitleClose
; ---------------------------------------------------------------------------
Var ST_HOV_CNT
Var ST_HOV_CUR
Var ST_HOV_CUR_T
Var ST_HOV_H0
Var ST_HOV_H1
Var ST_HOV_H2
Var ST_HOV_H3
Var ST_HOV_H4
Var ST_HOV_H5
Var ST_HOV_T0
Var ST_HOV_T1
Var ST_HOV_T2
Var ST_HOV_T3
Var ST_HOV_T4
Var ST_HOV_T5

; ---------------------------------------------------------------------------
; 颜色字符串 → 0xRRGGBB(SetCtlColors 用)
; ---------------------------------------------------------------------------
!macro ST_SetColors HANDLE FG_HEX BG_HEX
  SetCtlColors ${HANDLE} "0x${FG_HEX}" "0x${BG_HEX}"
!macroend

!macro ST_MakeClickThrough HANDLE
  ; 背景类标签必须点击穿透: nsDialogs 的 Label 默认带 SS_NOTIFY,
  ; 而控件 Z 序是先创建者在上层, 背景会吞掉落在其范围内的所有鼠标点击
  Push $0
  System::Call 'user32::GetWindowLong(i ${HANDLE}, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 & 0xFFFFFEFF
  System::Call 'user32::SetWindowLong(i ${HANDLE}, i ${GWL_STYLE}, i r0)'
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 界面缩放: 高分辨率 + 100% 缩放的屏幕上 800x560 的窗口和 10~13px 字体
; 几乎无法阅读。统一按 max(系统DPI缩放, 125%) 在运行时放大所有坐标和字体,
; 布局代码里的 px 字面量视为 100% 基准下的设计尺寸。
; ---------------------------------------------------------------------------
!macro ST_EnsureScaleImpl
  ${If} $ST_SCALE == ""
    Push $0
    System::Call 'user32::GetDpiForSystem() i .r0'
    IntOp $0 $0 * 100
    IntOp $0 $0 / 96
    ${If} $0 < 125
      StrCpy $ST_SCALE 125
    ${Else}
      StrCpy $ST_SCALE $0
    ${EndIf}
    Pop $0
  ${EndIf}
!macroend

!macro ST_Scale DST VALUE
  ; VALUE 可带 px 后缀(IntOp 按前导数字解析), 结果写回 DST(通常为 $ST_S0..$ST_S3)
  ; IntOp 单条只支持一个运算符, 先乘后除分两步
  IntOp ${DST} ${VALUE} * $ST_SCALE
  IntOp ${DST} ${DST} / 100
!macroend

!macro ST_CenterActionLabel HANDLE FG_HEX BG_HEX
  Push $0
  !insertmacro ST_SetColors ${HANDLE} "${FG_HEX}" "${BG_HEX}"
  System::Call 'user32::GetWindowLong(i ${HANDLE}, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 | ${SS_CENTER}
  IntOp $0 $0 | ${SS_CENTERIMAGE}
  IntOp $0 $0 | ${SS_NOTIFY}
  System::Call 'user32::SetWindowLong(i ${HANDLE}, i ${GWL_STYLE}, i r0)'
  ShowWindow ${HANDLE} ${SW_SHOW}
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 字体初始化(宏实现,展开到安装/卸载两套函数)
; ---------------------------------------------------------------------------
!macro ST_ScaledFont HEIGHT WEIGHT OUT_VAR
  IntOp $0 ${HEIGHT} * $ST_SCALE
  IntOp $0 $0 / 100
  System::Call 'gdi32::CreateFont(i r0, i 0, i 0, i 0, i ${WEIGHT}, i 0, i 0, i 0, i 0, i 0, i 0, i 0, i 0, t "${FONT_FAMILY}") i .s'
  Pop ${OUT_VAR}
!macroend

!macro ST_InitFontsImpl
  !insertmacro ST_EnsureScaleImpl
  Push $0
  !insertmacro ST_ScaledFont -20 700 $ST_FONT_TITLE
  !insertmacro ST_ScaledFont -13 400 $ST_FONT_SUBTITLE
  !insertmacro ST_ScaledFont -13 400 $ST_FONT_BODY
  !insertmacro ST_ScaledFont -12 400 $ST_FONT_SM
  !insertmacro ST_ScaledFont -10 400 $ST_FONT_XS
  !insertmacro ST_ScaledFont -13 500 $ST_FONT_BTN
  !insertmacro ST_ScaledFont -28 700 $ST_FONT_DISPLAY
  !insertmacro ST_ScaledFont -16 600 $ST_FONT_SIDEBAR_TITLE
  !insertmacro ST_ScaledFont -12 400 $ST_FONT_STEP
  Pop $0
!macroend

!macro ST_FreeFontsImpl
  ${If} $ST_FONT_TITLE != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_TITLE)'
  ${EndIf}
  ${If} $ST_FONT_SUBTITLE != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_SUBTITLE)'
  ${EndIf}
  ${If} $ST_FONT_BODY != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_BODY)'
  ${EndIf}
  ${If} $ST_FONT_SM != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_SM)'
  ${EndIf}
  ${If} $ST_FONT_XS != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_XS)'
  ${EndIf}
  ${If} $ST_FONT_BTN != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_BTN)'
  ${EndIf}
  ${If} $ST_FONT_DISPLAY != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_DISPLAY)'
  ${EndIf}
  ${If} $ST_FONT_SIDEBAR_TITLE != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_SIDEBAR_TITLE)'
  ${EndIf}
  ${If} $ST_FONT_STEP != 0
    System::Call 'gdi32::DeleteObject(i $ST_FONT_STEP)'
  ${EndIf}
!macroend

!macro ST_InitBrushesImpl
  System::Call 'gdi32::CreateSolidBrush(i ${BGR_SIDEBAR_BG}) i .s'
  Pop $ST_BRUSH_SIDEBAR
  System::Call 'gdi32::CreateSolidBrush(i ${BGR_BG_BASE}) i .s'
  Pop $ST_BRUSH_BG
  System::Call 'gdi32::CreateSolidBrush(i ${BGR_BG_SURFACE}) i .s'
  Pop $ST_BRUSH_SURFACE
!macroend

!macro ST_FreeBrushesImpl
  ${If} $ST_BRUSH_SIDEBAR != 0
    System::Call 'gdi32::DeleteObject(i $ST_BRUSH_SIDEBAR)'
  ${EndIf}
  ${If} $ST_BRUSH_BG != 0
    System::Call 'gdi32::DeleteObject(i $ST_BRUSH_BG)'
  ${EndIf}
  ${If} $ST_BRUSH_SURFACE != 0
    System::Call 'gdi32::DeleteObject(i $ST_BRUSH_SURFACE)'
  ${EndIf}
!macroend

; ---------------------------------------------------------------------------
; 主窗口定制(宏实现)
; ---------------------------------------------------------------------------
!macro ST_SetupWindowImpl
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  Push $7
  Push $8
  Push $9

  !insertmacro ST_EnsureScaleImpl

  ; 缩放后的窗口/标题栏尺寸(sidebar 等布局读取, 保证拼接无缝)
  IntOp $7 ${WINDOW_WIDTH} * $ST_SCALE
  IntOp $7 $7 / 100
  IntOp $8 ${WINDOW_HEIGHT} * $ST_SCALE
  IntOp $8 $8 / 100
  IntOp $9 ${TITLEBAR_HEIGHT} * $ST_SCALE
  IntOp $9 $9 / 100
  StrCpy $ST_WIN_W $7
  StrCpy $ST_WIN_H $8
  StrCpy $ST_TITLE_H $9

  System::Call 'user32::GetWindowLong(i $HWNDPARENT, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 & 0x0000FFFF
  IntOp $0 $0 | ${WS_POPUP}
  IntOp $0 $0 | ${WS_VISIBLE}
  IntOp $0 $0 | ${WS_CLIPSIBLINGS}
  System::Call 'user32::SetWindowLong(i $HWNDPARENT, i ${GWL_STYLE}, i r0)'

  System::Call 'dwmapi::DwmSetWindowAttribute(i $HWNDPARENT, i ${DWMWA_WINDOW_CORNER_PREFERENCE}, *i ${DWMWCP_ROUND}, i 4)'
  System::Call 'dwmapi::DwmSetWindowAttribute(i $HWNDPARENT, i ${DWMWA_USE_IMMERSIVE_DARK_MODE}, *i 1, i 4)'

  System::Call 'user32::GetSystemMetrics(i 0) i .r1'
  System::Call 'user32::GetSystemMetrics(i 1) i .r2'
  IntOp $3 $1 - $7
  IntOp $3 $3 / 2
  IntOp $4 $2 - $8
  IntOp $4 $4 / 2
  ; 合并 SWP flags(必须先 IntOp,System::Call 不解析表达式)
  IntOp $5 ${SWP_NOZORDER} | ${SWP_FRAMECHANGED}
  System::Call 'user32::SetWindowPos(i $HWNDPARENT, i 0, i r3, i r4, i r7, i r8, i r5)'

  ; Page resources keep their stock 1018 size unless resized after creation.
  FindWindow $6 "#32770" "" $HWNDPARENT
  ${If} $6 != 0
    System::Call 'user32::SetWindowPos(i r6, i 0, i 0, i 0, i r7, i r8, i ${SWP_NOZORDER})'
  ${EndIf}

  Pop $9
  Pop $8
  Pop $7
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 标题栏(宏实现,接受前缀以区分安装/卸载)
; ---------------------------------------------------------------------------
!macro ST_CreateTitleBarImpl
  Push $0
  Push $1
  !insertmacro ST_HoverResetImpl
  ${NSD_CreateLabel} 0 0 $ST_WIN_Wpx $ST_TITLE_Hpx ""
  Pop $ST_TITLEBAR
  !insertmacro ST_SetColors $ST_TITLEBAR "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_MakeClickThrough $ST_TITLEBAR

  ; 标题栏小图标(18px, 垂直居中)
  !insertmacro ST_CreateIcon 14 10 18 $1
  !insertmacro ST_SetColors $1 "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"

  !insertmacro ST_Scale $ST_S0 42px
  !insertmacro ST_Scale $ST_S1 500px
  ${NSD_CreateLabel} $ST_S0px 0 $ST_S1px $ST_TITLE_Hpx "${PRODUCT_NAME}"
  Pop $ST_TITLEBAR_TITLE
  !insertmacro ST_SetColors $ST_TITLEBAR_TITLE "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_MakeClickThrough $ST_TITLEBAR_TITLE
  ; 垂直居中,与左侧小图标对齐
  System::Call 'user32::GetWindowLong(i $ST_TITLEBAR_TITLE, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 | ${SS_CENTERIMAGE}
  System::Call 'user32::SetWindowLong(i $ST_TITLEBAR_TITLE, i ${GWL_STYLE}, i r0)'
  SendMessage $ST_TITLEBAR_TITLE ${WM_SETFONT} $ST_FONT_SM 1

  !insertmacro ST_Scale $ST_S0 712px
  !insertmacro ST_Scale $ST_S1 44px
  ${NSD_CreateLabel} $ST_S0px 0 $ST_S1px $ST_TITLE_Hpx "–"
  Pop $ST_BTN_MIN
  !insertmacro ST_CenterActionLabel $ST_BTN_MIN "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"
  SendMessage $ST_BTN_MIN ${WM_SETFONT} $ST_FONT_BTN 1
  !insertmacro ST_HoverRegister $ST_BTN_MIN 3

  !insertmacro ST_Scale $ST_S0 756px
  ${NSD_CreateLabel} $ST_S0px 0 $ST_S1px $ST_TITLE_Hpx "×"
  Pop $ST_BTN_CLOSE
  !insertmacro ST_CenterActionLabel $ST_BTN_CLOSE "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"
  SendMessage $ST_BTN_CLOSE ${WM_SETFONT} $ST_FONT_BTN 1
  !insertmacro ST_HoverRegister $ST_BTN_CLOSE 4

  Pop $1
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 圆角裁剪: 把控件裁剪为圆角矩形(RADIUS 为 100% 基准像素, 传 32 得正圆)
; ---------------------------------------------------------------------------
!macro ST_RoundRect HANDLE W H RADIUS
  Push $0
  Push $1
  Push $2
  Push $3
  IntOp $0 ${RADIUS} * $ST_SCALE
  IntOp $0 $0 / 100
  IntOp $1 ${W} + 1
  IntOp $2 ${H} + 1
  System::Call 'gdi32::CreateRoundRectRgn(i 0, i 0, i r1, i r2, i r0, i r0) i .r3'
  System::Call 'user32::SetWindowRgn(i ${HANDLE}, i r3, i 1)'
  Pop $3
  Pop $2
  Pop $1
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 真实图标控件: SS_ICON STATIC + LoadImage(LR_LOADFROMFILE)
; ico 内嵌 PNG, Vista+ 透明渲染正常; 调用处需再 ST_SetColors 指定背景色
; ---------------------------------------------------------------------------
!ifndef SS_ICON
  !define SS_ICON 0x00000003
!endif
!ifndef STM_SETIMAGE
  !define STM_SETIMAGE 0x0172
!endif
!macro ST_CreateIcon X Y SIZE OUT_VAR
  Push $0
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${SIZE}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S2px ""
  Pop ${OUT_VAR}
  System::Call 'user32::GetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 | ${SS_ICON}
  System::Call 'user32::SetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}, i r0)'
  System::Call 'user32::LoadImage(i 0, t "${ST_LOGO_PATH}", i 1, i $ST_S2, i $ST_S2, i 0x00000010) i .r0'
  SendMessage ${OUT_VAR} ${STM_SETIMAGE} 1 $0
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; Hover 机制: STATIC Label 收不到 WM_MOUSEMOVE/WM_MOUSELEAVE,
; 复用 ST_DragTick 已验证的轮询模式, 50ms 检测光标下控件并换色
; ---------------------------------------------------------------------------
!macro ST_HoverResetImpl
  StrCpy $ST_HOV_CNT 0
  StrCpy $ST_HOV_CUR 0
  StrCpy $ST_HOV_CUR_T 0
!macroend

!macro ST_HoverRegister HANDLE TYPE
  ${If} $ST_HOV_CNT == 0
    StrCpy $ST_HOV_H0 ${HANDLE}
    StrCpy $ST_HOV_T0 "${TYPE}"
  ${ElseIf} $ST_HOV_CNT == 1
    StrCpy $ST_HOV_H1 ${HANDLE}
    StrCpy $ST_HOV_T1 "${TYPE}"
  ${ElseIf} $ST_HOV_CNT == 2
    StrCpy $ST_HOV_H2 ${HANDLE}
    StrCpy $ST_HOV_T2 "${TYPE}"
  ${ElseIf} $ST_HOV_CNT == 3
    StrCpy $ST_HOV_H3 ${HANDLE}
    StrCpy $ST_HOV_T3 "${TYPE}"
  ${ElseIf} $ST_HOV_CNT == 4
    StrCpy $ST_HOV_H4 ${HANDLE}
    StrCpy $ST_HOV_T4 "${TYPE}"
  ${ElseIf} $ST_HOV_CNT == 5
    StrCpy $ST_HOV_H5 ${HANDLE}
    StrCpy $ST_HOV_T5 "${TYPE}"
  ${EndIf}
  IntOp $ST_HOV_CNT $ST_HOV_CNT + 1
!macroend

; 按类型涂色(MODE: 0=普通 1=悬浮), 涂完 InvalidateRect 触发重绘
!macro ST_HoverPaint HANDLE TYPE MODE
  ${If} ${TYPE} == "0"
    ${If} ${MODE} == "1"
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_ACCENT_HOVER}"
    ${Else}
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_ACCENT}"
    ${EndIf}
  ${ElseIf} ${TYPE} == "1"
    ${If} ${MODE} == "1"
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_PRIMARY}" "0x${COLOR_BORDER}"
    ${Else}
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_PRIMARY}" "0x${COLOR_BG_SURFACE}"
    ${EndIf}
  ${ElseIf} ${TYPE} == "2"
    ${If} ${MODE} == "1"
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_DANGER_HOVER}"
    ${Else}
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_DANGER}"
    ${EndIf}
  ${ElseIf} ${TYPE} == "3"
    ${If} ${MODE} == "1"
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_SIDEBAR}" "0x${COLOR_TITLEBAR_HOVER}"
    ${Else}
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_SIDEBAR}" "0x${COLOR_SIDEBAR_BG}"
    ${EndIf}
  ${Else}
    ${If} ${MODE} == "1"
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_DANGER}"
    ${Else}
      SetCtlColors ${HANDLE} "0x${COLOR_TEXT_SIDEBAR}" "0x${COLOR_SIDEBAR_BG}"
    ${EndIf}
  ${EndIf}
  System::Call 'user32::InvalidateRect(i ${HANDLE}, i 0, i 1)'
!macroend

!macro ST_HoverTickImpl
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  System::Alloc 8
  Pop $1
  System::Call 'user32::GetCursorPos(i r1)'
  System::Call '*$1(i .r2, i .r3)'
  System::Free $1
  System::Call 'user32::WindowFromPoint(i r2, i r3) i .r4'
  ; 在注册表中查找光标下的控件
  StrCpy $5 "0"
  StrCpy $6 "0"
  ${If} $ST_HOV_CNT > 0
  ${AndIf} $4 == $ST_HOV_H0
    StrCpy $5 $ST_HOV_H0
    StrCpy $6 $ST_HOV_T0
  ${ElseIf} $ST_HOV_CNT > 1
  ${AndIf} $4 == $ST_HOV_H1
    StrCpy $5 $ST_HOV_H1
    StrCpy $6 $ST_HOV_T1
  ${ElseIf} $ST_HOV_CNT > 2
  ${AndIf} $4 == $ST_HOV_H2
    StrCpy $5 $ST_HOV_H2
    StrCpy $6 $ST_HOV_T2
  ${ElseIf} $ST_HOV_CNT > 3
  ${AndIf} $4 == $ST_HOV_H3
    StrCpy $5 $ST_HOV_H3
    StrCpy $6 $ST_HOV_T3
  ${ElseIf} $ST_HOV_CNT > 4
  ${AndIf} $4 == $ST_HOV_H4
    StrCpy $5 $ST_HOV_H4
    StrCpy $6 $ST_HOV_T4
  ${ElseIf} $ST_HOV_CNT > 5
  ${AndIf} $4 == $ST_HOV_H5
    StrCpy $5 $ST_HOV_H5
    StrCpy $6 $ST_HOV_T5
  ${EndIf}
  ; 命中变化时才重绘(避免 SetCtlColors 频繁建画刷)
  ${If} $5 != $ST_HOV_CUR
    ${If} $ST_HOV_CUR != 0
      !insertmacro ST_HoverPaint $ST_HOV_CUR $ST_HOV_CUR_T 0
    ${EndIf}
    ${If} $5 != 0
      !insertmacro ST_HoverPaint $5 $6 1
      StrCpy $ST_HOV_CUR $5
      StrCpy $ST_HOV_CUR_T $6
    ${Else}
      StrCpy $ST_HOV_CUR 0
      StrCpy $ST_HOV_CUR_T 0
    ${EndIf}
  ${EndIf}
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
!macroend

; ---------------------------------------------------------------------------
; 函数封装:安装版(ST_*)与卸载版(un.ST_*)
; ---------------------------------------------------------------------------
Function ST_InitFonts
  !insertmacro ST_InitFontsImpl
FunctionEnd
Function un.ST_InitFonts
  !insertmacro ST_InitFontsImpl
FunctionEnd

Function ST_InitBrushes
  !insertmacro ST_InitBrushesImpl
FunctionEnd
Function un.ST_InitBrushes
  !insertmacro ST_InitBrushesImpl
FunctionEnd

Function ST_SetupWindow
  !insertmacro ST_SetupWindowImpl
FunctionEnd
Function un.ST_SetupWindow
  !insertmacro ST_SetupWindowImpl
FunctionEnd

Function ST_ApplyWindowLayout
  ${NSD_KillTimer} ST_ApplyWindowLayout
  Call ST_SetupWindow
  Call ST_HideDefaultNavigation
FunctionEnd
Function un.ST_ApplyWindowLayout
  ${NSD_KillTimer} un.ST_ApplyWindowLayout
  Call un.ST_SetupWindow
  Call un.ST_HideDefaultNavigation
FunctionEnd

Function ST_CreateTitleBar
  !insertmacro ST_CreateTitleBarImpl
  ; 绑定按钮事件(安装器)
  ${NSD_OnClick} $ST_BTN_MIN ST_OnMinClick
  ${NSD_OnClick} $ST_BTN_CLOSE ST_OnCloseClick
  ; 标题栏拖拽轮询(防重复先 Kill)
  ${NSD_KillTimer} ST_DragTick
  ${NSD_CreateTimer} ST_DragTick 25
  ; Hover 轮询
  ${NSD_KillTimer} ST_HoverTick
  ${NSD_CreateTimer} ST_HoverTick 50
FunctionEnd
Function un.ST_CreateTitleBar
  !insertmacro ST_CreateTitleBarImpl
  ; 绑定按钮事件(卸载器)
  ${NSD_OnClick} $ST_BTN_MIN un.ST_OnMinClick
  ${NSD_OnClick} $ST_BTN_CLOSE un.ST_OnCloseClick
  ${NSD_KillTimer} un.ST_DragTick
  ${NSD_CreateTimer} un.ST_DragTick 25
  ${NSD_KillTimer} un.ST_HoverTick
  ${NSD_CreateTimer} un.ST_HoverTick 50
FunctionEnd

Function ST_HoverTick
  !insertmacro ST_HoverTickImpl
FunctionEnd
Function un.ST_HoverTick
  !insertmacro ST_HoverTickImpl
FunctionEnd

; ---------------------------------------------------------------------------
; 标题栏按钮事件
; ---------------------------------------------------------------------------
!macro ST_OnMinClickImpl
  System::Call 'user32::ShowWindow(i $HWNDPARENT, i 6)'
!macroend
!macro ST_OnCloseClickImpl
  SendMessage $HWNDPARENT ${WM_CLOSE} 0 0
!macroend

Function ST_OnMinClick
  !insertmacro ST_OnMinClickImpl
FunctionEnd
Function un.ST_OnMinClick
  !insertmacro ST_OnMinClickImpl
FunctionEnd

Function ST_OnCloseClick
  ${If} $ST_CURRENT_PAGE == ${STEP_FINISH}
    GetDlgItem $0 $HWNDPARENT 1
    SendMessage $0 ${BM_CLICK} 0 0
  ${Else}
    !insertmacro ST_OnCloseClickImpl
  ${EndIf}
FunctionEnd
Function un.ST_OnCloseClick
  ${If} $ST_CURRENT_PAGE == ${UNSTEP_FINISH}
    GetDlgItem $0 $HWNDPARENT 1
    SendMessage $0 ${BM_CLICK} 0 0
  ${Else}
    !insertmacro ST_OnCloseClickImpl
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------------------
; 标题栏拖拽: 标题栏是点击穿透的 Label, 收不到鼠标消息;
; 用 25ms 轮询检测左键在标题栏带内按下, 转发 WM_NCLBUTTONDOWN+HTCAPTION
; 让系统进入标准移动循环(模态, 直到左键松开, 期间 ST_DRAG_HELD 防重入)
; ---------------------------------------------------------------------------
!macro ST_DragTickImpl
  Push $0
  Push $1
  Push $2
  Push $3
  Push $4
  Push $5
  Push $6
  System::Call 'user32::GetAsyncKeyState(i 1) i .r0'
  IntOp $0 $0 & 0x8000
  ${If} $0 == 0
    StrCpy $ST_DRAG_HELD 0
  ${ElseIf} $ST_DRAG_HELD != 1
    System::Alloc 8
    Pop $1
    System::Call 'user32::GetCursorPos(i r1)'
    System::Call '*$1(i .r2, i .r3)'
    System::Free $1
    System::Call 'user32::WindowFromPoint(i r2, i r3) i .r4'
    ${If} $4 != 0
    ${AndIf} $4 != $ST_BTN_MIN
    ${AndIf} $4 != $ST_BTN_CLOSE
      System::Call 'user32::GetAncestor(i r4, i 2) i .r5'
      ${If} $5 == $HWNDPARENT
        System::Alloc 16
        Pop $1
        System::Call 'user32::GetWindowRect(i $HWNDPARENT, i r1)'
        System::Call '*$1(i .r4, i .r5, i .r0)'
        System::Free $1
        IntOp $6 $5 + $ST_TITLE_H
        ${If} $2 >= $4
        ${AndIf} $2 < $0
        ${AndIf} $3 >= $5
        ${AndIf} $3 < $6
          StrCpy $ST_DRAG_HELD 1
          SendMessage $HWNDPARENT ${WM_NCLBUTTONDOWN} ${HTCAPTION} 0
        ${EndIf}
      ${EndIf}
    ${EndIf}
  ${EndIf}
  Pop $6
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
!macroend

Function ST_DragTick
  !insertmacro ST_DragTickImpl
FunctionEnd
Function un.ST_DragTick
  !insertmacro ST_DragTickImpl
FunctionEnd

; MUI 托管页中的 CreateWindowEx 控件不能依赖 nsDialogs::OnClick。
; 与拖动相同，轮询真实鼠标按下/松开，并只在同一控件内完成点击时执行动作。
!macro ST_ManagedActionTickImpl MIN_FUNCTION CLOSE_FUNCTION PRIMARY_FUNCTION
  Push $0
  Push $1
  Push $2
  Push $3
  System::Call 'user32::GetAsyncKeyState(i 1) i .r0'
  IntOp $0 $0 & 0x8000
  ${If} $0 != 0
    ${If} $ST_ACTION_HELD == 0
      StrCpy $ST_ACTION_HELD 1
      StrCpy $ST_ACTION_DOWN 0
      System::Alloc 8
      Pop $1
      System::Call 'user32::GetCursorPos(i r1)'
      System::Call '*$1(i .r2, i .r3)'
      System::Free $1
      System::Call 'user32::WindowFromPoint(i r2, i r3) i .r1'
      ${If} $1 == $ST_BTN_MIN
      ${OrIf} $1 == $ST_BTN_CLOSE
      ${OrIf} $1 == $ST_MANAGED_PRIMARY
        StrCpy $ST_ACTION_DOWN $1
      ${EndIf}
    ${EndIf}
  ${ElseIf} $ST_ACTION_HELD == 1
    StrCpy $ST_ACTION_HELD 0
    System::Alloc 8
    Pop $1
    System::Call 'user32::GetCursorPos(i r1)'
    System::Call '*$1(i .r2, i .r3)'
    System::Free $1
    System::Call 'user32::WindowFromPoint(i r2, i r3) i .r1'
    ${If} $ST_ACTION_DOWN != 0
    ${AndIf} $1 == $ST_ACTION_DOWN
      ${If} $1 == $ST_BTN_MIN
        Call ${MIN_FUNCTION}
      ${ElseIf} $1 == $ST_BTN_CLOSE
        Call ${CLOSE_FUNCTION}
      ${ElseIf} $1 == $ST_MANAGED_PRIMARY
        Call ${PRIMARY_FUNCTION}
      ${EndIf}
    ${EndIf}
    StrCpy $ST_ACTION_DOWN 0
  ${EndIf}
  Pop $3
  Pop $2
  Pop $1
  Pop $0
!macroend

Function ST_ManagedActionTick
  ; MUI 在 SHOW 回调返回后才把 finish 内层对话框切到前面，持续确保自定义主按钮可命中。
  ${If} $ST_MANAGED_PRIMARY != 0
    Call ST_FinishRaiseControls
  ${EndIf}
  !insertmacro ST_ManagedActionTickImpl ST_OnMinClick ST_OnCloseClick ST_PageFinish_Done
FunctionEnd

Function un.ST_ManagedActionTick
  !insertmacro ST_ManagedActionTickImpl un.ST_OnMinClick un.ST_OnCloseClick un.ST_ManagedPrimaryNoop
FunctionEnd

Function un.ST_ManagedPrimaryNoop
FunctionEnd

; ---------------------------------------------------------------------------
; 默认向导导航:保留原生状态机,只隐藏系统按钮并由自定义控件触发
; ---------------------------------------------------------------------------
!macro ST_HideDefaultNavigationImpl
  Push $0
  ${If} $ST_OUTER_HWND == 0
    StrCpy $ST_OUTER_HWND $HWNDPARENT
  ${EndIf}
  GetDlgItem $0 $ST_OUTER_HWND 1
  ShowWindow $0 ${SW_HIDE}
  GetDlgItem $0 $ST_OUTER_HWND 2
  ShowWindow $0 ${SW_HIDE}
  GetDlgItem $0 $ST_OUTER_HWND 3
  ShowWindow $0 ${SW_HIDE}
  Pop $0
!macroend

!macro ST_ClickWizardButtonImpl CONTROL_ID
  Push $0
  ${If} $ST_OUTER_HWND == 0
    StrCpy $ST_OUTER_HWND $HWNDPARENT
  ${EndIf}
  GetDlgItem $0 $ST_OUTER_HWND ${CONTROL_ID}
  SendMessage $0 ${BM_CLICK} 0 0
  Pop $0
!macroend

Function ST_HideDefaultNavigation
  !insertmacro ST_HideDefaultNavigationImpl
FunctionEnd
Function un.ST_HideDefaultNavigation
  !insertmacro ST_HideDefaultNavigationImpl
FunctionEnd

Function ST_GoNext
  !insertmacro ST_ClickWizardButtonImpl 1
FunctionEnd
Function un.ST_GoNext
  !insertmacro ST_ClickWizardButtonImpl 1
FunctionEnd

Function ST_GoBack
  !insertmacro ST_ClickWizardButtonImpl 3
FunctionEnd

; ---------------------------------------------------------------------------
; 按钮/标签/输入框创建宏(坐标按 $ST_SCALE 缩放)
; ---------------------------------------------------------------------------
!macro ST_CreatePrimaryButton X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_CenterActionLabel ${OUT_VAR} "${COLOR_TEXT_ON_ACCENT}" "${COLOR_ACCENT}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BTN 1
  !insertmacro ST_RoundRect ${OUT_VAR} $ST_S2 $ST_S3 ${RADIUS_MD}
  !insertmacro ST_HoverRegister ${OUT_VAR} 0
!macroend

!macro ST_CreateSecondaryButton X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_CenterActionLabel ${OUT_VAR} "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_SURFACE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BTN 1
  !insertmacro ST_RoundRect ${OUT_VAR} $ST_S2 $ST_S3 ${RADIUS_MD}
  !insertmacro ST_HoverRegister ${OUT_VAR} 1
!macroend

!macro ST_CreateDangerButton X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_CenterActionLabel ${OUT_VAR} "${COLOR_TEXT_ON_ACCENT}" "${COLOR_DANGER}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BTN 1
  !insertmacro ST_RoundRect ${OUT_VAR} $ST_S2 $ST_S3 ${RADIUS_MD}
  !insertmacro ST_HoverRegister ${OUT_VAR} 2
!macroend

!macro ST_CreateTitle X Y W TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 28px
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_BASE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_TITLE 1
!macroend

!macro ST_CreateSubtitle X Y W TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 20px
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_SECONDARY}" "${COLOR_BG_BASE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_SUBTITLE 1
!macroend

!macro ST_CreateBody X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_BASE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BODY 1
!macroend

!macro ST_CreateSmall X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_SECONDARY}" "${COLOR_BG_BASE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_SM 1
!macroend

!macro ST_CreateTiny X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_TERTIARY}" "${COLOR_BG_BASE}"
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_XS 1
!macroend

!macro ST_CreateCheckbox X Y W TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 20px
  ${NSD_CreateCheckbox} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BODY 1
!macroend

!macro ST_CreateOptionLabel X Y W TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 22px
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_BASE}"
  System::Call 'user32::GetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 | ${SS_NOTIFY}
  System::Call 'user32::SetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}, i r0)'
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BODY 1
!macroend

!macro ST_CreatePathField X Y W TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 28px
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "${TEXT}"
  Pop ${OUT_VAR}
  !insertmacro ST_SetColors ${OUT_VAR} "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_SURFACE}"
  System::Call 'user32::GetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}) i .r0'
  IntOp $0 $0 | ${SS_NOTIFY}
  IntOp $0 $0 | ${SS_CENTERIMAGE}
  IntOp $0 $0 | ${SS_PATHELLIPSIS}
  System::Call 'user32::SetWindowLong(i ${OUT_VAR}, i ${GWL_STYLE}, i r0)'
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_SM 1
!macroend

; ---------------------------------------------------------------------------
; 进度条
; ---------------------------------------------------------------------------
!macro ST_CreateProgressBar X Y W H OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ${NSD_CreateProgressBar} $ST_S0px $ST_S1px $ST_S2px $ST_S3px ""
  Pop ${OUT_VAR}
  System::Call 'uxtheme::SetWindowTheme(i ${OUT_VAR}, w "", w "")'
  SendMessage ${OUT_VAR} ${PBM_SETBARCOLOR} 0 ${BGR_ACCENT}
  SendMessage ${OUT_VAR} ${PBM_SETBKCOLOR} 0 ${BGR_BORDER}
  SendMessage ${OUT_VAR} ${PBM_SETRANGE} 0 0x00000064
!macroend

!macro ST_SetProgress HWND PERCENT
  SendMessage ${HWND} ${PBM_SETPOS} ${PERCENT} 0
!macroend

; ---------------------------------------------------------------------------
; instfiles 页(MUI_PAGE_INSTFILES)专用: 原生 Win32 控件
; 该页面没有 nsDialogs 上下文, 禁止使用 NSD_* / nsDialogs::CreateControl
; (会因插件残留上一页对话框状态而崩溃), 全部用 CreateWindowEx 创建。
; ---------------------------------------------------------------------------
!ifndef SS_CENTER
  !define SS_CENTER            0x00000001
!endif
!ifndef SS_CENTERIMAGE
  !define SS_CENTERIMAGE       0x00000200
!endif
!ifndef SS_NOTIFY
  !define SS_NOTIFY            0x00000100
!endif
!ifndef BS_AUTOCHECKBOX
  !define BS_AUTOCHECKBOX      0x00000003
!endif
!ifndef IMAGE_ICON
  !define IMAGE_ICON           1
!endif
!ifndef LR_LOADFROMFILE
  !define LR_LOADFROMFILE      0x00000010
!endif

; 原生静态文本/背景块。FG/BG 为 BGR COLORREF(0x00BBGGRR)
!macro ST_RawStatic PARENT X Y W H TEXT STYLE FG BG OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ; System::Call 不解析空格分隔的位或表达式(i ${A} | ${B} 只取第一个值),
  ; 会静默丢弃 WS_VISIBLE 导致控件创建后永远不可见, 必须先用 IntOp 预计算样式
  IntOp $ST_STYLE ${WS_CHILD} | ${WS_VISIBLE}
  IntOp $ST_STYLE $ST_STYLE | ${STYLE}
  System::Call 'user32::CreateWindowEx(i 0, t "STATIC", t "${TEXT}", i $ST_STYLE, i $ST_S0, i $ST_S1, i $ST_S2, i $ST_S3, i ${PARENT}, i 0, i 0, i 0) i .s'
  Pop ${OUT_VAR}
  SetCtlColors ${OUT_VAR} ${FG} ${BG}
!macroend

; 原生静态文本 + 字体
!macro ST_RawStaticFont PARENT X Y W H TEXT STYLE FG BG FONT OUT_VAR
  !insertmacro ST_RawStatic ${PARENT} ${X} ${Y} ${W} ${H} "${TEXT}" ${STYLE} ${FG} ${BG} ${OUT_VAR}
  SendMessage ${OUT_VAR} ${WM_SETFONT} ${FONT} 1
!macroend

; 原生图标(logo)。注意 NSIS 宏不支持空字符串参数, FG 传任意有效 COLORREF(图标控件不使用前景色)
!macro ST_RawIcon PARENT X Y SIZE FG BG OUT_VAR
  !insertmacro ST_RawStatic ${PARENT} ${X} ${Y} ${SIZE} ${SIZE} " " ${SS_ICON} ${FG} ${BG} ${OUT_VAR}
  System::Call 'user32::LoadImage(i 0, t "${ST_LOGO_PATH}", i ${IMAGE_ICON}, i $ST_S2, i $ST_S2, i ${LR_LOADFROMFILE}) i .r0'
  System::Call 'user32::SendMessage(i ${OUT_VAR}, i ${STM_SETIMAGE}, i ${IMAGE_ICON}, i r0)'
!macroend

; 原生进度条
!macro ST_RawProgress PARENT X Y W H BAR_BGR ID OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  ; 同 ST_RawStatic: IntOp 预计算, 避免 System::Call 丢弃 WS_VISIBLE
  IntOp $ST_STYLE ${WS_CHILD} | ${WS_VISIBLE}
  IntOp $ST_STYLE $ST_STYLE | ${PBS_SMOOTH}
  System::Call 'user32::CreateWindowEx(i 0, t "msctls_progress32", t "", i $ST_STYLE, i $ST_S0, i $ST_S1, i $ST_S2, i $ST_S3, i ${PARENT}, i ${ID}, i 0, i 0) i .s'
  Pop ${OUT_VAR}
  System::Call 'uxtheme::SetWindowTheme(i ${OUT_VAR}, w "", w "")'
  SendMessage ${OUT_VAR} ${PBM_SETBARCOLOR} 0 ${BAR_BGR}
  SendMessage ${OUT_VAR} ${PBM_SETBKCOLOR} 0 ${BGR_BORDER}
  SendMessage ${OUT_VAR} ${PBM_SETRANGE} 0 0x00000064
!macroend

; 原生复选框。MUI 托管完成页不创建 nsDialogs 上下文，因此用 Win32 控件，
; 避免“立即运行”晚于页面其他内容出现。
!macro ST_RawCheckbox PARENT X Y W H TEXT OUT_VAR
  !insertmacro ST_Scale $ST_S0 ${X}
  !insertmacro ST_Scale $ST_S1 ${Y}
  !insertmacro ST_Scale $ST_S2 ${W}
  !insertmacro ST_Scale $ST_S3 ${H}
  IntOp $ST_STYLE ${WS_CHILD} | ${WS_VISIBLE}
  IntOp $ST_STYLE $ST_STYLE | ${BS_AUTOCHECKBOX}
  System::Call 'user32::CreateWindowEx(i 0, t "BUTTON", t "${TEXT}", i $ST_STYLE, i $ST_S0, i $ST_S1, i $ST_S2, i $ST_S3, i ${PARENT}, i 0, i 0, i 0) i .s'
  Pop ${OUT_VAR}
  System::Call 'uxtheme::SetWindowTheme(i ${OUT_VAR}, w "Explorer", w "")'
  SetCtlColors ${OUT_VAR} ${BGR_TEXT_PRIMARY} ${BGR_BG_BASE}
  SendMessage ${OUT_VAR} ${WM_SETFONT} $ST_FONT_BODY 1
!macroend

; 销毁原生控件句柄(从安装/卸载中页离开时清理, 避免残影覆盖完成页)
!macro ST_RawDestroy HANDLE
  ${If} ${HANDLE} != 0
    System::Call 'user32::DestroyWindow(i ${HANDLE})'
    StrCpy ${HANDLE} 0
  ${EndIf}
!macroend

; 步骤指示器一项(原生控件版): 圆点 + 文本
; Y=100% 基准纵坐标, IDX=步骤序号, CUR=当前步骤序号, TEXT=文案,
; DOT_FG=当前步圆点色, LBL_FG=当前步文本色, SIDE_BG=侧边栏背景色(其余步骤沿用)
!macro ST_InstStepItem PARENT Y IDX CUR DONE_TEXT TEXT DOT_FG LBL_FG SIDE_BG
  IntOp $ST_IP_STEP_Y ${Y} + 2
  ${If} ${IDX} < ${CUR}
    !insertmacro ST_RawStaticFont ${PARENT} 24 ${Y} 20 20 "${DONE_TEXT}" 0 ${BGR_SUCCESS} ${SIDE_BG} $ST_FONT_SM $ST_IP_STEP_DOT
    !insertmacro ST_RawStaticFont ${PARENT} 52 $ST_IP_STEP_Y 170 20 "${TEXT}" 0 ${BGR_TEXT_SIDEBAR} ${SIDE_BG} $ST_FONT_STEP $ST_IP_STEP_LBL
  ${ElseIf} ${IDX} == ${CUR}
    !insertmacro ST_RawStaticFont ${PARENT} 24 ${Y} 20 20 "●" 0 ${DOT_FG} ${SIDE_BG} $ST_FONT_SM $ST_IP_STEP_DOT
    !insertmacro ST_RawStaticFont ${PARENT} 52 $ST_IP_STEP_Y 170 20 "${TEXT}" 0 ${LBL_FG} ${SIDE_BG} $ST_FONT_STEP $ST_IP_STEP_LBL
  ${Else}
    !insertmacro ST_RawStaticFont ${PARENT} 24 ${Y} 20 20 "●" 0 ${BGR_TEXT_TERTIARY} ${SIDE_BG} $ST_FONT_SM $ST_IP_STEP_DOT
    !insertmacro ST_RawStaticFont ${PARENT} 52 $ST_IP_STEP_Y 170 20 "${TEXT}" 0 ${BGR_TEXT_SIDEBAR} ${SIDE_BG} $ST_FONT_STEP $ST_IP_STEP_LBL
  ${EndIf}
!macroend

; instfiles 页整体 chrome: 标题栏 + logo + 应用名 + 侧边栏 + 内容区背景 + 内容标题
; PARENT=内层对话框句柄, SIDE_BGR/TITLE_BGR=侧边栏与标题栏背景色(BGR COLORREF),
; PAGE_TITLE=内容标题文案, PAGE_MSG=标题下描述文本(可空 "")
!macro ST_InstFilesChrome PARENT SIDE_BGR TITLE_BGR PAGE_TITLE PAGE_MSG
  Push $0
  Push $1
  StrCpy $ST_IP_PARENT ${PARENT}

  ; IntOp 预计算窗口样式(见 ST_RawStatic 注释: System::Call 会丢弃空格分隔位或里的 WS_VISIBLE)
  IntOp $ST_STYLE ${WS_CHILD} | ${WS_VISIBLE}

  ; 1) 内容区背景(白) - x>=SIDEBAR_WIDTH, y>=TITLE_H
  !insertmacro ST_Scale $ST_S0 ${SIDEBAR_WIDTH}
  IntOp $ST_S1 $ST_WIN_W - $ST_S0
  IntOp $ST_S2 $ST_WIN_H - $ST_TITLE_H
  System::Call 'user32::CreateWindowEx(i 0, t "STATIC", t "", i $ST_STYLE, i $ST_S0, i $ST_TITLE_H, i $ST_S1, i $ST_S2, i $ST_IP_PARENT, i 0, i 0, i 0) i .s'
  Pop $ST_IP_CONTENT
  SetCtlColors $ST_IP_CONTENT "" 0x00ffffff

  ; 2) 侧边栏背景(深色)
  System::Call 'user32::CreateWindowEx(i 0, t "STATIC", t "", i $ST_STYLE, i 0, i $ST_TITLE_H, i $ST_S0, i $ST_S2, i $ST_IP_PARENT, i 0, i 0, i 0) i .s'
  Pop $ST_IP_SIDEBAR
  SetCtlColors $ST_IP_SIDEBAR "" ${SIDE_BGR}

  ; 3) 标题栏背景(全宽深色带)
  System::Call 'user32::CreateWindowEx(i 0, t "STATIC", t "", i $ST_STYLE, i 0, i 0, i $ST_WIN_W, i $ST_TITLE_H, i $ST_IP_PARENT, i 0, i 0, i 0) i .s'
  Pop $ST_IP_TITLEBAR
  SetCtlColors $ST_IP_TITLEBAR "" ${TITLE_BGR}

  ; 4) logo + 应用名(标题栏上, 后创建者在上层)
  !insertmacro ST_RawIcon $ST_IP_PARENT 14 10 18 ${BGR_TEXT_SIDEBAR_DEF} ${TITLE_BGR} $ST_IP_LOGO
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 42 0 500 $ST_TITLE_H "${PRODUCT_NAME}" ${SS_CENTERIMAGE} ${BGR_TEXT_SIDEBAR_DEF} ${TITLE_BGR} $ST_FONT_SM $ST_IP_TITLE

  ; 5) 标题栏操作。托管页也使用与欢迎/安装位置页完全相同的位置、颜色和交互句柄。
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 712 0 44 $ST_TITLE_H "–" 0x00000301 ${BGR_TEXT_SIDEBAR_DEF} ${TITLE_BGR} $ST_FONT_BTN $ST_BTN_MIN
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 756 0 44 $ST_TITLE_H "×" 0x00000301 ${BGR_TEXT_SIDEBAR_DEF} ${TITLE_BGR} $ST_FONT_BTN $ST_BTN_CLOSE

  ; 6) 侧边栏: logo + 应用名 + 版本
  !insertmacro ST_RawIcon $ST_IP_PARENT 24 66 64 ${BGR_TEXT_SIDEBAR_DEF} ${SIDE_BGR} $ST_IP_SIDEBAR_LOGO
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 24 142 192 24 "${PRODUCT_NAME}" 0 ${BGR_TEXT_ON_ACCENT_DEF} ${SIDE_BGR} $ST_FONT_SIDEBAR_TITLE $ST_IP_SIDEBAR_NAME
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 24 170 192 18 "v${VERSION}" 0 ${BGR_TEXT_TERTIARY} ${SIDE_BGR} $ST_FONT_XS $ST_IP_SIDEBAR_VER

  ; 7) 内容标题 + 描述
  !insertmacro ST_RawStaticFont $ST_IP_PARENT 272 70 480 28 "${PAGE_TITLE}" 0 ${BGR_TEXT_PRIMARY_DEF} 0x00ffffff $ST_FONT_TITLE $ST_IP_PAGETITLE
  ${If} "${PAGE_MSG}" != " "
    !insertmacro ST_RawStaticFont $ST_IP_PARENT 272 106 480 20 "${PAGE_MSG}" 0 ${BGR_TEXT_SECONDARY_DEF} 0x00ffffff $ST_FONT_SUBTITLE $ST_IP_PAGEMSG
  ${EndIf}

  Pop $1
  Pop $0
!macroend

; MUI 的 instfiles/finish 页没有 nsDialogs::Show 生命周期。这里显式为原生标题栏
; 注册按钮和轮询计时器，使拖动、最小化、关闭、悬浮效果与前两页一致。
Function ST_StartManagedChromeInteraction
  !insertmacro ST_HoverResetImpl
  !insertmacro ST_HoverRegister $ST_BTN_MIN 3
  !insertmacro ST_HoverRegister $ST_BTN_CLOSE 4
  StrCpy $ST_ACTION_HELD 0
  StrCpy $ST_ACTION_DOWN 0
  Call ST_DragTick
  Call ST_HoverTick
  Call ST_ManagedActionTick
  ${NSD_KillTimer} ST_DragTick
  ${NSD_CreateTimer} ST_DragTick 25
  ${NSD_KillTimer} ST_HoverTick
  ${NSD_CreateTimer} ST_HoverTick 50
  ${NSD_KillTimer} ST_ManagedActionTick
  ${NSD_CreateTimer} ST_ManagedActionTick 25
FunctionEnd

Function un.ST_StartManagedChromeInteraction
  !insertmacro ST_HoverResetImpl
  !insertmacro ST_HoverRegister $ST_BTN_MIN 3
  !insertmacro ST_HoverRegister $ST_BTN_CLOSE 4
  StrCpy $ST_ACTION_HELD 0
  StrCpy $ST_ACTION_DOWN 0
  StrCpy $ST_MANAGED_PRIMARY 0
  Call un.ST_DragTick
  Call un.ST_HoverTick
  Call un.ST_ManagedActionTick
  ${NSD_KillTimer} un.ST_DragTick
  ${NSD_CreateTimer} un.ST_DragTick 25
  ${NSD_KillTimer} un.ST_HoverTick
  ${NSD_CreateTimer} un.ST_HoverTick 50
  ${NSD_KillTimer} un.ST_ManagedActionTick
  ${NSD_CreateTimer} un.ST_ManagedActionTick 25
FunctionEnd

Function ST_StopManagedChromeInteraction
  ${NSD_KillTimer} ST_DragTick
  ${NSD_KillTimer} ST_HoverTick
  ${NSD_KillTimer} ST_ManagedActionTick
FunctionEnd

Function un.ST_StopManagedChromeInteraction
  ${NSD_KillTimer} un.ST_DragTick
  ${NSD_KillTimer} un.ST_HoverTick
  ${NSD_KillTimer} un.ST_ManagedActionTick
FunctionEnd
