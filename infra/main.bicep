// ============================================================================
// STC Pipeline - Azure infrastructure
// Deployed at RESOURCE GROUP scope. Create the resource group first:
//
//   az group create --name rg-stc-prd-uks-001 --location uksouth
//   az deployment group create --resource-group rg-stc-prd-uks-001 \
//       --template-file main.bicep --parameters main.bicepparam
//
// NOT VALIDATED: this environment has no Azure CLI / Bicep compiler
// available, so `az bicep build` has not been run against this file. Run it
// yourself before deploying:
//   az bicep build --file main.bicep
//
// Naming: follows OCUG Azure Cloud Resource Naming Standards Policy v1.2.
// Resource types marked (*) below are NOT in the policy's Appendix A - the
// abbreviations used here (id, acr, cae, caj) are proposed CAF-aligned codes,
// not yet approved. Raise these with the Cloud & Infrastructure Team per
// Section 8 of the policy (new resource type -> policy review) before this
// goes anywhere near a real prd subscription.
// ============================================================================

@description('Workload code - kept as "stc" across every resource for this pipeline, matching the policy\'s convention of one workload code per business capability.')
param workload string = 'stc'

@description('Environment code per policy Section 3.3')
@allowed(['prd', 'dev', 'tst', 'uat', 'sbx'])
param environment string = 'prd'

@description('Region code per policy Section 3.4 - uks is UK South, the default region')
@allowed(['uks', 'ukw', 'neu', 'cin', 'glb'])
param regionCode string = 'uks'

@description('Azure region matching regionCode - Bicep needs the real region name, not the 3-letter code')
param location string = 'uksouth'

@description('Instance number, zero-padded per policy (3 digits)')
param instance string = '001'

@description('SafetyCulture API key - pass via --parameters at deploy time (e.g. from a pipeline secret), never commit a real value here')
@secure()
param safetyCultureApiKey string

@description('Container image to run, e.g. acrocustcprd001.azurecr.io/stc-pipeline:latest - built and pushed separately, see Dockerfile')
param containerImage string

@description('Cron schedule for the pipeline run, default = daily at 02:00 UTC')
param cronSchedule string = '0 2 * * *'

// ----------------------------------------------------------------------------
// Naming helpers - one place to see how every resource name is built
// ----------------------------------------------------------------------------
var namePrefix = '${workload}-${environment}-${regionCode}-${instance}'

var storageAccountName = 'stocu${workload}${environment}${instance}'      // special case: no hyphens, lowercase, <=24 chars
var acrName = 'acrocu${workload}${environment}${instance}'                // (*) not in Appendix A - same no-hyphen constraint as storage
var keyVaultName = 'kv-${namePrefix}'                                     // <=24 chars: "kv-stc-prd-uks-001" = 18 chars, OK
var logAnalyticsName = 'law-${namePrefix}'
var appInsightsName = 'appi-${namePrefix}'
var managedIdentityName = 'id-${namePrefix}'                             // (*) not in Appendix A
var containerAppsEnvName = 'cae-${namePrefix}'                          // (*) not in Appendix A
var containerAppJobName = 'caj-${namePrefix}'                           // (*) not in Appendix A

var filesystemName = 'stc-data' // the ADLS Gen2 filesystem / blob container holding TNS/BNZ/SLV/GLD/REP

// ----------------------------------------------------------------------------
// Storage Account (ADLS Gen2 - hierarchical namespace enabled)
// ----------------------------------------------------------------------------
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    isHnsEnabled: true // this is what makes it ADLS Gen2, not just blob storage
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
  tags: {
    DisplayName: 'st-${namePrefix}'
    workload: workload
    environment: environment
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}

resource dataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: filesystemName
  properties: {
    publicAccess: 'None'
  }
}

// ----------------------------------------------------------------------------
// Key Vault - holds the SafetyCulture API key and any other pipeline secrets
// ----------------------------------------------------------------------------
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true // access via RBAC role assignments below, not legacy access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
  }
  tags: {
    DisplayName: keyVaultName
    workload: workload
    environment: environment
  }
}

resource apiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'safetyculture-api-key'
  properties: {
    value: safetyCultureApiKey
  }
}

// ----------------------------------------------------------------------------
// Monitoring
// ----------------------------------------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: {
    DisplayName: logAnalyticsName
    workload: workload
    environment: environment
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'other'
  properties: {
    Application_Type: 'other'
    WorkspaceResourceId: logAnalytics.id
  }
  tags: {
    DisplayName: appInsightsName
    workload: workload
    environment: environment
  }
}

// ----------------------------------------------------------------------------
// User-assigned managed identity - the Container App Job runs as this, so
// no connection strings/keys are ever baked into the image or env vars
// ----------------------------------------------------------------------------
resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: managedIdentityName
  location: location
  tags: {
    DisplayName: managedIdentityName
    workload: workload
    environment: environment
  }
}

// Grant the identity write access to the data lake
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, managedIdentity.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant the identity read access to the API key secret
resource keyVaultRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, 'KeyVaultSecretsUser')
  scope: keyVault
  properties: {
    // Key Vault Secrets User
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------------------
// Container Registry - holds the pipeline's Docker image
// ----------------------------------------------------------------------------
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false // pull via the managed identity, not admin credentials
  }
  tags: {
    DisplayName: 'acr-${namePrefix}'
    workload: workload
    environment: environment
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, managedIdentity.id, 'AcrPull')
  scope: containerRegistry
  properties: {
    // AcrPull
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ----------------------------------------------------------------------------
// Container Apps Environment + Job
// ----------------------------------------------------------------------------
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
  tags: {
    DisplayName: containerAppsEnvName
    workload: workload
    environment: environment
  }
}

resource pipelineJob 'Microsoft.App/jobs@2024-03-01' = {
  name: containerAppJobName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: cronSchedule
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 21600 // 6 hours - generous ceiling for a full run; tune once real run times are known
      replicaRetryLimit: 1
      registries: [
        {
          server: '${acrName}.azurecr.io'
          identity: managedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'safetyculture-api-key'
          keyVaultUrl: apiKeySecret.properties.secretUri
          identity: managedIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'stc-pipeline'
          image: containerImage
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: [
            {
              name: 'ADLS_ACCOUNT_URL'
              value: 'https://${storageAccountName}.blob.core.windows.net'
            }
            {
              name: 'ADLS_FILESYSTEM'
              value: filesystemName
            }
            {
              name: 'SAFETYCULTURE_API_KEY'
              secretRef: 'safetyculture-api-key'
            }
            {
              name: 'AZURE_CLIENT_ID' // tells DefaultAzureCredential which user-assigned identity to use
              value: managedIdentity.properties.clientId
            }
          ]
        }
      ]
    }
  }
  tags: {
    DisplayName: containerAppJobName
    workload: workload
    environment: environment
  }
}

// ----------------------------------------------------------------------------
// Outputs
// ----------------------------------------------------------------------------
output storageAccountName string = storageAccountName
output storageAccountUrl string = 'https://${storageAccountName}.blob.core.windows.net'
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output managedIdentityClientId string = managedIdentity.properties.clientId
output containerAppJobName string = containerAppJobName
