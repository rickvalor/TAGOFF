# PowerShell completion for link-scrub / link_scrub.
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

Register-ArgumentCompleter -Native -CommandName link-scrub -ScriptBlock $LinkScrubCompleter
Register-ArgumentCompleter -Native -CommandName link_scrub -ScriptBlock $LinkScrubCompleter
Register-ArgumentCompleter -Native -CommandName link-scrub-watch -ScriptBlock $LinkScrubCompleter
