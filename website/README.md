# Sloth OS website and user guides

The static website is served from the `website/` folder. It contains the public-facing overview and guides:

- [Website home](index.html)
- [Getting started](getting-started.html)
- [Windows programs and games](windows-apps.html)
- [Privacy](privacy.html)
- [FAQ](faq.html)

## GitHub Pages

The workflow in `.github/workflows/pages.yml` deploys the `website/` directory when changes reach `main`. In the repository settings, open **Pages** and set the build and deployment source to **GitHub Actions**. The first deployment runs after the workflow is merged and Pages is enabled.

The intended address is `https://sloth-os-linux.github.io/`. GitHub Pages availability for a private repository depends on the account plan and repository settings. The project roadmap also lists making the repository public as a release prerequisite. Keep the pre-release and download-status copy current until a public installer and real-hardware validation are ready.

## Content policy

The pages describe the repository as it currently stands. They call out the pre-release status and do not advertise an ISO that is not available. Update the release status, installation guide and privacy details when the implementation changes. The detailed developer setup and build steps remain in the root README and developer docs (`docs/`, not published).

## License

The pages are covered by the project's licenses (see `NOTICE`): code Apache-2.0, the Sloth OS logo
(`logo.svg`, a copy of `files/system/usr/share/sloth-os/logo/sloth-logo-flat.svg`) CC BY-SA 4.0.
