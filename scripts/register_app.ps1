<#
.SYNOPSIS
    Register an Azure AD app for TARS (Microsoft 365 integration).

.DESCRIPTION
    Since App Registrations may be disabled in the Azure Portal, this script
    uses the Microsoft Graph PowerShell SDK to create the app registration
    via PowerShell instead.

    Prerequisites:
      Install-Module Microsoft.Graph -Scope CurrentUser

.EXAMPLE
    ./scripts/register_app.ps1
    # Follow the prompts, then copy the output values into your .env file.
#>

#Requires -Modules Microsoft.Graph.Applications

param(
    [string]$AppName = "TARS Executive Assistant"
)

# ── Connect to Microsoft Graph ────────────────────────────────────────
Write-Host "Connecting to Microsoft Graph..." -ForegroundColor Cyan
Write-Host "You will be prompted to sign in with an account that has permission to create app registrations." -ForegroundColor Yellow
Write-Host ""

Connect-MgGraph -Scopes "Application.ReadWrite.All" -ErrorAction Stop

# ── Create the App Registration ───────────────────────────────────────
Write-Host ""
Write-Host "Creating app registration: $AppName" -ForegroundColor Cyan

# Define the required API permissions (Microsoft Graph delegated)
$requiredPermissions = @(
    @{ Id = "e1fe6dd8-ba31-4d61-89e7-88639da4683d"; Type = "Scope" }  # User.Read
    @{ Id = "ef54d2bf-783f-4e0f-bca1-3210c0444d99"; Type = "Scope" }  # Calendars.ReadWrite
    @{ Id = "e2ddd3b6-5240-4a5e-90dd-fe10aa2af2ce"; Type = "Scope" }  # Mail.ReadWrite (personal)
    @{ Id = "024d486e-b451-40bb-833d-3e66d98c5c73"; Type = "Scope" }  # Mail.Send
    @{ Id = "2219042f-cab5-40cc-b0d2-16b1540b4c5f"; Type = "Scope" }  # Tasks.ReadWrite
)

$resourceAccess = @{
    ResourceAppId  = "00000003-0000-0000-c000-000000000000"  # Microsoft Graph
    ResourceAccess = $requiredPermissions
}

$appParams = @{
    DisplayName            = $AppName
    SignInAudience         = "AzureADMyOrg"
    RequiredResourceAccess = @($resourceAccess)
    PublicClient           = @{
        RedirectUris = @("https://login.microsoftonline.com/common/oauth2/nativeclient")
    }
    IsFallbackPublicClient = $true
}

$app = New-MgApplication @appParams -ErrorAction Stop

# ── Get Tenant ID ─────────────────────────────────────────────────────
$context = Get-MgContext
$tenantId = $context.TenantId

# ── Output ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " App Registration Created Successfully" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Add these to your .env file:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  MS_CLIENT_ID=$($app.AppId)"
Write-Host "  MS_TENANT_ID=$tenantId"
Write-Host ""
Write-Host "App Object ID: $($app.Id)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Copy the values above into your .env file"
Write-Host "  2. Start TARS: python app.py"
Write-Host "  3. Send /login in Telegram to authenticate"
Write-Host ""
Write-Host "Note: An admin may need to grant consent for the API permissions." -ForegroundColor Yellow
Write-Host "They can do this via:" -ForegroundColor Yellow
Write-Host "  https://login.microsoftonline.com/$tenantId/adminconsent?client_id=$($app.AppId)" -ForegroundColor Yellow
Write-Host ""

Disconnect-MgGraph | Out-Null
