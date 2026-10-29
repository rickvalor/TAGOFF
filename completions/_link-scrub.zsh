#compdef link-scrub link_scrub link-scrub-watch
# zsh completion for link-scrub / link_scrub.
# Install: copy as _link-scrub into a directory on your $fpath.

_arguments \
  '(-v --verbose)'{-v,--verbose}'[print what was removed/unwrapped, to stderr]' \
  '--json[emit one JSON object per line instead of plain text]' \
  '--stats[print an aggregate summary to stderr after processing]' \
  '--check[exit 1 if any URL had tracking to remove]' \
  '--list-params[print the loaded tracking-param rules and exit]' \
  '--list-domains[print the loaded redirector-domain rules and exit]' \
  '(-h --help)'{-h,--help}'[print the help message and exit]' \
  '(-V --version)'{-V,--version}'[print the version and exit]' \
  '*:URL:_urls'
