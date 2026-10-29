# bash completion for tagoff / tagoff.
# Install: source this file, or copy it into /etc/bash_completion.d/
_tagoff_completions() {
    local cur
    cur="${COMP_WORDS[COMP_CWORD]}"
    local opts="-v --verbose --json --stats --check --list-params --list-domains -h --help -V --version"
    COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
}
complete -F _tagoff_completions tagoff
complete -F _tagoff_completions tagoff
complete -F _tagoff_completions tagoff-watch
