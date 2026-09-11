; ============================================================================
; Score Trans Installer - Main Script
; 自定义 NSIS 安装器,完全替换 electron-builder 默认的 MUI2 wizard
;
; 重要:使用自定义 nsis.script 时,electron-builder 不会走两阶段编译
; (即不会先单独编译 uninstaller 再嵌入),也不定义 BUILD_UNINSTALLER。
; 因此本脚本采用 NSIS 标准模式:
;   - 在 Section "install" 里用 WriteUninstaller 把卸载器写到 $INSTDIR
;   - 卸载器页面用 UninstPage custom 无条件定义
;   - 所有 un.* 函数会被 makensis 自动打包进卸载器
; ============================================================================

Unicode true
ManifestDPIAwareness PerMonitorV2
ManifestSupportedOS Win10

; ---------------------------------------------------------------------------
; 基础设置(common.nsh 已定义 Name / BrandingText / APP_EXECUTABLE_FILENAME)
; 注意: OutFile 由 electron-builder 通过 -X 命令传入, 此处不要重复定义
; ---------------------------------------------------------------------------
InstallDir "$LOCALAPPDATA\Programs\${PRODUCT_FILENAME}"

; ---------------------------------------------------------------------------
; 全局变量(必须先于页面文件声明)
; ---------------------------------------------------------------------------
Var newStartMenuLink
Var oldStartMenuLink
Var newDesktopLink
Var oldDesktopLink
Var oldShortcutName
Var oldMenuDirectory

Var ST_DIR_PER_USER
Var ST_DIR_PER_MACHINE
Var ST_INSTALL_MODE_RADIO
Var ST_DELETE_USER_DATA

Var appExe
Var launchLink
Var keepShortcuts

; ---------------------------------------------------------------------------
; 包含 electron-builder 公共逻辑
; ---------------------------------------------------------------------------
!include "x64.nsh"
!include "WinVer.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"
!include "FileFunc.nsh"
!include "MUI2.nsh"

!include "common.nsh"
!include "multiUser.nsh"
!include "allowOnlyOneInstallerInstance.nsh"
!include "installUtil.nsh"
!include "installer.nsh"

; installMode 初始化(自定义版本,替代 assistedInstaller.nsh 的 initMultiUser)
!include "${BUILD_RESOURCES_DIR}\installer\installMode.nsh"

; 主题与 UI
!include "${BUILD_RESOURCES_DIR}\installer\theme.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\ui.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\sidebar.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\pages_welcome.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\pages_directory.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\pages_installing.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\pages_finish.nsh"
!include "${BUILD_RESOURCES_DIR}\installer\uninstaller.nsh"

; ---------------------------------------------------------------------------
; 执行级别
; ---------------------------------------------------------------------------
!ifdef INSTALL_MODE_PER_ALL_USERS
  RequestExecutionLevel admin
!else
  RequestExecutionLevel user
!endif

; ---------------------------------------------------------------------------
; MUI 自定义注入点(必须在 MUI_LANGUAGE 之前定义)
; MUI 框架会在自己的 .onGUIInit 里调用这些函数
; 注意: MUI 不提供 GUIEND 注入点, 字体/画刷资源由进程退出时 Windows 自动回收
; ---------------------------------------------------------------------------
!define MUI_CUSTOMFUNCTION_GUIINIT ST_OnGUIInit
!define MUI_CUSTOMFUNCTION_UNGUIINIT un.ST_OnGUIInit

; ---------------------------------------------------------------------------
; 页面定义
; 注意: 安装/卸载中页必须用 instfiles 框架(MUI_PAGE_INSTFILES / MUI_UNPAGE_INSTFILES),
;       否则 Section 不会执行
; ---------------------------------------------------------------------------
Page custom ST_PageWelcome_Show ST_PageWelcome_Leave
Page custom ST_PageDirectory_Show ST_PageDirectory_Leave

!define MUI_PAGE_CUSTOMFUNCTION_PRE ST_Installing_Pre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ST_Installing_Show
!insertmacro MUI_PAGE_INSTFILES

; ---------------------------------------------------------------------------
; 完成页: 改用 MUI_PAGE_FINISH(MUI 托管页)。
; 关键原因: MUI_PAGE_INSTFILES 完成后只会自动推进到 MUI 托管的 finish 页,
;           不会自动进入 Page custom(实测 NSIS 3.0.4 卡死等点击"下一步", 而该按钮被隐藏)。
; 先清掉 install 页的 PRE/SHOW 定义避免串扰, 再定义 finish 页自己的回调。
; ---------------------------------------------------------------------------
!ifdef MUI_PAGE_CUSTOMFUNCTION_PRE
  !undef MUI_PAGE_CUSTOMFUNCTION_PRE
!endif
!ifdef MUI_PAGE_CUSTOMFUNCTION_SHOW
  !undef MUI_PAGE_CUSTOMFUNCTION_SHOW
!endif
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ST_PageFinish_Show
!insertmacro MUI_PAGE_FINISH

!if "${BUILD_UNINSTALLER}" == ""
  ; 安装器编译时：UninstPage 的 leave 回调会导致 warning 6010，暂不引用
  UninstPage custom un.ST_UnPageWelcome_Show
!else
  ; 卸载器编译时：完整引用两个回调
  UninstPage custom un.ST_UnPageWelcome_Show un.ST_UnPageWelcome_Leave
!endif

!define MUI_PAGE_CUSTOMFUNCTION_PRE un.ST_UnInstalling_Pre
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ST_UnInstalling_Show
!insertmacro MUI_UNPAGE_INSTFILES

; 卸载完成页: 改用 MUI_UNPAGE_FINISH(MUI 托管, 卸载完成后自动推进, 避免 Page custom 卡死)
!ifdef MUI_PAGE_CUSTOMFUNCTION_PRE
  !undef MUI_PAGE_CUSTOMFUNCTION_PRE
!endif
!ifdef MUI_PAGE_CUSTOMFUNCTION_SHOW
  !undef MUI_PAGE_CUSTOMFUNCTION_SHOW
!endif
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ST_UnPageFinish_Show
!insertmacro MUI_UNPAGE_FINISH

; ---------------------------------------------------------------------------
; 安装器 .onInit
; ---------------------------------------------------------------------------
Function .onInit
  Call setInstallSectionSpaceRequired

  ; 释放真实 Logo 图标供标题栏/侧边栏/欢迎页使用
  InitPluginsDir
  File /oname=$PLUGINSDIR\logo.ico "${BUILD_RESOURCES_DIR}\icon.ico"

  SetOutPath $INSTDIR
  ${LogSet} on

  !insertmacro check64BitAndSetRegView
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONEXCLAMATION "Score Trans 需要 Windows 10 或更高版本"
    Quit
  ${EndIf}

  ${IfNot} ${UAC_IsInnerInstance}
    !insertmacro ALLOW_ONLY_ONE_INSTALLER_INSTANCE
  ${EndIf}

  !insertmacro initMultiUser

  StrCpy $ST_DIR_PER_USER "$LOCALAPPDATA\Programs\${PRODUCT_FILENAME}"
  ${If} ${RunningX64}
    StrCpy $ST_DIR_PER_MACHINE "$PROGRAMFILES64\${PRODUCT_FILENAME}"
  ${Else}
    StrCpy $ST_DIR_PER_MACHINE "$PROGRAMFILES\${PRODUCT_FILENAME}"
  ${EndIf}
  StrCpy $ST_INSTALL_MODE_RADIO "0"

  Call ST_InitFonts
  Call ST_InitBrushes
FunctionEnd

; ---------------------------------------------------------------------------
; 安装器 GUI 定制(由 MUI_CUSTOMFUNCTION_GUIINIT 注入)
; ---------------------------------------------------------------------------
Function ST_OnGUIInit
  StrCpy $ST_HWND $HWNDPARENT
  StrCpy $ST_OUTER_HWND $HWNDPARENT
  StrCpy $ST_IS_UNINSTALLER "0"
  Call ST_SetupWindow
FunctionEnd

; ---------------------------------------------------------------------------
; 安装 Section
; 手动展开 installApplicationFiles,跳过 uninstaller 嵌入行
; (自定义 script 模式下 UNINSTALLER_OUT_FILE 为空,File 命令会失败)
; ---------------------------------------------------------------------------
Section "install" INSTALL_SECTION_ID
  Call ST_Installing_StartInstall

  InitPluginsDir
  SetDetailsPrint none

  StrCpy $appExe "$INSTDIR\${APP_EXECUTABLE_FILENAME}"

  !insertmacro setLinkVars

  ${IfNot} ${UAC_IsInnerInstance}
    !insertmacro CHECK_APP_RUNNING
  ${EndIf}
  Call ST_Installing_UpdateStep1

  ; 卸载旧版本
  StrCpy $keepShortcuts "false"
  !insertMacro setIsTryToKeepShortcuts
  ${If} $isTryToKeepShortcuts == "true"
    ReadRegStr $R1 SHELL_CONTEXT "${INSTALL_REGISTRY_KEY}" KeepShortcuts
    ${If} $R1 == "true"
    ${AndIf} ${FileExists} "$appExe"
      StrCpy $keepShortcuts "true"
    ${EndIf}
  ${EndIf}

  !insertmacro uninstallOldVersion SHELL_CONTEXT
  !insertmacro handleUninstallResult SHELL_CONTEXT
  ${If} $installMode == "all"
    !insertmacro uninstallOldVersion HKEY_CURRENT_USER
    !insertmacro handleUninstallResult HKEY_CURRENT_USER
  ${EndIf}
  Call ST_Installing_UpdateStep2

  SetOutPath $INSTDIR

  ; --- 手动展开 installApplicationFiles 的核心(embedded 分支) ---
  !insertmacro extractEmbeddedAppPackage
  ${If} $installMode == "all"
    SetShellVarContext current
  ${EndIf}
  !insertmacro copyFile "$EXEPATH" "$LOCALAPPDATA\${APP_INSTALLER_STORE_FILE}"
  ${If} $installMode == "all"
  SetShellVarContext all
  ${EndIf}

  ; 直接生成卸载器到 $INSTDIR(替代 File "/oname=..." 嵌入)
  WriteUninstaller "$INSTDIR\${UNINSTALL_FILENAME}"
  Call ST_Installing_UpdateStep3

  !insertmacro registryAddInstallInfo
  !insertmacro addStartMenuLink $keepShortcuts
  !insertmacro addDesktopLink $keepShortcuts
  Call ST_Installing_UpdateStep4

  ${If} ${FileExists} "$newStartMenuLink"
    StrCpy $launchLink "$newStartMenuLink"
  ${Else}
    StrCpy $launchLink "$INSTDIR\${APP_EXECUTABLE_FILENAME}"
  ${EndIf}

  Call ST_Installing_FinishInstall

  ; 静默模式(/S, 自动更新场景)下 Section 完成后立即退出,
  ; 否则进程会在 instfiles 完成后滞留不退(实测 PID 常驻, 阻塞下一次安装的单实例互斥)
  ${If} ${Silent}
    SetErrorLevel 0
    Quit
  ${EndIf}
SectionEnd

Function setInstallSectionSpaceRequired
  !insertmacro setSpaceRequired ${INSTALL_SECTION_ID}
FunctionEnd

; ---------------------------------------------------------------------------
; 卸载器(无条件定义,WriteUninstaller 会让 makensis 打包 un.* 进 uninstaller.exe)
; ---------------------------------------------------------------------------
Function un.onInit
  InitPluginsDir
  File /oname=$PLUGINSDIR\logo.ico "${BUILD_RESOURCES_DIR}\icon.ico"
  SetOutPath $INSTDIR
  ${LogSet} on
  !insertmacro check64BitAndSetRegView
  !insertmacro initMultiUser
  Call un.ST_InitFonts
  Call un.ST_InitBrushes
FunctionEnd

Function un.ST_OnGUIInit
  StrCpy $ST_HWND $HWNDPARENT
  StrCpy $ST_IS_UNINSTALLER "1"
  Call un.ST_SetupWindow
FunctionEnd

Section "un.install"
  !insertmacro setLinkVars

  Call un.ST_UnInstalling_Start

  RMDir /r $INSTDIR
  Call un.ST_UnInstalling_UpdateStep1

  ${IfNot} ${isKeepShortcuts}
    WinShell::UninstAppUserModelId "${APP_ID}"
    WinShell::UninstShortcut "$oldDesktopLink"
    Delete "$oldDesktopLink"
    WinShell::UninstShortcut "$oldStartMenuLink"
    Delete "$oldStartMenuLink"
    ReadRegStr $R1 SHELL_CONTEXT "${INSTALL_REGISTRY_KEY}" MenuDirectory
    ${IfNot} $R1 == ""
      RMDir "$SMPROGRAMS\$R1"
    ${EndIf}
  ${EndIf}

  System::Call 'shell32::SHChangeNotify(i, i, i, i) v (0x08000000, 0, 0, 0)'

  Call un.ST_UnInstalling_UpdateStep2

  ; 删除用户数据(默认勾选,由 ST_UnPageWelcome 复选框控制)
  ${If} $ST_DELETE_USER_DATA == "1"
    ${If} $installMode == "all"
      SetShellVarContext current
    ${EndIf}
    RMDir /r "$APPDATA\${APP_FILENAME}"
    !ifdef APP_PRODUCT_FILENAME
      RMDir /r "$APPDATA\${APP_PRODUCT_FILENAME}"
    !endif
    !ifdef APP_PACKAGE_NAME
      RMDir /r "$APPDATA\${APP_PACKAGE_NAME}"
    !endif
    ${If} $installMode == "all"
      SetShellVarContext all
    ${EndIf}
  ${EndIf}

  DeleteRegKey SHELL_CONTEXT "${UNINSTALL_REGISTRY_KEY}"
  !ifdef UNINSTALL_REGISTRY_KEY_2
    DeleteRegKey SHELL_CONTEXT "${UNINSTALL_REGISTRY_KEY_2}"
  !endif
  DeleteRegKey SHELL_CONTEXT "${INSTALL_REGISTRY_KEY}"

  Call un.ST_UnInstalling_Finish
SectionEnd

; ---------------------------------------------------------------------------
; 中文语言(MUI_LANGUAGE 必须在 MUI_PAGE_* 之后,提供 MUI_TEXT_* 字符串)
; ---------------------------------------------------------------------------
!insertmacro MUI_LANGUAGE "SimpChinese"
