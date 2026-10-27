# Branding generators

Developer scripts that produce the Sloth OS branding files. Their output is committed,
so the build does not run them. Re-run them only when you change the source.

| Script | Output | Needs |
|---|---|---|
| `gen_colors.py <out dir>` | Plasma color schemes (`files/system/usr/share/color-schemes/*.colors`) | Python stdlib |
| `wallpapers.py <out dir>` | Plasma wallpaper packages from the source images (4K, plus 5120x2160 for ultrawide ones); see the docstring for the Real-ESRGAN preparation | ImageMagick, realesrgan-ncnn-vulkan |
| `fastfetch_logo.py sloth-ascii-art.txt <out txt>` | The hanging sloth for fastfetch (`files/system/usr/share/sloth-os/logo/sloth-ascii.txt`): adds the colors to the hand-drawn `sloth-ascii-art.txt` (M: light mask, o: grey belly, the rest silver; the colors are in `files/system/etc/fastfetch/config.jsonc`) | Python stdlib |
| `plymouth_contour.py <padded logo png> <out dir> <N>` | `points.txt`, the clockwise outer-contour points used by the boot animation (`files/system/usr/share/plymouth/themes/sloth-os/sloth-os.script`) | numpy, opencv |

The logo source image is `docs/branding/logo-source.png`. Previews: `docs/branding/boot-preview.gif`
and `docs/branding/color-schemes-preview.png`.
