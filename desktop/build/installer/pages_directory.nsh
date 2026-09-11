; ============================================================================
; Score Trans Installer - 页面 2: 安装位置(含安装模式单选)
; ============================================================================

Var ST_DIR_DIALOG
Var ST_DIR_EDIT              ; 路径输入框
Var ST_DIR_RADIO_USER        ; "仅为我安装"
Var ST_DIR_RADIO_MACHINE     ; "为所有用户安装"
Var ST_DIR_BTN_NEXT
Var ST_DIR_BTN_BACK
Var ST_DIR_LABEL_SPACE       ; 磁盘空间提示

Function ST_PageDirectory_Show
  nsDialogs::Create 1018
  Pop $ST_DIR_DIALOG
  ${If} $ST_DIR_DIALOG == error
    Abort
  ${EndIf}
  System::Call 'user32::GetParent(i $ST_DIR_DIALOG) i .s'
  Pop $ST_OUTER_HWND

  Call ST_SetupWindow

  StrCpy $ST_CURRENT_PAGE ${STEP_DIRECTORY}

  Call ST_CreateTitleBar
  Push $ST_CURRENT_PAGE
  Call ST_CreateSidebar

  ; 标题
  !insertmacro ST_CreateTitle 272px 70px 480px "选择安装位置" $0

  ; 副标题
  !insertmacro ST_CreateSubtitle 272px 106px 480px "选择为谁安装以及安装到哪里" $1

  ; ----- 安装模式单选 -----
  !insertmacro ST_CreateSmall 272px 150px 480px 18px "为谁安装?" $2

  ; 仅为我安装
  !insertmacro ST_CreateOptionLabel 272px 176px 360px "○ 仅为我安装(推荐)" $ST_DIR_RADIO_USER
  ${NSD_OnClick} $ST_DIR_RADIO_USER ST_PageDirectory_SelectUser

  ; 为所有用户安装
  !insertmacro ST_CreateOptionLabel 272px 200px 420px "○ 为所有用户安装(需要管理员)" $ST_DIR_RADIO_MACHINE
  ${NSD_OnClick} $ST_DIR_RADIO_MACHINE ST_PageDirectory_SelectMachine

  ; ----- 安装路径 -----
  !insertmacro ST_CreateSmall 272px 240px 480px 18px "安装到:" $3

  ; 路径字段(点击可浏览)
  ; 初始值直接用 $INSTDIR: initMultiUser 已按"历史安装目录 > 默认目录 > /D 参数"设置好,
  ; 覆盖安装(自动更新)时会自动填入上次安装的目录, 用户无需重新选择
  !insertmacro ST_CreatePathField 272px 262px 388px "$INSTDIR" $ST_DIR_EDIT
  ${NSD_OnClick} $ST_DIR_EDIT ST_PageDirectory_OnBrowse
  System::Call 'user32::SetWindowText(i $ST_DIR_EDIT, t "$INSTDIR")'

  ; 根据当前 installMode 默认选中
  ${If} $installMode == "all"
    Call ST_PageDirectory_SelectMachine
  ${Else}
    Call ST_PageDirectory_SelectUser
  ${EndIf}

  ; 浏览按钮
  !insertmacro ST_CreateSecondaryButton 668px 262px 116px 28px "浏览..." $4
  ${NSD_OnClick} $4 ST_PageDirectory_OnBrowse

  ; 磁盘空间提示
  !insertmacro ST_CreateTiny 272px 296px 480px 20px "需要空间约 250 MB" $ST_DIR_LABEL_SPACE

  ; ----- 按钮 -----
  !insertmacro ST_CreateSecondaryButton 272px 460px 88px 40px "上一步" $ST_DIR_BTN_BACK
  ${NSD_OnClick} $ST_DIR_BTN_BACK ST_PageDirectory_OnBack

  !insertmacro ST_CreatePrimaryButton 684px 460px 100px 40px "安装" $ST_DIR_BTN_NEXT
  ${NSD_OnClick} $ST_DIR_BTN_NEXT ST_PageDirectory_OnNext

  !insertmacro ST_CreateSecondaryButton 588px 460px 88px 40px "取消" $5
  ${NSD_OnClick} $5 ST_OnCloseClick

  ${NSD_CreateTimer} ST_ApplyWindowLayout 250
  nsDialogs::Show
FunctionEnd

Function ST_PageDirectory_Leave
  ; 读取路径
  System::Call 'user32::GetWindowText(i $ST_DIR_EDIT, t .r0, i 1024)'
  ; 空路径校验: 为空则留在本页并提示
  ${If} $0 == ""
    MessageBox MB_OK|MB_ICONEXCLAMATION "请选择有效的安装目录"
    Abort
  ${EndIf}
  StrCpy $INSTDIR $0
FunctionEnd

Function ST_PageDirectory_SelectUser
  StrCpy $ST_INSTALL_MODE_RADIO "0"
  !insertmacro setInstallModePerUser
  System::Call 'user32::SetWindowText(i $ST_DIR_RADIO_USER, t "● 仅为我安装(推荐)")'
  System::Call 'user32::SetWindowText(i $ST_DIR_RADIO_MACHINE, t "○ 为所有用户安装(需要管理员)")'
  ; setInstallModePerUser 已按"历史目录 > 默认目录 > /D 参数"更新 $INSTDIR
  System::Call 'user32::SetWindowText(i $ST_DIR_EDIT, t "$INSTDIR")'
FunctionEnd

Function ST_PageDirectory_SelectMachine
  StrCpy $ST_INSTALL_MODE_RADIO "1"
  !insertmacro setInstallModePerAllUsers
  System::Call 'user32::SetWindowText(i $ST_DIR_RADIO_USER, t "○ 仅为我安装(推荐)")'
  System::Call 'user32::SetWindowText(i $ST_DIR_RADIO_MACHINE, t "● 为所有用户安装(需要管理员)")'
  ; setInstallModePerAllUsers 已按"历史目录 > 默认目录 > /D 参数"更新 $INSTDIR
  System::Call 'user32::SetWindowText(i $ST_DIR_EDIT, t "$INSTDIR")'
FunctionEnd

Function ST_PageDirectory_OnBrowse
  ; 弹出目录选择对话框
  nsDialogs::SelectFolderDialog "选择安装目录" "$INSTDIR"
  Pop $0
  ${If} $0 != error
    System::Call 'user32::SetWindowText(i $ST_DIR_EDIT, t "$0")'
  ${EndIf}
FunctionEnd

Function ST_PageDirectory_OnBack
  Call ST_GoBack
FunctionEnd

Function ST_PageDirectory_OnNext
  Call ST_GoNext
FunctionEnd
