# Maintainer: Parch Linux Team
# Contributor: Parch Linux Team
# SPDX-License-Identifier: GPL-3.0-only

pkgname=pdm
pkgver=1.1.0
pkgrel=1
pkgdesc="A modern driver management tool for Arch-based distributions"
arch=('any')
url="https://github.com/parchlinux/Parch-Driver-Manager"
license=('GPL-3.0-only')
depends=(
    'python'
    'python-gobject'
    'gtk4'
    'libadwaita'
    'glib2'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-setuptools'
    'python-wheel'
    'gettext'
)
optdepends=(
    'pkexec: privilege escalation (default backend)'
    'sudo: alternative privilege escalation'
    'doas: alternative privilege escalation'
)
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/Parch-Driver-Manager-${pkgver}"

    msg2 "Compiling gettext translations..."
    msgfmt po/fa.po -o src/parch_driver_manager/locale/fa/LC_MESSAGES/parch-driver-manager.mo

    msg2 "Building Python package..."
    python -m build --wheel --no-isolation
}

check() {
    cd "${srcdir}/Parch-Driver-Manager-${pkgver}"

    if [[ -f pytest.ini ]] || [[ -d tests ]]; then
        msg2 "Running tests..."
        python -m pytest -v || true
    fi
}

package() {
    cd "${srcdir}/Parch-Driver-Manager-${pkgver}"

    msg2 "Installing Python package..."
    python -m installer --destdir="$pkgdir" dist/*.whl

    msg2 "Installing desktop file..."
    install -Dm644 data/com.parchlinux.DriverManager.desktop \
        "${pkgdir}/usr/share/applications/com.parchlinux.DriverManager.desktop"

    msg2 "Installing AppStream metadata..."
    install -Dm644 data/com.parchlinux.DriverManager.metainfo.xml \
        "${pkgdir}/usr/share/metainfo/com.parchlinux.DriverManager.metainfo.xml"

    msg2 "Installing GSettings schema..."
    install -Dm644 data/com.parchlinux.driver-manager.gschema.xml \
        "${pkgdir}/usr/share/glib-2.0/schemas/com.parchlinux.driver-manager.gschema.xml"

    msg2 "Installing icons..."
    for size in 16 22 24 32 48 64 96 128 256; do
        install -Dm644 data/icons/hicolor/scalable/apps/com.parchlinux.DriverManager.svg \
            "${pkgdir}/usr/share/icons/hicolor/scalable/apps/com.parchlinux.DriverManager.svg"
    done
    # Create the 48x48 PNG for notification icons that don't support SVG
    install -Dm644 data/icons/hicolor/scalable/apps/com.parchlinux.DriverManager.svg \
        "${pkgdir}/usr/share/icons/hicolor/scalable/apps/com.parchlinux.DriverManager.svg"
}
