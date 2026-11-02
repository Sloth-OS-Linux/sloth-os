#!/bin/sh
# Tells the boot screen the language of the password hint: sloth.lang=hu -> "sloth-lang:hu" (sloth-os.script)
for arg in $(cat /proc/cmdline); do
    case "$arg" in
        sloth.lang=*)
            lang="${arg#sloth.lang=}"
            # only a language code (hu, pt_BR…): it becomes part of a file name
            case "$lang" in
                *[!A-Za-z_]*|"") exit 0 ;;
            esac
            plymouth display-message --text="sloth-lang:$lang"
            ;;
    esac
done
exit 0
