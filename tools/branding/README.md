# Branding generators

Developer scripts that produce the Sloth OS branding files. Their output is committed,
so the build does not run them. Re-run them only when you change the source.

| Script | Output | Needs |
|---|---|---|
| `gen_colors.py <out dir>` | Plasma color schemes (`files/system/usr/share/color-schemes/*.colors`) | Python stdlib |
| `wallpapers.py <out dir>` | Plasma wallpaper packages from the source images (4K, plus 5120x2160 for ultrawide ones); see the docstring for the Real-ESRGAN preparation | ImageMagick, realesrgan-ncnn-vulkan |
| `plymouth_contour.py <padded logo png> <out dir> <N>` | `points.txt`, the clockwise outer-contour points used by the boot animation (`files/system/usr/share/plymouth/themes/sloth-os/sloth-os.script`) | numpy, opencv |

The logo source image is `docs/branding/logo-source.png`. Previews: `docs/branding/boot-preview.gif`
and `docs/branding/color-schemes-preview.png`.
