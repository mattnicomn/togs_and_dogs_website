[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TerraformPath
)

$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repositoryRoot "modules/api/deployment-semantics.tf.json"
$fingerprintModulePath = (Join-Path $repositoryRoot "modules/api/deployment-fingerprint").Replace("\", "/")
$temporaryRoot = Join-Path ([IO.Path]::GetTempPath()) ("togs-api-manifest-stability-" + [guid]::NewGuid().ToString("N"))
$systemTemporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$resolvedTemporaryRoot = [IO.Path]::GetFullPath($temporaryRoot)

if (-not $resolvedTemporaryRoot.StartsWith($systemTemporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use a temporary directory outside the system temporary root"
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [IO.File]::WriteAllText($Path, $Text, [Text.UTF8Encoding]::new($false))
}

function Invoke-Terraform {
    param([string[]]$Arguments, [string]$WorkingDirectory)
    $output = & $TerraformPath @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        $safe = @($output | Select-Object -Last 12) -join [Environment]::NewLine
        throw "Local provider-free Terraform command failed: $($Arguments[0])`n$safe"
    }
    return @($output)
}

function Get-PlannedFingerprint {
    param([string]$PlanPath, [string]$WorkingDirectory)
    $json = Invoke-Terraform -Arguments @("show", "-json", $PlanPath) -WorkingDirectory $WorkingDirectory
    $plan = ($json -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
    return [string]$plan.planned_values.outputs.semantic_sha1.value
}

function Assert-ManifestEmbedded {
    param([string]$PlanPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($PlanPath)
    try {
        $entry = $archive.GetEntry("tfconfig/m-/deployment-semantics.tf.json")
        if ($null -eq $entry) {
            throw "Saved plan does not embed deployment-semantics.tf.json"
        }
    }
    finally {
        $archive.Dispose()
    }
}

$rootConfiguration = @"
locals {
  api_integration_target_references = {
    for reference in distinct([
      for integration in values(local.api_deployment_semantics.integrations) : integration.target_reference
    ]) : reference => "test://`${reference}"
  }

  api_authorizer_provider_references = {
    for reference in distinct(flatten([
      for authorizer in values(local.api_deployment_semantics.authorizers) : authorizer.provider_reference_keys
    ])) : reference => "test://`${reference}"
  }

  api_deployment_authorizers = {
    for key, authorizer in local.api_deployment_semantics.authorizers : key => {
      type                = authorizer.type
      identity_source     = authorizer.identity_source
      provider_references = [for reference in authorizer.provider_reference_keys : local.api_authorizer_provider_references[reference]]
      result_ttl_seconds  = authorizer.result_ttl_seconds
    }
  }

  api_deployment_integrations = {
    for key, integration in local.api_deployment_semantics.integrations : key => merge(integration, {
      uri = local.api_integration_target_references[integration.target_reference]
    })
  }
}

module "deployment_fingerprint" {
  source = "$fingerprintModulePath"

  resources             = local.api_deployment_semantics.resources
  authorizers           = local.api_deployment_authorizers
  methods               = local.api_deployment_semantics.methods
  integrations          = local.api_deployment_integrations
  method_responses      = local.api_deployment_semantics.method_responses
  integration_responses = local.api_deployment_semantics.integration_responses
  cors                  = local.api_deployment_semantics.cors
  gateway_responses     = local.api_deployment_semantics.gateway_responses
}

output "semantic_sha1" {
  value = module.deployment_fingerprint.sha1
}
"@

try {
    New-Item -ItemType Directory -Path $resolvedTemporaryRoot | Out-Null
    $mainPath = Join-Path $resolvedTemporaryRoot "main.tf"
    $temporaryManifestPath = Join-Path $resolvedTemporaryRoot "deployment-semantics.tf.json"
    Write-Utf8NoBom -Path $mainPath -Text ($rootConfiguration.Replace("`r`n", "`n"))

    $manifestText = [IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8)
    $lfText = $manifestText.Replace("`r`n", "`n")
    $crlfText = $lfText.Replace("`n", "`r`n")
    $compactText = (($manifestText | ConvertFrom-Json -Depth 100) | ConvertTo-Json -Compress -Depth 100)
    Write-Utf8NoBom -Path $temporaryManifestPath -Text $lfText

    Push-Location $resolvedTemporaryRoot
    try {
        Invoke-Terraform -Arguments @("init", "-backend=false", "-input=false", "-no-color") -WorkingDirectory $resolvedTemporaryRoot | Out-Null

        $fingerprints = [ordered]@{}
        foreach ($case in @(
            @{ Name = "lf"; Text = $lfText },
            @{ Name = "crlf"; Text = $crlfText },
            @{ Name = "compact"; Text = $compactText }
        )) {
            Write-Utf8NoBom -Path $temporaryManifestPath -Text $case.Text
            $planPath = Join-Path $resolvedTemporaryRoot ("$($case.Name).tfplan")
            Invoke-Terraform -Arguments @("plan", "-refresh=false", "-lock=false", "-input=false", "-no-color", "-out=$planPath") -WorkingDirectory $resolvedTemporaryRoot | Out-Null
            Assert-ManifestEmbedded -PlanPath $planPath
            $fingerprints[$case.Name] = Get-PlannedFingerprint -PlanPath $planPath -WorkingDirectory $resolvedTemporaryRoot
        }

        if ($fingerprints.lf -ne $fingerprints.crlf -or $fingerprints.lf -ne $fingerprints.compact) {
            throw "LF, CRLF, and compact manifest representations produced different semantic fingerprints"
        }

        # Re-read the original LF plan after the working manifest has changed. The
        # saved plan remains self-contained because the Terraform JSON config is embedded.
        $archivedFingerprint = Get-PlannedFingerprint -PlanPath (Join-Path $resolvedTemporaryRoot "lf.tfplan") -WorkingDirectory $resolvedTemporaryRoot
        if ($archivedFingerprint -ne $fingerprints.lf) {
            throw "Saved-plan embedded configuration fingerprint changed after checkout bytes changed"
        }

        Write-Output "LF_FINGERPRINT=$($fingerprints.lf)"
        Write-Output "CRLF_FINGERPRINT=$($fingerprints.crlf)"
        Write-Output "COMPACT_FINGERPRINT=$($fingerprints.compact)"
        Write-Output "SAVED_PLAN_MANIFEST_EMBEDDED=true"
        Write-Output "SAVED_PLAN_REREAD_STABLE=true"
    }
    finally {
        Pop-Location
    }
}
finally {
    if (Test-Path -LiteralPath $resolvedTemporaryRoot) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force
    }
}
