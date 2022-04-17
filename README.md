# sqlite_msvc_packager
Downloads the latest Windows SQLite3 components and packages them for ease of deployment for Windows development environments.

1. Grabs the [SQLite Download page](https://www.sqlite.org/download.html) and parses the handy `Download product data for scripts to read` section.
2. Grabs the `sqlite-dll-win32-x86`, `sqlite-dll-win64-x64` and `sqlite-amalgamation` zip files.
3. Unpacks the DLL zip files into their own folders; renames the two DLLs from `sqlite3.dll` to `sqlite3-Win32.dll` and `sqlite3-x64.dll`, modifies each `sqlite3.def` file appropriately. with a `LIBRARY ...` line.
4. Runs the Win32 and x64 versions of `lib` on the modifies `sqlite3.def` files.
5. Collects the `sqlite3.h` and `sqlite3ext.h` files, the two DLLs, the 2 lib files for placement in directories of the following structure:
```
C:\ProgramData -+--> bin              : sqlite3-Win32.dll, sqlite3-x64.dll
                +--> include          : sqlite3.h, sqlite3ext.h
                +--> lib -+--> Win32  : sqlite3.lib (implib from mod'd 32-bit def file)
                          +--> x64    : sqlite3.lib (implib from mod'd 64-bit def file)
```
### `.\configure`, `make`, `make install`,  `make package`
The process is orchestrated, with some ability to customize, using batch files that try to find `python3` and then use it to configure and make.

Final placement can be done by running `make install` from a `cmd.exe` with Administrator privilege, or by executing a `makensis` install set produced by `make package`.

The install set comes with an uninstaller, but it also adds the `.\bin` data from the install target (by default `C:\ProgramData\bin`) to the defaut system-wide execution path.

The uninstaller does not delete etiher the `.\bin`, `.\include` or `\lib` directory but it will remove the `Win32` or `x64` directories if they're empty after components are removed.
Also, the uninstaller does not delete `.\bin` from the execution path.
