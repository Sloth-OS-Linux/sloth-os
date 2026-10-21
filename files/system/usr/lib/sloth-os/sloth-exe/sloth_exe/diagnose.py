"""Why did it not start? Recognizes known errors in the runner's output (Wine/Proton/DXVK error lines).

The result is a list of fixes that self-healing (heal.py) applies at the next start:
  ("verb", "vcrun2022")       installing a missing Windows component (winetricks, through umu)
  ("env", "PROTON_USE_WINED3D") turning on an environment variable
  ("args", "--disable-gpu")   an argument for the program (for apps with a built-in browser engine)
The user sees nothing of this.
"""
import re

# A missing DLL -> the winetricks component that brings it
DLL_VERBS = {
    **dict.fromkeys(("msvcp140", "msvcp140_1", "msvcp140_2", "vcruntime140", "vcruntime140_1", "concrt140",
                     "vcomp140", "mfc140", "mfc140u", "vccorlib140"), "vcrun2022"),
    **dict.fromkeys(("msvcp120", "msvcr120", "vcomp120", "mfc120", "mfc120u"), "vcrun2013"),
    **dict.fromkeys(("msvcp110", "msvcr110", "vcomp110", "mfc110", "mfc110u"), "vcrun2012"),
    **dict.fromkeys(("msvcp100", "msvcr100", "vcomp100", "mfc100", "mfc100u"), "vcrun2010"),
    **dict.fromkeys(("msvcp90", "msvcr90", "mfc90", "mfc90u"), "vcrun2008"),
    **dict.fromkeys(("msvcp80", "msvcr80", "mfc80", "mfc80u"), "vcrun2005"),
    **{f"d3dx9_{n}": "d3dx9" for n in range(24, 44)},
    **{f"d3dx10_{n}": "d3dx10" for n in range(33, 44)},
    "d3dx11_42": "d3dx11_42", "d3dx11_43": "d3dx11_43",
    "d3dcompiler_42": "d3dcompiler_42", "d3dcompiler_43": "d3dcompiler_43", "d3dcompiler_46": "d3dcompiler_46",
    "d3dcompiler_47": "d3dcompiler_47",
    **dict.fromkeys(("x3daudio1_7", "xapofx1_5", "xaudio2_7", "xactengine3_7"), "xact"),
    "xinput1_3": "xinput", "physxloader": "physx", "physxcore": "physx",
    "msxml3": "msxml3", "msxml4": "msxml4", "msxml6": "msxml6",
    "gdiplus": "gdiplus", "riched20": "riched20", "mfplat": "mf", "mf": "mf",
    "vb6run": "vb6run", "msvbvm60": "vb6run", "mscomctl": "mfc42", "mfc42": "mfc42",
}

_MISSING_DLL = re.compile(r"err:module:import_dll (?:library|loading library) ([\w.\-]+?)(?:\.dll)?\b", re.I)
_LOAD_FAIL = re.compile(r"err:module:\w+ (?:failed to load|could not load) .*?([\w\-]+)\.dll", re.I)

# (patterns in lowercase, fix)
_RULES = [
    # .NET: wine-mono is not enough (e.g. a WPF program or one asking for .NET Framework 4.8)
    (("err:mscoree", "could not load wine mono", "clr version not found"), ("verb", "dotnet48")),
    # Vulkan / DXVK does not start (an old or missing Vulkan driver): the old, OpenGL-based Direct3D
    (("failed to create vulkan instance", "dxvk: no adapters", "vkcreatedevice failed",
      "failed to create device", "vk_error_initialization_failed", "vk_error_incompatible_driver"),
     ("env", "PROTON_USE_WINED3D")),
    # Built-in browser engine (CEF / Electron): the GPU process does not start
    (("gpu process isn't usable", "gpu_process_host", "exiting gpu process", "gpu process exited unexpectedly"),
     ("args", "--disable-gpu")),
]

# If any of these shows, the program crashed (the user did not close it)
CRASH_MARKS = ("unhandled exception", "unhandled page fault", "wine: unhandled", "err:seh:", "backtrace:",
               "assertion failed", "fatal error", "access violation", "segmentation fault", "crashed")


def crashed(lines):
    return any(any(m in line.lower() for m in CRASH_MARKS) for line in lines)


def fixes(lines):
    """The output's lines -> a list of fixes (in order, without repeats)."""
    out = []

    def add(fix):
        if fix not in out:
            out.append(fix)

    for line in lines:
        for pattern in (_MISSING_DLL, _LOAD_FAIL):
            m = pattern.search(line)
            if m:
                verb = DLL_VERBS.get(m.group(1).lower().removesuffix(".dll"))
                if verb:
                    add(("verb", verb))
        low = line.lower()
        for marks, fix in _RULES:
            if any(mark in low for mark in marks):
                add(fix)
    return out
