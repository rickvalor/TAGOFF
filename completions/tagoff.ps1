# PowerShell completion for tagoff / tagoff.
# Install: dot-source this file from your $PROFILE.
$LinkScrubOptions = @(
    '-v', '--verbose', '--json', '--stats', '--check',
    '--list-params', '--list-domains', '-h', '--help', '-V', '--version'
)

$LinkScrubCompleter = {
    param($wordToComplete, $commandAst, $cursorPosition)
    $LinkScrubOptions | Where-Object { $_ -like "$wordToComplete*" } |
        ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
}

Register-ArgumentCompleter -Native -CommandName tagoff -ScriptBlock $LinkScrubCompleter
Register-ArgumentCompleter -Native -CommandName tagoff -ScriptBlock $LinkScrubCompleter
Register-ArgumentCompleter -Native -CommandName tagoff-watch -ScriptBlock $LinkScrubCompleter
