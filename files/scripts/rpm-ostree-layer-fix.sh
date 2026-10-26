#!/usr/bin/bash
set -euo pipefail

rpm_dir=/usr/share/sloth-os/rpm-ostree
dnf -y --setopt=install_weak_deps=False --nogpgcheck install "$rpm_dir"/*.rpm
rpm -q rpm-ostree rpm-ostree-libs
rm -rf "$rpm_dir"
