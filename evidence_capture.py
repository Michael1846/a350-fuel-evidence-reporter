# SPDX-License-Identifier: AGPL-3.0-only
"""On-demand, user-triggered image capture and a time-correlated SimConnect snapshot.

Screenshots are only taken after a local UI action or explicitly registered Windows
hotkey. No automatic or periodic screen capture.
"""
import datetime as dt
import io
import math
import os
import time
from PIL import ImageGrab
from screen_target import locate_msfs_monitor, get_manual_monitor

BASIC_FIELDS = ('lat','lon','altitude_ft','groundspeed_kt','ias_kt','tas_kt',
                'vertical_speed_fpm','fob_kg','ff1_kg_h','ff2_kg_h','ff_total_kg_h',
                'wind_from_deg','wind_speed_kt','mach','on_ground','engine1_n1_pct','engine2_n1_pct','ff1_source','ff2_source',
                'engine1_antiice','engine2_antiice','engine1_antiice_source','engine2_antiice_source')

def utc_ms(now=None):
    return dt.datetime.fromtimestamp(time.time() if now is None else now, dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')

def freeze_sim_context(status, trigger_time=None, max_age=5.0):
    """Never mislabel stale data as an exact screenshot-position fix.

    trigger_time is the instant the user initiated capture, not when the file
    finished writing. Values are the most recent SimConnect poll, up to 2.5s old.
    """
    triggered = time.time() if trigger_time is None else float(trigger_time)
    received = status.get('timestamp')
    connected = status.get('state')=='connected'
    age = max(0.0,triggered-float(received)) if received is not None else None
    fresh = bool(connected and age is not None and age <= max_age)
    data=status.get('data') or {}
    values = {name:(data.get(name) if fresh else None) for name in BASIC_FIELDS}
    valid_position = all(isinstance(values.get(k),(int,float)) and math.isfinite(values[k]) for k in ('lat','lon'))
    return {
        'event_time_utc':utc_ms(triggered),
        'telemetry_time_utc':utc_ms(received) if received is not None and fresh else None,
        'telemetry_age_seconds':round(age,3) if age is not None else None,
        'context_status': 'fresh_simconnect' if fresh and valid_position else ('no_position' if fresh else 'unavailable_or_stale'),
        'context_source': 'SimConnect last polled data; not a simultaneous GPS fix' if fresh else 'No valid synchronized SimConnect position',
        'flight_status':status.get('flight_status') if fresh else None,
        'aircraft_title':(status.get('identity') or {}).get('title',''),
        **values,
    }

def grab_screen(mode='msfs_monitor'):
    """Capture current screen/window on Windows without changing MSFS focus.

    Modes: msfs_monitor (auto-detected MSFS display), foreground, primary, all. Under
    exclusive fullscreen some GPU content may render black; user can upload
    a manually captured picture in that case.
    """
    if os.name!='nt':
        raise RuntimeError('Direct screen capture is available on Windows only. Screenshots can be uploaded manually.')
    if mode not in ('msfs_monitor','foreground','primary','all') and not mode.startswith('display:'):
        raise ValueError('Unknown capture mode')
    target=None
    if mode=='msfs_monitor':
        # Fail closed: never silently capture the browser/primary monitor.
        target=locate_msfs_monitor()
        im=ImageGrab.grab(bbox=tuple(target['bounds']),all_screens=True)
    elif mode.startswith('display:'):
        monitor=get_manual_monitor(mode[len('display:'):])
        target={'monitor':monitor['device'],'bounds':monitor['bounds'],
                'primary':monitor['primary'],'method':'manual monitor selection'}
        im=ImageGrab.grab(bbox=tuple(monitor['bounds']),all_screens=True)
    elif mode=='foreground':
        import ctypes
        from ctypes import wintypes
        user32=ctypes.windll.user32
        hwnd=user32.GetForegroundWindow()
        if not hwnd:raise RuntimeError('No active window detected')
        rect=wintypes.RECT()
        if not user32.GetWindowRect(hwnd,ctypes.byref(rect)):
            raise RuntimeError('Unable to determine active window position')
        if rect.right <= rect.left or rect.bottom <= rect.top:
            raise RuntimeError('Invalid window dimensions')
        im=ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom),all_screens=True)
    else:
        im=ImageGrab.grab(all_screens=(mode=='all'))
    if im.width<=0 or im.height<=0:raise RuntimeError('Empty screenshot')
    stream=io.BytesIO();im.convert('RGB').save(stream,format='PNG',optimize=False)
    return stream.getvalue(), (im.width,im.height), (target or {'method':'manual','capture_mode':mode})

class GlobalCaptureHotkey:
    """Win32 RegisterHotKey handler, Ctrl+Shift+F10, no additional package."""
    def __init__(self,callback):
        self.callback=callback
        self.registered=False
        self.error='Not started'
        self.thread=None

    def start(self):
        if os.name!='nt':
            self.error='Windows only';return
        import threading
        self.thread=threading.Thread(target=self._run,daemon=True,name='A350ScreenshotHotkey')
        self.thread.start()

    def _run(self):
        import ctypes
        from ctypes import wintypes
        user32=ctypes.windll.user32
        hotkey_id=0xA350
        mod_control_shift_norepeat=0x0002|0x0004|0x4000
        vk_f10=0x79
        if not user32.RegisterHotKey(None,hotkey_id,mod_control_shift_norepeat,vk_f10):
            self.error='Shortcut could not be registered (potential conflict)';return
        self.registered=True;self.error=''
        try:
            msg=wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==0x0312 and msg.wParam==hotkey_id:
                    try:self.callback()
                    except Exception as e:self.error=str(e)[:240]
        finally:
            self.registered=False
            user32.UnregisterHotKey(None,hotkey_id)
