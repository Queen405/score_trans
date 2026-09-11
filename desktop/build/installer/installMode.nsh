; ============================================================================
; Score Trans Installer - Install Mode Initialization
; 复制自 electron-builder 的 assistedInstaller.nsh,避免引入 MUI_PAGE_* 定义
; ============================================================================

; 依赖:
;   multiUser.nsh    (提供 setInstallModePerUser / setInstallModePerAllUsers)
;   UAC.nsh          (multiUser.nsh 已 include)
;   StdUtils.nsh     (setInstallModePerUser 内部使用 ${StdUtils.GetParameter})

!include "StdUtils.nsh"

!ifndef MULTIUSER_INIT_TEXT_ADMINREQUIRED
  !define MULTIUSER_INIT_TEXT_ADMINREQUIRED "$(^Caption) requires administrator privileges."
!endif
!ifndef MULTIUSER_INIT_TEXT_POWERREQUIRED
  !define MULTIUSER_INIT_TEXT_POWERREQUIRED "$(^Caption) requires at least Power User privileges."
!endif
!ifndef MULTIUSER_INIT_TEXT_ALLUSERSNOTPOSSIBLE
  !define MULTIUSER_INIT_TEXT_ALLUSERSNOTPOSSIBLE "Your user account does not have sufficient privileges to install $(^Name) for all users of this computer."
!endif

!macro initMultiUser
  !ifdef INSTALL_MODE_PER_ALL_USERS
    !insertmacro setInstallModePerAllUsers
  !else
    ${If} ${UAC_IsInnerInstance}
    ${AndIfNot} ${UAC_IsAdmin}
      ; 内层进程且非管理员:让外层知道我们没有管理员权限
      SetErrorLevel 0x666666
      Quit
    ${endIf}

    ; 检查注册表,判断是否有 per-machine / per-user 历史安装
    StrCpy $hasPerMachineInstallation "0"
    StrCpy $hasPerUserInstallation "0"

    ReadRegStr $perMachineInstallationFolder HKLM "${INSTALL_REGISTRY_KEY}" InstallLocation
    ${if} $perMachineInstallationFolder != ""
      StrCpy $hasPerMachineInstallation "1"
    ${endif}

    ReadRegStr $perUserInstallationFolder HKCU "${INSTALL_REGISTRY_KEY}" InstallLocation
    ${if} $perUserInstallationFolder != ""
      StrCpy $hasPerUserInstallation "1"
    ${endif}

    ; 命令行开关 /allusers /currentuser
    ${GetParameters} $R0
    ${GetOptions} $R0 "/allusers" $R1
    ${IfNot} ${Errors}
      StrCpy $hasPerMachineInstallation "1"
      StrCpy $hasPerUserInstallation "0"
    ${EndIf}

    ${GetOptions} $R0 "/currentuser" $R1
    ${IfNot} ${Errors}
      StrCpy $hasPerMachineInstallation "0"
      StrCpy $hasPerUserInstallation "1"
    ${EndIf}

    ; 根据历史安装决定默认模式
    ${if} $hasPerUserInstallation == "1"
    ${andif} $hasPerMachineInstallation == "0"
      !insertmacro setInstallModePerUser
    ${elseif} $hasPerUserInstallation == "0"
      ${andif} $hasPerMachineInstallation == "1"
      !insertmacro setInstallModePerAllUsers
    ${else}
      ; 首次安装或两者都有:默认 per-user
      !ifdef INSTALL_MODE_PER_ALL_USERS
        !insertmacro setInstallModePerAllUsers
      !else
        !ifdef INSTALL_MODE_PER_ALL_USERS_DEFAULT
          !insertmacro setInstallModePerAllUsers
        !else
          !insertmacro setInstallModePerUser
        !endif
      !endif
    ${endif}
  !endif
!macroend
