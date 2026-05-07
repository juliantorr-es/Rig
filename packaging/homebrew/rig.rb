class Rig < Formula
  include Language::Python::Virtualenv

  desc "Cryptographically governed control plane for local AI coding"
  homepage "https://github.com/juliantorr-es/Rig"
  url "https://github.com/juliantorr-es/Rig/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "AGPL-3.0-or-later"

  depends_on "python@3.14"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"rig", "--help"
  end
end
