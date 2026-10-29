# TEMPLATE -- not a working formula yet. See packaging/README.md for
# exactly what's missing (a real tagged release + a real sha256).
class LinkScrub < Formula
  desc "Strip tracking query params from URLs and unwrap link-shim redirectors"
  homepage "https://github.com/OWNER/TAGOFF"
  # TODO: replace with the real tagged-release tarball URL once one exists.
  url "https://github.com/OWNER/TAGOFF/archive/refs/tags/vX.Y.Z.tar.gz"
  # TODO: replace with `shasum -a 256 <the tarball above>` once it's real.
  sha256 "0000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "rust" => :build

  def install
    cd "rust_core" do
      system "cargo", "install", *std_cargo_args
    end
  end

  test do
    assert_match "id=1", shell_output("#{bin}/tagoff https://example.com/a?utm_source=x\\&id=1")
  end
end
