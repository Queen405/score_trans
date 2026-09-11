; ============================================================================
; Score Trans Installer - Sidebar
; 左侧深色侧边栏(240px@100%)+ 顶部 logo + 步骤指示器
; 所有函数以宏实现,展开到安装版(ST_*)和卸载版(un.ST_*)
; 坐标均为 100% 基准设计值, 创建时按 $ST_SCALE 运行时缩放
; ============================================================================

Var ST_SIDEBAR_BG
Var ST_CONTENT_BG
Var ST_SIDEBAR_LOGO
Var ST_SIDEBAR_TITLE
Var ST_SIDEBAR_VERSION

!define ST_STEP_LABEL_0 "欢迎"
!define ST_STEP_LABEL_1 "安装位置"
!define ST_STEP_LABEL_2 "安装中"
!define ST_STEP_LABEL_3 "完成"

!define ST_UNSTEP_LABEL_0 "确认卸载"
!define ST_UNSTEP_LABEL_1 "卸载中"
!define ST_UNSTEP_LABEL_2 "完成"

; ---------------------------------------------------------------------------
; 步骤指示器一项(宏): 圆点 + 标签
; 参数: Y_POS STEP_INDEX CURRENT_STEP LABEL_VAR SIDEBAR_BG_COLOR
; ---------------------------------------------------------------------------
!macro ST_SidebarStepItem Y_POS STEP_INDEX CURRENT_STEP LABEL_TEXT BG_COLOR
  !insertmacro ST_Scale $ST_S0 24
  !insertmacro ST_Scale $ST_S1 ${Y_POS}
  ${If} ${STEP_INDEX} < ${CURRENT_STEP}
    ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S0px $ST_S0px "✓"
  ${Else}
    ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S0px $ST_S0px "●"
  ${EndIf}
  Pop $9
  ${If} ${STEP_INDEX} == ${CURRENT_STEP}
    !insertmacro ST_SetColors $9 "${COLOR_ACCENT}" "${BG_COLOR}"
  ${ElseIf} ${STEP_INDEX} < ${CURRENT_STEP}
    !insertmacro ST_SetColors $9 "${COLOR_SUCCESS}" "${BG_COLOR}"
  ${Else}
    !insertmacro ST_SetColors $9 "${COLOR_TEXT_TERTIARY}" "${BG_COLOR}"
  ${EndIf}
  SendMessage $9 ${WM_SETFONT} $ST_FONT_SM 1

  IntOp $8 ${Y_POS} + 2
  !insertmacro ST_Scale $ST_S1 $8
  !insertmacro ST_Scale $ST_S2 56
  !insertmacro ST_Scale $ST_S3 160
  !insertmacro ST_Scale $ST_S0 20
  ${NSD_CreateLabel} $ST_S2px $ST_S1px $ST_S3px $ST_S0px "${LABEL_TEXT}"
  Pop $9
  ${If} ${STEP_INDEX} == ${CURRENT_STEP}
    !insertmacro ST_SetColors $9 "${COLOR_TEXT_SIDEBAR_ACTIVE}" "${BG_COLOR}"
  ${Else}
    !insertmacro ST_SetColors $9 "${COLOR_TEXT_SIDEBAR}" "${BG_COLOR}"
  ${EndIf}
  SendMessage $9 ${WM_SETFONT} $ST_FONT_STEP 1
!macroend

; ---------------------------------------------------------------------------
; 安装器 sidebar(4 步)
; ---------------------------------------------------------------------------
!macro ST_CreateSidebarImpl CURRENT_STEP
  Push $0
  Push $1

  ; 1. 内容区背景(宽高直接由缩放后的窗口尺寸推出, 避免取整误差留缝)
  !insertmacro ST_Scale $ST_S0 ${SIDEBAR_WIDTH}
  IntOp $ST_S1 $ST_WIN_W - $ST_S0
  IntOp $ST_S2 $ST_WIN_H - $ST_TITLE_H
  ${NSD_CreateLabel} $ST_S0px $ST_TITLE_Hpx $ST_S1px $ST_S2px ""
  Pop $ST_CONTENT_BG
  !insertmacro ST_SetColors $ST_CONTENT_BG "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_BASE}"
  !insertmacro ST_MakeClickThrough $ST_CONTENT_BG

  ; 2. 侧边栏背景
  ${NSD_CreateLabel} 0 $ST_TITLE_Hpx $ST_S0px $ST_S2px ""
  Pop $ST_SIDEBAR_BG
  !insertmacro ST_SetColors $ST_SIDEBAR_BG "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_MakeClickThrough $ST_SIDEBAR_BG

  ; 2. Logo(真实应用图标)
  !insertmacro ST_CreateIcon 24 66 64 $ST_SIDEBAR_LOGO
  !insertmacro ST_SetColors $ST_SIDEBAR_LOGO "${COLOR_SIDEBAR_BG}" "${COLOR_SIDEBAR_BG}"

  ; 3. 标题
  !insertmacro ST_Scale $ST_S1 142
  !insertmacro ST_Scale $ST_S2 192
  !insertmacro ST_Scale $ST_S3 24
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "Score Trans"
  Pop $ST_SIDEBAR_TITLE
  !insertmacro ST_SetColors $ST_SIDEBAR_TITLE "${COLOR_TEXT_SIDEBAR_ACTIVE}" "${COLOR_SIDEBAR_BG}"
  SendMessage $ST_SIDEBAR_TITLE ${WM_SETFONT} $ST_FONT_SIDEBAR_TITLE 1

  ; 4. 版本号
  !insertmacro ST_Scale $ST_S1 170
  !insertmacro ST_Scale $ST_S3 18
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "v${VERSION}"
  Pop $ST_SIDEBAR_VERSION
  !insertmacro ST_SetColors $ST_SIDEBAR_VERSION "${COLOR_TEXT_TERTIARY}" "${COLOR_SIDEBAR_BG}"
  SendMessage $ST_SIDEBAR_VERSION ${WM_SETFONT} $ST_FONT_XS 1

  ; 5. 步骤指示器(4 步)
  !insertmacro ST_SidebarStepItem 240 0 ${CURRENT_STEP} "${ST_STEP_LABEL_0}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_SidebarStepItem 280 1 ${CURRENT_STEP} "${ST_STEP_LABEL_1}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_SidebarStepItem 320 2 ${CURRENT_STEP} "${ST_STEP_LABEL_2}" "${COLOR_SIDEBAR_BG}"
  !insertmacro ST_SidebarStepItem 360 3 ${CURRENT_STEP} "${ST_STEP_LABEL_3}" "${COLOR_SIDEBAR_BG}"

  Pop $1
  Pop $0
!macroend

Function ST_CreateSidebar
  Exch $0
  !insertmacro ST_CreateSidebarImpl $0
FunctionEnd

; ---------------------------------------------------------------------------
; 卸载器 sidebar(3 步,深色 #0e1014)
; ---------------------------------------------------------------------------
!macro ST_CreateUninstallSidebarImpl CURRENT_STEP
  Push $0
  Push $1

  ; 1. 内容区背景
  !insertmacro ST_Scale $ST_S0 ${SIDEBAR_WIDTH}
  IntOp $ST_S1 $ST_WIN_W - $ST_S0
  IntOp $ST_S2 $ST_WIN_H - $ST_TITLE_H
  ${NSD_CreateLabel} $ST_S0px $ST_TITLE_Hpx $ST_S1px $ST_S2px ""
  Pop $ST_CONTENT_BG
  !insertmacro ST_SetColors $ST_CONTENT_BG "${COLOR_TEXT_PRIMARY}" "${COLOR_BG_BASE}"
  !insertmacro ST_MakeClickThrough $ST_CONTENT_BG

  ; 2. 侧边栏背景
  ${NSD_CreateLabel} 0 $ST_TITLE_Hpx $ST_S0px $ST_S2px ""
  Pop $ST_SIDEBAR_BG
  !insertmacro ST_SetColors $ST_SIDEBAR_BG "${COLOR_TEXT_SIDEBAR}" "${COLOR_SIDEBAR_BG_DARK}"
  !insertmacro ST_MakeClickThrough $ST_SIDEBAR_BG

  ; 2. Logo(真实应用图标)
  !insertmacro ST_CreateIcon 24 66 64 $ST_SIDEBAR_LOGO
  !insertmacro ST_SetColors $ST_SIDEBAR_LOGO "${COLOR_SIDEBAR_BG_DARK}" "${COLOR_SIDEBAR_BG_DARK}"

  ; 3. 标题
  !insertmacro ST_Scale $ST_S1 142
  !insertmacro ST_Scale $ST_S2 192
  !insertmacro ST_Scale $ST_S3 24
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "卸载 Score Trans"
  Pop $ST_SIDEBAR_TITLE
  !insertmacro ST_SetColors $ST_SIDEBAR_TITLE "${COLOR_TEXT_SIDEBAR_ACTIVE}" "${COLOR_SIDEBAR_BG_DARK}"
  SendMessage $ST_SIDEBAR_TITLE ${WM_SETFONT} $ST_FONT_SIDEBAR_TITLE 1

  ; 4. 版本号
  !insertmacro ST_Scale $ST_S1 170
  !insertmacro ST_Scale $ST_S3 18
  ${NSD_CreateLabel} $ST_S0px $ST_S1px $ST_S2px $ST_S3px "v${VERSION}"
  Pop $ST_SIDEBAR_VERSION
  !insertmacro ST_SetColors $ST_SIDEBAR_VERSION "${COLOR_TEXT_TERTIARY}" "${COLOR_SIDEBAR_BG_DARK}"
  SendMessage $ST_SIDEBAR_VERSION ${WM_SETFONT} $ST_FONT_XS 1

  ; 5. 步骤指示器(3 步)
  !insertmacro ST_SidebarStepItem 240 0 ${CURRENT_STEP} "${ST_UNSTEP_LABEL_0}" "${COLOR_SIDEBAR_BG_DARK}"
  !insertmacro ST_SidebarStepItem 280 1 ${CURRENT_STEP} "${ST_UNSTEP_LABEL_1}" "${COLOR_SIDEBAR_BG_DARK}"
  !insertmacro ST_SidebarStepItem 320 2 ${CURRENT_STEP} "${ST_UNSTEP_LABEL_2}" "${COLOR_SIDEBAR_BG_DARK}"

  Pop $1
  Pop $0
!macroend

Function un.ST_CreateUninstallSidebar
  Exch $0
  !insertmacro ST_CreateUninstallSidebarImpl $0
FunctionEnd
