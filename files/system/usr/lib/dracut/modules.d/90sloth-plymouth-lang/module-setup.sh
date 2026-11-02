#!/bin/bash
# Sloth OS: the language of the boot screen's password hint (Plymouth theme sloth-os). The installer puts the language
# chosen there on the kernel command line (sloth.lang=hu); in the initramfs this service hands it to the theme,
# before the encrypted disk's password is asked.

check() {
    return 255  # only when asked for (dracut.conf.d/91-sloth-plymouth-lang.conf)
}

depends() {
    echo plymouth systemd
}

install() {
    inst_simple "$moddir/sloth-plymouth-lang.sh" /usr/libexec/sloth-plymouth-lang
    inst_simple "$moddir/sloth-plymouth-lang.service" "$systemdsystemunitdir/sloth-plymouth-lang.service"
    $SYSTEMCTL -q --root "$initdir" add-wants sysinit.target sloth-plymouth-lang.service
}
