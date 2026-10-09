"""Keep Enter from sending while a Windows IME is composing text."""
import ctypes
from ctypes import wintypes
import sys

def ime_composing(widget):
    if sys.platform != 'win32':
        return False
    try:
        imm = ctypes.WinDLL('imm32')
        imm.ImmGetContext.argtypes = [wintypes.HWND]
        imm.ImmGetContext.restype = wintypes.HANDLE
        imm.ImmGetCompositionStringW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        imm.ImmGetCompositionStringW.restype = ctypes.c_long
        imm.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        imm.ImmReleaseContext.restype = wintypes.BOOL
        hwnd = widget.winfo_id()
        context = imm.ImmGetContext(hwnd)
        if not context:
            return False
        try:
            return imm.ImmGetCompositionStringW(context, 8, None, 0) > 0
        finally:
            imm.ImmReleaseContext(hwnd, context)
    except (OSError, AttributeError):
        return False
