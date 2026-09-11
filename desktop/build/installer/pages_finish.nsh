; ============================================================================
; Score Trans Installer - 页面 4: 完成(MUI_PAGE_FINISH 自定义)
;
; 注意: 本页是 MUI 托管页(不能用 nsDialogs::Create, 会崩溃),
;       所有自定义控件用原生 CreateWindowEx(见 ST_Raw* 宏, 已修复 WS_VISIBLE 丢失问题)。
;
; MUI_PAGE_FINISH 默认控件布局(实测 NSIS 3.0.4):
;   $HWNDPARENT 顶层: 完成(ID=1)/取消(ID=2)/上一步(ID=3)/标题(1037)/描述(1038)
;   finish 内容 inner #32770: 大图(1200)/标题(1201)/描述(1202)/运行复选框(1203)
;   instfiles 残留 inner #32770: 进度条(1004)/已完成(1006)/日志(1016)/显示细节(1027)
; ============================================================================

Var ST_FINISH_RUN_CHECK   ; MUI 运行复选框(MUI_FINISHPAGE_RUN, ID=1203)
Var ST_FINISH_BTN_DONE    ; MUI 完成按钮(ID=1)

; ---------------------------------------------------------------------------
; 完成页 SHOW(由 MUI_PAGE_CUSTOMFUNCTION_SHOW 注入)
; ---------------------------------------------------------------------------
Function ST_PageFinish_Show
  Call ST_StopManagedChromeInteraction

  ; 销毁安装中页的原生控件(避免残影覆盖完成页)
  ; ST_INSTALLING_PROGRESS 通常是 MUI 自己的 1004 控件，隐藏即可，不能销毁宿主控件。
  ${If} $ST_INSTALLING_PROGRESS != 0
    ShowWindow $ST_INSTALLING_PROGRESS ${SW_HIDE}
    StrCpy $ST_INSTALLING_PROGRESS 0
  ${EndIf}
  !insertmacro ST_RawDestroy $ST_INSTALLING_PERCENT
  !insertmacro ST_RawDestroy $ST_INSTALLING_LABEL
  !insertmacro ST_RawDestroy $ST_IP_CONTENT
  !insertmacro ST_RawDestroy $ST_IP_SIDEBAR
  !insertmacro ST_RawDestroy $ST_IP_TITLEBAR
  !insertmacro ST_RawDestroy $ST_IP_LOGO
  !insertmacro ST_RawDestroy $ST_IP_TITLE
  !insertmacro ST_RawDestroy $ST_IP_SIDEBAR_LOGO
  !insertmacro ST_RawDestroy $ST_IP_SIDEBAR_NAME
  !insertmacro ST_RawDestroy $ST_IP_SIDEBAR_VER
  !insertmacro ST_RawDestroy $ST_IP_PAGETITLE
  !insertmacro ST_RawDestroy $ST_IP_PAGEMSG

  Call ST_SetupWindow

  ; 隐藏 MUI 原生导航，完成按钮改由本页一次性创建，避免与页面内容错峰出现。
  GetDlgItem $1 $HWNDPARENT 1
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 3
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 2
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 隐藏 MUI finish 默认标题/描述($HWNDPARENT 的 1037/1038)
  GetDlgItem $1 $HWNDPARENT 1037
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 1038
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 遍历所有 inner #32770: 隐藏 instfiles 残留 + finish 默认内容,
  ; 运行复选框也使用本页自己的原生控件；MUI 的 1203 只需隐藏。
  StrCpy $ST_FINISH_RUN_CHECK 0
  FindWindow $2 "#32770" "" $HWNDPARENT
  ${Do}
    ${If} $2 == 0
      ${ExitDo}
    ${EndIf}
    ; instfiles 残留
    GetDlgItem $1 $2 1004
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1006
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1016
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1027
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    ; finish 默认(大图/标题/描述)
    GetDlgItem $1 $2 1200
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1201
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    GetDlgItem $1 $2 1202
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    ; 隐藏 MUI 自带的运行复选框。
    GetDlgItem $1 $2 1203
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
    ${EndIf}
    ; 找下一个 inner
    System::Call 'user32::FindWindowEx(i $HWNDPARENT, i r2, t "#32770", i 0) i .r2'
  ${Loop}

  ; 画自定义 chrome(标题栏/侧边栏/内容区背景 + 步骤指示器, 4 步全勾)
  StrCpy $0 $HWNDPARENT
  StrCpy $ST_CURRENT_PAGE ${STEP_FINISH}
  !insertmacro ST_InstFilesChrome $0 ${BGR_SIDEBAR_BG} ${BGR_SIDEBAR_BG} "安装完成" " "
  !insertmacro ST_InstStepItem $0 240 0 ${STEP_FINISH} "✓" "欢迎" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 280 1 ${STEP_FINISH} "✓" "安装位置" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 320 2 ${STEP_FINISH} "✓" "安装中" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}
  !insertmacro ST_InstStepItem $0 360 3 ${STEP_FINISH} "✓" "完成" ${BGR_ACCENT_DEF} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG}

  ; ---- 自定义内容区 ----
  ; 大号成功图标(绿色圆形底 + 白色 ✓)
  !insertmacro ST_Scale $ST_S0 272px
  !insertmacro ST_Scale $ST_S1 110px
  !insertmacro ST_Scale $ST_S2 64px
  !insertmacro ST_RawStaticFont $0 272 110 64 64 "✓" ${SS_CENTER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SUCCESS} $ST_FONT_DISPLAY $3
  !insertmacro ST_RoundRect $3 $ST_S2 $ST_S2 32

  ; 标题
  !insertmacro ST_RawStaticFont $0 272 196 480 28 "安装完成" 0 ${BGR_TEXT_PRIMARY_DEF} 0x00ffffff $ST_FONT_TITLE $1

  ; 副标题
  !insertmacro ST_RawStaticFont $0 272 232 480 20 "Score Trans 已成功安装到您的计算机" 0 ${BGR_TEXT_SECONDARY_DEF} 0x00ffffff $ST_FONT_SUBTITLE $2

  ; 路径衬底(surface 圆角) + 路径文本
  !insertmacro ST_Scale $ST_S0 272px
  !insertmacro ST_Scale $ST_S1 268px
  !insertmacro ST_Scale $ST_S2 480px
  !insertmacro ST_Scale $ST_S3 28px
  !insertmacro ST_RawStatic $0 272 268 480 28 "" 0 ${BGR_TEXT_SECONDARY_DEF} ${BGR_BG_SURFACE} $4
  !insertmacro ST_RoundRect $4 $ST_S2 $ST_S3 ${RADIUS_SM}
  !insertmacro ST_RawStaticFont $0 272 268 480 28 "  安装位置:$INSTDIR" 0 ${BGR_TEXT_SECONDARY_DEF} ${BGR_BG_SURFACE} $ST_FONT_SM $5

  ; 运行选项与完成按钮同本页内容一起创建、一起显示。
  Call ST_FinishLayoutControls
  Call ST_StartManagedChromeInteraction
FunctionEnd

; ---------------------------------------------------------------------------
; 创建完成页的运行复选框与完成按钮
; ---------------------------------------------------------------------------
Function ST_FinishLayoutControls
  !insertmacro ST_RawCheckbox $HWNDPARENT 272 320 300 24 "立即运行 Score Trans" $ST_FINISH_RUN_CHECK
  SendMessage $ST_FINISH_RUN_CHECK ${BM_SETCHECK} ${BST_CHECKED} 0

  !insertmacro ST_RawStaticFont $HWNDPARENT 684 460 100 40 "完成" 0x00000301 ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_ACCENT} $ST_FONT_BTN $ST_FINISH_BTN_DONE
  !insertmacro ST_RoundRect $ST_FINISH_BTN_DONE $ST_S2 $ST_S3 ${RADIUS_MD}
  StrCpy $ST_MANAGED_PRIMARY $ST_FINISH_BTN_DONE
FunctionEnd

Function ST_PageFinish_Done
  SendMessage $ST_FINISH_RUN_CHECK ${BM_GETCHECK} 0 0 $0
  ${If} $0 == ${BST_CHECKED}
    Call ST_FinishRunApp
  ${EndIf}
  ; 由 MUI 原生完成按钮结束向导；托管 finish 页会忽略直接 WM_CLOSE。
  GetDlgItem $1 $HWNDPARENT 1
  ${If} $1 != 0
    SendMessage $1 ${BM_CLICK} 0 0
  ${EndIf}
FunctionEnd

; 供托管页交互轮询使用：确保复选框和完成按钮位于 MUI 内层页之上。
Function ST_FinishRaiseControls
  ${If} $ST_FINISH_RUN_CHECK != 0
    System::Call 'user32::SetWindowPos(i $ST_FINISH_RUN_CHECK, i 0, i 0, i 0, i 0, i 0, i 0x0013)'
  ${EndIf}
  ${If} $ST_FINISH_BTN_DONE != 0
    System::Call 'user32::SetWindowPos(i $ST_FINISH_BTN_DONE, i 0, i 0, i 0, i 0, i 0, i 0x0013)'
  ${EndIf}
FunctionEnd

; ---------------------------------------------------------------------------
; 启动已安装的应用
; ---------------------------------------------------------------------------
Function ST_FinishRunApp
  ${If} ${FileExists} "$launchLink"
    ${StdUtils.ExecShellAsUser} $0 "$launchLink" "open" ""
  ${Else}
    ExecShell "open" "$INSTDIR\${APP_EXECUTABLE_FILENAME}"
  ${EndIf}
FunctionEnd
