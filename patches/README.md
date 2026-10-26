# rpm-ostree layer-read fix

`rpm-ostree-async-layer-read.patch` keeps the downloaded layer file on Tokio's async runtime and bridges a Tokio duplex stream to the synchronous tar parser. This avoids polling the image proxy's pipe-backed `tokio::fs::File` through `SyncIoBridge`, the path seen in the Sloth OS update crash log.

The checked-in runtime RPMs in `files/rpm-ostree/` were built for Fedora 44 from upstream `rpm-ostree` 2026.3 (release `4.sloth2`). The build used `rpm-ostree.spec`, `builddeps.spec`, and the upstream 2026.3 release tarball. Fedora 44 must be built with `--without ostree_ext`: the `bootc` package owns those libostree helper files. Build for x86_64 in a Fedora 44 build environment with the spec's build dependencies installed:

```sh
rpmbuild --define '_topdir /path/to/rpmbuild' \
  --without ostree_ext --without sanitizers --without bin_unit_tests \
  --without rhsm --with zchunk --define '_smp_mflags -j2' \
  -ba /path/to/rpm-ostree.spec
```

The `rpm-ostree-fix.yml` recipe module installs these two local RPMs in both Sloth OS variants and removes their build-time copies from the image. The RPMs were checked for Fedora 44 package metadata; a clean-container install check is required before using the image.
