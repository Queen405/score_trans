; ============================================================================
; Score Trans Installer - 页面 3: 安装中(MUI_PAGE_INSTFILES 自定义)
; 通过 MUI_PAGE_CUSTOMFUNCTION_PRE/SHOW 完全替换默认 instfiles 页外观
; ============================================================================

Var ST_INSTALLING_PROGRESS     ; 进度条
Var ST_INSTALLING_PERCENT      ; 百分比文本
Var ST_INSTALLING_LABEL        ; 当前步骤描述
Var ST_INSTALLING_DIALOG       ; MUI instfiles 内层对话框

; ---------------------------------------------------------------------------
; MUI_PAGE_CUSTOMFUNCTION_PRE: 在 instfiles 页创建前调用
; 可在这里隐藏默认控件(但此时控件还没创建,留到 SHOW 里做)
; ---------------------------------------------------------------------------
Function ST_Installing_Pre
  ; 不 Abort,让 instfiles 页正常创建(Section 会执行)
FunctionEnd

; ---------------------------------------------------------------------------
; MUI_PAGE_CUSTOMFUNCTION_SHOW: 在 instfiles 页显示时调用
; 此时默认控件已创建,我们可以隐藏并替换
; ---------------------------------------------------------------------------
Function ST_Installing_Show
  StrCpy $ST_MANAGED_PRIMARY 0
  Call ST_SetupWindow
  Call ST_HideDefaultNavigation

  ; 隐藏 MUI 默认头部(标题/描述, 直接挂 $HWNDPARENT 顶层, GetDlgItem 可命中)
  GetDlgItem $1 $HWNDPARENT 1037
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 1038
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 隐藏 instfiles 页的默认日志与细节控件。原生进度条 1004 保留并直接美化，
  ; 它由 NSIS/Nsis7z 根据实际解压和写入状态驱动，比手工阶段百分比准确。
  ; 注意: 这三个控件挂在 MUI 内部的 #32770 对话框上, 不在 $HWNDPARENT 直接层级,
  ;       直接 GetDlgItem($HWNDPARENT, ...) 恒返回 0, 必须先 FindWindow 内层对话框
  FindWindow $2 "#32770" "" $HWNDPARENT
  ${If} $2 != 0
    StrCpy $ST_INSTALLING_DIALOG $2
    GetDlgItem $1 $2 1004
    ${If} $1 != 0
      StrCpy $ST_INSTALLING_PROGRESS $1
    ${EndIf}
    GetDlgItem $1 $2 1016
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1006
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
  ${EndIf}

  ; 将 chrome 与原生进度条放在同一个 MUI 内层对话框中，避免覆盖进度条，
  ; 同时保留 Nsis7z 对控件 ID=1004 的真实进度更新。
  ${If} $ST_INSTALLING_DIALOG != 0
    StrCpy $0 $ST_INSTALLING_DIALOG
  ${Else}
    StrCpy $0 $HWNDPARENT
  ${EndIf}

  ; 设置当前步骤并绘制页面 chrome(标题栏/侧边栏/内容区)
  StrCpy $ST_CURRENT_PAGE ${STEP_INSTALLING}

  !insertmacro ST_InstFilesChrome $0 ${BGR_SIDEBAR_BG} ${BGR_SIDEBAR_BG} "正在安装" " "
  !insertmacro ST_InstStepItem $0 240 0 ${STEP_INSTALLING} "✓" "欢迎" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 280 1 ${STEP_INSTALLING} "✓" "安装位置" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 320 2 ${STEP_INSTALLING} "✓" "安装中" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 360 3 ${STEP_INSTALLING} "✓" "完成" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}

  ; 移动并美化 MUI 原生进度条。若极少数主题资源中找不到 1004，创建后备控件。
  ${If} $ST_INSTALLING_PROGRESS == 0
    !insertmacro ST_RawProgress $0 272 224 488 8 ${BGR_ACCENT} ${IDC_PROGRESS} $ST_INSTALLING_PROGRESS
  ${Else}
    !insertmacro ST_Scale $ST_S0 272
    !insertmacro ST_Scale $ST_S1 224
    !insertmacro ST_Scale $ST_S2 488
    !insertmacro ST_Scale $ST_S3 8
    System::Call 'user32::SetWindowPos(i $ST_INSTALLING_PROGRESS, i 0, i $ST_S0, i $ST_S1, i $ST_S2, i $ST_S3, i 0)'
    System::Call 'uxtheme::SetWindowTheme(i $ST_INSTALLING_PROGRESS, w "", w "")'
    SendMessage $ST_INSTALLING_PROGRESS ${PBM_SETBARCOLOR} 0 ${BGR_ACCENT}
    SendMessage $ST_INSTALLING_PROGRESS ${PBM_SETBKCOLOR} 0 ${BGR_BORDER}
    ShowWindow $ST_INSTALLING_PROGRESS ${SW_SHOW}
  ${EndIf}

  !insertmacro ST_RawStaticFont $0 272 180 488 32 "正在安装应用文件" ${SS_CENTER} ${BGR_TEXT_PRIMARY_DEF} 0x00ffffff $ST_FONT_TITLE $ST_INSTALLING_PERCENT

  !insertmacro ST_RawStaticFont $0 272 246 488 24 "正在准备安装..." 0 ${BGR_TEXT_SECONDARY_DEF} 0x00ffffff $ST_FONT_SM $ST_INSTALLING_LABEL

  Call ST_StartManagedChromeInteraction
FunctionEnd

; ---------------------------------------------------------------------------
; 供 Section 调用的进度更新函数(在安装 Section 里 Call)
; ---------------------------------------------------------------------------
Function ST_Installing_StartInstall
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在准备安装..."
FunctionEnd

Function ST_Installing_UpdateStep1
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在检查运行中的应用..."
FunctionEnd

Function ST_Installing_UpdateStep2
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在解压并写入应用文件..."
FunctionEnd

Function ST_Installing_UpdateStep3
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在创建快捷方式..."
FunctionEnd

Function ST_Installing_UpdateStep4
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在写入注册表..."
FunctionEnd

Function ST_Installing_FinishInstall
  SendMessage $ST_INSTALLING_PERCENT ${WM_SETTEXT} 0 "STR:安装完成"
  SendMessage $ST_INSTALLING_LABEL ${WM_SETTEXT} 0 "STR:安装完成"
FunctionEnd
