; ============================================================================
; Score Trans Installer - 页面 1: 欢迎页
; ============================================================================

Var ST_WELCOME_DIALOG
Var ST_WELCOME_BTN_NEXT

Function ST_PageWelcome_Show
  ; 创建页面对话框(覆盖整个窗口)
  nsDialogs::Create 1018
  Pop $ST_WELCOME_DIALOG
  ${If} $ST_WELCOME_DIALOG == error
    Abort
  ${EndIf}
  System::Call 'user32::GetParent(i $ST_WELCOME_DIALOG) i .s'
  Pop $ST_OUTER_HWND

  Call ST_SetupWindow

  ; 设置当前步骤
  StrCpy $ST_CURRENT_PAGE ${STEP_WELCOME}

  ; 创建标题栏
  Call ST_CreateTitleBar

  ; 创建侧边栏
  Push $ST_CURRENT_PAGE
  Call ST_CreateSidebar

  ; 内容区:x = 240 + 32
  ; Hero: 128px 应用图标
  !insertmacro ST_CreateIcon 272 96 128 $6
  !insertmacro ST_SetColors $6 "${COLOR_BG_BASE}" "${COLOR_BG_BASE}"

  ; 标题
  !insertmacro ST_CreateTitle 272px 248px 480px "欢迎使用 Score Trans" $0

  ; 副标题
  !insertmacro ST_CreateSubtitle 272px 284px 480px "五线谱与简谱互转工具" $1

  ; 描述
  !insertmacro ST_CreateBody 272px 326px 480px 72px "Score Trans 是一款 Windows 桌面应用,用于将五线谱图片/PDF 识别为 MusicXML,并在五线谱与简谱之间自由转换。$\r$\n$\r$\n点击「立即安装」开始,或点击「自定义」调整安装选项。" $2

  ; 版本信息
  !insertmacro ST_CreateTiny 272px 424px 480px 20px "版本 v${VERSION}  ·  Windows 10 及以上" $3

  ; 按钮: [立即安装]  [自定义]
  !insertmacro ST_CreatePrimaryButton 612px 460px 172px 40px "立即安装" $ST_WELCOME_BTN_NEXT
  ${NSD_OnClick} $ST_WELCOME_BTN_NEXT ST_PageWelcome_OnNext

  !insertmacro ST_CreateSecondaryButton 500px 460px 100px 40px "自定义" $4
  ${NSD_OnClick} $4 ST_PageWelcome_OnCustom

  ; 取消按钮(右上角,文字)
  !insertmacro ST_CreateSecondaryButton 272px 460px 88px 40px "取消" $5
  ${NSD_OnClick} $5 ST_OnCloseClick

  ${NSD_CreateTimer} ST_ApplyWindowLayout 250
  nsDialogs::Show
FunctionEnd

Function ST_PageWelcome_Leave
FunctionEnd

Function ST_PageWelcome_OnNext
  Call ST_GoNext
FunctionEnd

Function ST_PageWelcome_OnCustom
  Call ST_GoNext
FunctionEnd
