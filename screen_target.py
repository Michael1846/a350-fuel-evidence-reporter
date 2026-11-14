# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only Win32 discovery of the monitor occupied by the MSFS game window.

No focus changes, window activation, synthetic keystrokes, or display reconfiguration.
Fail closed if the simulator is absent/minimized/ambiguous: never silently grab
some other application. MonitorFromWindow selects maximum window overlap.
"""
import ctypes
import os
import re
from ctypes import wintypes

KNOWN_EXECUTABLES = {
    'flightsimulator.exe',
    'flightsimulator2024.exe',
    'microsoftflightsimulator.exe',
    'microsoftflightsimulator2024.exe',
}
TITLE_PATTERN = re.compile(r'^(?:microsoft\s+)?flight\s+simulator(?:\s+2024)?$', re.IGNORECASE)


class ScreenTargetError(RuntimeError):
    """Cannot safely determine which display to capture."""


def select_sim_window(windows):
    """Pure selection function: reject small/hidden windows and ambiguous matches."""
    candidates=[]
    for w in windows:
        bounds=w.get('window_bounds') or []
        if len(bounds)!=4:
            continue
        x0,y0,x1,y1=bounds
        width,height=x1-x0,y1-y0
        if not w.get('visible') or w.get('minimized') or width<640 or height<360:
            continue
        name=str(w.get('process_name','')).lower()
        title=str(w.get('title','')).strip()
        exe_match=name in KNOWN_EXECUTABLES
        title_match=bool(TITLE_PATTERN.fullmatch(title))
        # An explicitly known *non*-simulator executable must never be
        # accepted just because its window title resembles the game.
        if name and not exe_match:
            continue
        if not (exe_match or title_match):
            continue
        # A positive exe identity is strongest; exact MSFS title is secondary.
        score=(2 if exe_match else 0)+(1 if title_match else 0)
        candidates.append((score,width*height,w))
    if not candidates:
        raise ScreenTargetError('MSFS window not found or minimized. Keep the simulator visible, or select a manual capture mode.')
    candidates.sort(key=lambda r:(r[0],r[1]),reverse=True)
    best=candidates[0]
    if len(candidates)>1:
        second=candidates[1]
        if best[0]==second[0] and second[1]>=best[1]*0.95 and best[2].get('pid')!=second[2].get('pid'):
            raise ScreenTargetError('Multiple equally plausible MSFS windows detected. Close the duplicate or use a manual capture mode.')
    return best[2]


def _win32_windows():
    user32=ctypes.windll.user32
    kernel32=ctypes.windll.kernel32
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user32.EnumWindows.restype=wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype=wintypes.DWORD
    user32.GetWindowTextLengthW.argtypes=[wintypes.HWND]
    user32.GetWindowTextLengthW.restype=ctypes.c_int
    user32.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user32.GetWindowTextW.restype=ctypes.c_int
    user32.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype=wintypes.BOOL
    kernel32.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel32.OpenProcess.restype=wintypes.HANDLE
    kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel32.CloseHandle.restype=wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype=wintypes.BOOL
    cache={}
    rows=[]
    def process_name(pid):
        if pid in cache:return cache[pid]
        handle=kernel32.OpenProcess(0x1000,False,pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        name=''
        if handle:
            try:
                path=ctypes.create_unicode_buffer(32768)
                n=wintypes.DWORD(len(path))
                if kernel32.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(n)):
                    name=path.value.replace('/','\\').split('\\')[-1]
            finally:kernel32.CloseHandle(handle)
        cache[pid]=name
        return name
    def callback(hwnd,_):
        if not user32.IsWindowVisible(hwnd):return True
        if user32.IsIconic(hwnd):return True
        rect=wintypes.RECT()
        if not user32.GetWindowRect(hwnd,ctypes.byref(rect)):return True
        pid=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        size=user32.GetWindowTextLengthW(hwnd)
        title=''
        if size:
            buf=ctypes.create_unicode_buffer(size+1)
            user32.GetWindowTextW(hwnd,buf,size+1)
            title=buf.value
        rows.append({'hwnd':int(hwnd),'pid':pid.value,'title':title,'process_name':process_name(pid.value),
                     'window_bounds':[rect.left,rect.top,rect.right,rect.bottom],
                     'visible':True,'minimized':False})
        return True
    callback_ref=callback_type(callback)
    if not user32.EnumWindows(callback_ref,0):
        raise ScreenTargetError('Windows did not provide a readable list of open windows.')
    return rows


class MONITORINFOEXW(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),
              ('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD),
              ('szDevice',wintypes.WCHAR*32)]


def _read_monitor_info(handle):
    user32=ctypes.windll.user32
    info=MONITORINFOEXW()
    info.cbSize=ctypes.sizeof(info)
    user32.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFOEXW)]
    user32.GetMonitorInfoW.restype=wintypes.BOOL
    if not user32.GetMonitorInfoW(handle,ctypes.byref(info)):
        raise ScreenTargetError('Windows could not identify the monitor occupied by MSFS.')
    r=info.rcMonitor
    if r.right<=r.left or r.bottom<=r.top:
        raise ScreenTargetError('Windows returned invalid MSFS display bounds.')
    return {'device':info.szDevice,'bounds':[r.left,r.top,r.right,r.bottom],
            'primary':bool(info.dwFlags&1)}


def _monitor_for_window(hwnd):
    user32=ctypes.windll.user32
    user32.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD]
    user32.MonitorFromWindow.restype=wintypes.HANDLE
    handle=user32.MonitorFromWindow(hwnd,0)  # MONITOR_DEFAULTTONULL
    if not handle:raise ScreenTargetError('MSFS window is not on an active monitor.')
    return _read_monitor_info(handle)


def list_monitors():
    """Expose available monitors for an explicit, opt-in manual fallback."""
    if os.name!='nt':return []
    user32=ctypes.windll.user32
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    user32.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.POINTER(wintypes.RECT),callback_type,wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype=wintypes.BOOL
    results=[]
    def callback(monitor,dc,rect,param):
        info=_read_monitor_info(monitor)
        left,top,right,bottom=info['bounds']
        results.append({**info,'width':right-left,'height':bottom-top})
        return True
    cb=callback_type(callback)
    if not user32.EnumDisplayMonitors(None,None,cb,0):
        raise ScreenTargetError('Windows could not enumerate available monitors.')
    return sorted(results,key=lambda v:(not v['primary'],v['bounds'][0],v['bounds'][1]))


def get_manual_monitor(device):
    """Only accept display names returned by the current Windows enumeration."""
    for monitor in list_monitors():
        if monitor['device']==device:return monitor
    raise ScreenTargetError('The selected monitor is disconnected or unavailable. Refresh the display list.')


def locate_msfs_monitor():
    """Details for UI and screenshots; monitors are reevaluated each capture."""
    if os.name!='nt':raise ScreenTargetError('Automatic MSFS monitor detection requires Windows.')
    window=select_sim_window(_win32_windows())
    monitor=_monitor_for_window(window['hwnd'])
    left,top,right,bottom=monitor['bounds']
    return {'detected':True,'window_title':window['title'],
            'process_name':window['process_name'],'pid':window['pid'],
            'monitor':monitor['device'],'primary':monitor['primary'],
            'bounds':monitor['bounds'],'width':right-left,'height':bottom-top,
            'window_bounds':window['window_bounds'],
            'method':'Win32 MonitorFromWindow; largest MSFS window overlap'}


def target_status():
    try:result=locate_msfs_monitor()
    except (ScreenTargetError,OSError,AttributeError) as exc:
        result={'detected':False,'error':str(exc)}
    try:result['monitors']=list_monitors()
    except (ScreenTargetError,OSError,AttributeError) as exc:
        result['monitors']=[]
        result['monitor_error']=str(exc)
    return result
