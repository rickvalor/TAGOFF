# bash completion for link-scrub / link_scrub.
# Install: source this file, or copy it into /etc/bash_completion.d/
_link_scrub_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    local opts="-v --verbose --json --stats --check --list-params --list-domains -h --help -V --version"
    COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
}
complete -F _link_scrub_completions link-scrub
complete -F _link_scrub_completions link_scrub
complete -F _link_scrub_completions link-scrub-watch
