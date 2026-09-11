; ============================================================================
; Score Trans Installer - 卸载器 3 页
; 所有函数以 un. 前缀(NSIS 卸载器规则)
; ============================================================================

Var ST_UN_WELCOME_DIALOG
Var ST_UN_WELCOME_BTN_NEXT
Var ST_UN_CHECK_DELETE_DATA
Var ST_UN_UNINSTALLING_PROGRESS
Var ST_UN_UNINSTALLING_LABEL
Var ST_UN_UNINSTALLING_PERCENT

; ---------------------------------------------------------------------------
; 页 1: 卸载确认
; ---------------------------------------------------------------------------
Function un.ST_UnPageWelcome_Show
  nsDialogs::Create 1018
  Pop $ST_UN_WELCOME_DIALOG
  ${If} $ST_UN_WELCOME_DIALOG == error
    Abort
  ${EndIf}
  System::Call 'user32::GetParent(i $ST_UN_WELCOME_DIALOG) i .s'
  Pop $ST_OUTER_HWND

  Call un.ST_SetupWindow

  StrCpy $ST_CURRENT_PAGE ${UNSTEP_WELCOME}

  Call un.ST_CreateTitleBar
  Push $ST_CURRENT_PAGE
  Call un.ST_CreateUninstallSidebar

  !insertmacro ST_CreateTitle 272px 70px 480px "卸载 Score Trans" $0
  !insertmacro ST_CreateSubtitle 272px 106px 480px "即将从您的计算机中移除 Score Trans" $1

  !insertmacro ST_CreateBody 272px 150px 480px 60px "卸载将删除:$\r$\n  · 应用程序文件$\r$\n  · 开始菜单和桌面快捷方式$\r$\n  · 注册表项" $2

  !insertmacro ST_CreateCheckbox 272px 240px 480px "同时删除用户数据(设置、缓存、历史记录)" $ST_UN_CHECK_DELETE_DATA
  SendMessage $ST_UN_CHECK_DELETE_DATA ${BM_SETCHECK} ${BST_CHECKED} 0

  !insertmacro ST_CreateTiny 272px 280px 480px 20px "安装位置:$INSTDIR" $3

  !insertmacro ST_CreateSecondaryButton 272px 460px 88px 40px "取消" $4
  ${NSD_OnClick} $4 un.ST_OnCloseClick

  !insertmacro ST_CreateDangerButton 684px 460px 100px 40px "卸载" $ST_UN_WELCOME_BTN_NEXT
  ${NSD_OnClick} $ST_UN_WELCOME_BTN_NEXT un.ST_UnPageWelcome_OnNext

  ${NSD_CreateTimer} un.ST_ApplyWindowLayout 250
  nsDialogs::Show
FunctionEnd

Function un.ST_UnPageWelcome_Leave
  SendMessage $ST_UN_CHECK_DELETE_DATA ${BM_GETCHECK} 0 0 $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $ST_DELETE_USER_DATA "1"
  ${Else}
    StrCpy $ST_DELETE_USER_DATA "0"
  ${EndIf}
FunctionEnd

Function un.ST_UnPageWelcome_OnNext
  Call un.ST_GoNext
FunctionEnd

; ---------------------------------------------------------------------------
; 页 2: 卸载中(MUI_UNPAGE_INSTFILES 自定义)
; ---------------------------------------------------------------------------
Function un.ST_UnInstalling_Pre
FunctionEnd

Function un.ST_UnInstalling_Show
  Call un.ST_SetupWindow
  Call un.ST_HideDefaultNavigation

  ; 控件父容器 = 主窗口(后创建者 Z 序更高, 盖住 MUI 默认头部)
  StrCpy $0 $HWNDPARENT

  GetDlgItem $1 $HWNDPARENT 1037
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 1038
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 隐藏默认控件(1004 进度条 / 1016 日志 / 1006 显示细节按钮)
  ; 注意: 这三个控件挂在 MUI 内部 #32770 对话框上, 不在 $HWNDPARENT 直接层级,
  ;       直接 GetDlgItem($HWNDPARENT, ...) 恒返回 0, 必须先 FindWindow 内层对话框
  FindWindow $2 "#32770" "" $HWNDPARENT
  ${If} $2 != 0
    GetDlgItem $1 $2 1004
    ${If} $1 != 0
      ShowWindow $1 ${SW_HIDE}
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

  ; 页面 chrome(卸载器深色主题) + 步骤指示器
  StrCpy $ST_CURRENT_PAGE ${UNSTEP_UNINSTALLING}

  !insertmacro ST_InstFilesChrome $0 ${BGR_SIDEBAR_BG_DARK} ${BGR_SIDEBAR_BG_DARK} "正在卸载" " "
  !insertmacro ST_InstStepItem $0 240 0 ${UNSTEP_UNINSTALLING} "✓" "确认卸载" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}
  !insertmacro ST_InstStepItem $0 280 1 ${UNSTEP_UNINSTALLING} "✓" "卸载中" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}
  !insertmacro ST_InstStepItem $0 320 2 ${UNSTEP_UNINSTALLING} "✓" "完成" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}

  ; 进度条 + 百分比 + 步骤描述(原生控件, 挂内层对话框)
  !insertmacro ST_RawProgress $0 272 224 488 8 ${BGR_DANGER} 6207 $ST_UN_UNINSTALLING_PROGRESS
  !insertmacro ST_RawStaticFont $0 272 180 488 32 "0%" ${SS_CENTER} ${BGR_TEXT_PRIMARY_DEF} 0x00ffffff $ST_FONT_DISPLAY $ST_UN_UNINSTALLING_PERCENT
  !insertmacro ST_RawStaticFont $0 272 246 488 24 "正在准备卸载..." 0 ${BGR_TEXT_SECONDARY_DEF} 0x00ffffff $ST_FONT_SM $ST_UN_UNINSTALLING_LABEL
  Call un.ST_StartManagedChromeInteraction
FunctionEnd

; ---------------------------------------------------------------------------
; 卸载进度更新(供 un.install Section 调用)
; ---------------------------------------------------------------------------
Function un.ST_UnInstalling_Start
  SendMessage $ST_UN_UNINSTALLING_PROGRESS ${PBM_SETPOS} 0 0
  SendMessage $ST_UN_UNINSTALLING_PERCENT ${WM_SETTEXT} 0 "STR:0%"
  SendMessage $ST_UN_UNINSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在准备卸载..."
FunctionEnd

Function un.ST_UnInstalling_UpdateStep1
  SendMessage $ST_UN_UNINSTALLING_PROGRESS ${PBM_SETPOS} 40 0
  SendMessage $ST_UN_UNINSTALLING_PERCENT ${WM_SETTEXT} 0 "STR:40%"
  SendMessage $ST_UN_UNINSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在删除应用程序文件..."
FunctionEnd

Function un.ST_UnInstalling_UpdateStep2
  SendMessage $ST_UN_UNINSTALLING_PROGRESS ${PBM_SETPOS} 70 0
  SendMessage $ST_UN_UNINSTALLING_PERCENT ${WM_SETTEXT} 0 "STR:70%"
  SendMessage $ST_UN_UNINSTALLING_LABEL ${WM_SETTEXT} 0 "STR:正在删除快捷方式..."
FunctionEnd

Function un.ST_UnInstalling_Finish
  SendMessage $ST_UN_UNINSTALLING_PROGRESS ${PBM_SETPOS} 100 0
  SendMessage $ST_UN_UNINSTALLING_PERCENT ${WM_SETTEXT} 0 "STR:100%"
  SendMessage $ST_UN_UNINSTALLING_LABEL ${WM_SETTEXT} 0 "STR:卸载完成"
FunctionEnd

; ---------------------------------------------------------------------------
; 页 3: 卸载完成(MUI_UNPAGE_FINISH 自定义, 不能用 nsDialogs, 全部原生 CreateWindowEx)
; ---------------------------------------------------------------------------
Function un.ST_UnPageFinish_Show
  Call un.ST_StopManagedChromeInteraction

  ; 销毁卸载中页的原生控件(避免残影覆盖完成页)
  !insertmacro ST_RawDestroy $ST_UN_UNINSTALLING_PROGRESS
  !insertmacro ST_RawDestroy $ST_UN_UNINSTALLING_PERCENT
  !insertmacro ST_RawDestroy $ST_UN_UNINSTALLING_LABEL
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

  Call un.ST_SetupWindow

  ; finish 页隐藏"上一步"(3)/"取消"(2), 保留"完成"(1)
  GetDlgItem $1 $HWNDPARENT 3
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 2
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 隐藏 MUI 默认标题/描述($HWNDPARENT 的 1037/1038)
  GetDlgItem $1 $HWNDPARENT 1037
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}
  GetDlgItem $1 $HWNDPARENT 1038
  ${If} $1 != 0
    ShowWindow $1 ${SW_HIDE}
  ${EndIf}

  ; 遍历所有 inner #32770: 隐藏 instfiles 残留(1004/1006/1016/1027) + finish 默认内容(1200/1201/1202)
  FindWindow $2 "#32770" "" $HWNDPARENT
  ${Do}
    ${If} $2 == 0
      ${ExitDo}
    ${EndIf}
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
    System::Call 'user32::FindWindowEx(i $HWNDPARENT, i r2, t "#32770", i 0) i .r2'
  ${Loop}

  ; 画自定义 chrome(卸载器深色主题)
  StrCpy $0 $HWNDPARENT
  StrCpy $ST_CURRENT_PAGE ${UNSTEP_FINISH}
  !insertmacro ST_InstFilesChrome $0 ${BGR_SIDEBAR_BG_DARK} ${BGR_SIDEBAR_BG_DARK} "卸载完成" " "
  !insertmacro ST_InstStepItem $0 240 0 ${UNSTEP_FINISH} "✓" "确认卸载" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}
  !insertmacro ST_InstStepItem $0 280 1 ${UNSTEP_FINISH} "✓" "卸载中" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}
  !insertmacro ST_InstStepItem $0 320 2 ${UNSTEP_FINISH} "✓" "完成" ${BGR_DANGER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SIDEBAR_BG_DARK}

  ; 大号成功图标(绿色圆形底 + 白色 ✓)
  !insertmacro ST_Scale $ST_S0 272px
  !insertmacro ST_Scale $ST_S1 110px
  !insertmacro ST_Scale $ST_S2 64px
  !insertmacro ST_RawStaticFont $0 272 110 64 64 "✓" ${SS_CENTER} ${BGR_TEXT_ON_ACCENT_DEF} ${BGR_SUCCESS} $ST_FONT_DISPLAY $3
  !insertmacro ST_RoundRect $3 $ST_S2 $ST_S2 32

  ; 标题 + 副标题
  !insertmacro ST_RawStaticFont $0 272 196 480 28 "卸载完成" 0 ${BGR_TEXT_PRIMARY_DEF} 0x00ffffff $ST_FONT_TITLE $1
  !insertmacro ST_RawStaticFont $0 272 232 480 20 "Score Trans 已从您的计算机中移除" 0 ${BGR_TEXT_SECONDARY_DEF} 0x00ffffff $ST_FONT_SUBTITLE $2

  ; 美化 MUI 完成按钮(ID=1): 移到内容区右下角 (684, 460)
  GetDlgItem $4 $HWNDPARENT 1
  ${If} $4 != 0
    !insertmacro ST_Scale $ST_S0 684px
    !insertmacro ST_Scale $ST_S1 460px
    !insertmacro ST_Scale $ST_S2 100px
    !insertmacro ST_Scale $ST_S3 40px
    System::Call 'user32::SetWindowPos(i r4, i 0, i $ST_S0, i $ST_S1, i $ST_S2, i $ST_S3, i ${SWP_NOZORDER})'
    SetCtlColors $4 "0x${COLOR_TEXT_ON_ACCENT}" "0x${COLOR_ACCENT}"
    SendMessage $4 ${WM_SETFONT} $ST_FONT_BTN 1
    ShowWindow $4 ${SW_SHOW}
  ${EndIf}
  Call un.ST_StartManagedChromeInteraction
FunctionEnd
