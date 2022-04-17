;
; 2022.04.15 - First version
;
;    May you do good and not evil.
;    May you find forgiveness for yourself and forgive others.
;    May you share freely, never taking more than you give.
;
;-------------------------------------------------------------------------
;
; package.nsi -- Set up installer that populates things like this
;                (top level location configurable, include and lib hierarchies not)
; C:\ProgramData\include          (sqlite3.h, sqlite3ext.h)
;               \lib     \Win32   (sqlite3.lib)
;                        \x64            "
;               \bin              (sqlite3-Win32.dll, sqlite3-x64.dll)
;
;-------------------------------------------------------------------------

Name "SQLite3 Windows DLL"
Outfile "sqlite3-for-msvc-setup.exe"
RequestExecutionLevel admin
InstallDir C:\ProgramData

;--------------------------------
;
; 1. License Page

Page license

LicenseText "Please read the following license agreement."
LicenseData "sqlite3-blessing.txt"
LicenseForceSelection checkbox "I accept"

;--------------------------------
;
; 2. Directory Page

Page directory


;--------------------------------
;
; 3. Install files

Page instfiles

;--------------------------------
; Uninstall Pages
;    -- like their install analogs

;--------------------------------
;
; 1. Uninstall confirm

UninstPage uninstConfirm un.AreYouSure

;--------------------------------
;
; 2. Uninstall progress

UninstPage instfiles

; StrContains
; This function does a case sensitive searches for an occurrence of a substring in a string. 
; It returns the substring if it is found. 
; Otherwise it returns null(""). 
; Written by kenglish_hi
; Adapted from StrReplace written by dandaman32
 
 
Var STR_HAYSTACK
Var STR_NEEDLE
Var STR_CONTAINS_VAR_1
Var STR_CONTAINS_VAR_2
Var STR_CONTAINS_VAR_3
Var STR_CONTAINS_VAR_4
Var STR_RETURN_VAR
 
Function StrContains
  Exch $STR_NEEDLE
  Exch 1
  Exch $STR_HAYSTACK
  ; Uncomment to debug
  ;MessageBox MB_OK 'STR_NEEDLE = $STR_NEEDLE STR_HAYSTACK = $STR_HAYSTACK '
    StrCpy $STR_RETURN_VAR ""
    StrCpy $STR_CONTAINS_VAR_1 -1
    StrLen $STR_CONTAINS_VAR_2 $STR_NEEDLE
    StrLen $STR_CONTAINS_VAR_4 $STR_HAYSTACK
    loop:
      IntOp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_1 + 1
      StrCpy $STR_CONTAINS_VAR_3 $STR_HAYSTACK $STR_CONTAINS_VAR_2 $STR_CONTAINS_VAR_1
      StrCmp $STR_CONTAINS_VAR_3 $STR_NEEDLE found
      StrCmp $STR_CONTAINS_VAR_1 $STR_CONTAINS_VAR_4 done
      Goto loop
    found:
      StrCpy $STR_RETURN_VAR $STR_NEEDLE
      Goto done
    done:
   Pop $STR_NEEDLE ;Prevent "invalid opcode" errors and keep the
   Exch $STR_RETURN_VAR  
FunctionEnd
 
!macro _StrContainsConstructor OUT NEEDLE HAYSTACK
  Push `${HAYSTACK}`
  Push `${NEEDLE}`
  Call StrContains
  Pop `${OUT}`
!macroend
 
!define StrContains '!insertmacro "_StrContainsConstructor"'

;--------------------------------
; Function -- uninstall ... are you sure?
; (function name must begin 'un.')

Function un.AreYouSure
  ; set the title of the uninstall window
  MessageBox MB_YESNO \
             "Uninstall SQLite3 headers, import libraries and DLLs?" \
             /SD IDNO IDNO leaveIt
  Return
  leaveIt:
  Quit
FunctionEnd

;================================================================
; Sections - install
;================================================================

Section "Headers and Libraries"
    SetOutPath "$INSTDIR\include"
    File include\*
    SetOutPath "$INSTDIR\lib\Win32"
    File lib\Win32\*
    SetOutPath "$INSTDIR\lib\x64"
    File lib\x64\*
    SetOutPath "$INSTDIR\bin"
    File bin\*

    WriteUninstaller "$INSTDIR\uninstall-sqlite3-for-msvc-setup.exe"
SectionEnd

Section "Add INSTDIR-bin to path"
    StrCpy $R9 "$INSTDIR\bin"
    ReadRegStr $R8 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"

    ; if it's already in the path, leave
    ${StrContains} $0 $R9 $R8
    StrCmp $0 "" 0 done
    ; spaces in path?
    ${StrContains} $1 " " $R9
    ; current value ends in ;?
    StrCpy $2 "$R8" 1 -1

    StrLen $9 $R9
    StrLen $8 $R8

    ; what's the maximum "now" size we could have with still room for a ;
    ; the path and some slop for quote marks if needed...
    IntOp $0 ${NSIS_MAX_STRLEN} - 5
    IntOp $0 $0 - $9
    IntCmp $0 $8 0 tooLong 0

    StrCmp $2 ";" 0 addSemis
    StrCmp $1 "" 0 useQuotes
    StrCpy $R8 "$R8$R9;"
    goto writeReg
useQuotes:
    StrCpy $R8 '$R8"$R9";'
    goto writeReg
addSemis:
    StrCmp $1 "" 0 quotePlusSemi
    StrCpy $R8 "$R8;$R9;"
    goto writeReg
quotePlusSemi:
    StrCpy $R8 '$R8;"$R9";'
    goto writeReg
writeReg:
    WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" $R8
    goto done

tooLong:
    MessageBox MB_OK "The current system path can not be changed on this platform because it's already $8 characters long.$\rCurrent maximum string length is ${NSIS_MAX_STRLEN} and a larger limit can be compiled in.$\rAlternatively, add the value into the path yourself using the Advanced System Settings."

done:
SectionEnd

Function un.isEmptyDir
  # Stack ->                    # Stack: <directory>
  Exch $0                       # Stack: $0
  Push $1                       # Stack: $1, $0
  FindFirst $0 $1 "$0\*.*"
  strcmp $1 "." 0 _notempty
    FindNext $0 $1
    strcmp $1 ".." 0 _notempty
      ClearErrors
      FindNext $0 $1
      IfErrors 0 _notempty
        FindClose $0
        Pop $1                  # Stack: $0
        StrCpy $0 1
        Exch $0                 # Stack: 1 (true)
        goto _end
     _notempty:
       FindClose $0
       ClearErrors
       Pop $1                   # Stack: $0
       StrCpy $0 0
       Exch $0                  # Stack: 0 (false)
  _end:
FunctionEnd

;================================================================
; Sections - uninstall
;================================================================

Section "Uninstall"
    Delete "$INSTDIR\include\sqlite3.h"
    Delete "$INSTDIR\include\sqlite3ext.h"

    Delete "$INSTDIR\lib\Win32\sqlite3.lib"
    Delete "$INSTDIR\lib\x64\sqlite3.lib"

    Delete "$INSTDIR\bin\sqlite3-Win32.dll"
    Delete "$INSTDIR\bin\sqlite3-x64.dll"

    Delete "$INSTDIR\uninstall-sqlite3-for-msvc-setup.exe"
SectionEnd
