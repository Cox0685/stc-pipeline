using 'main.bicep'

param workload = 'stc'
param environment = 'prd'
param regionCode = 'uks'
param location = 'uksouth'
param instance = '001'

// Real value supplied at deploy time, e.g.:
//   az deployment group create ... --parameters safetyCultureApiKey=$env:SC_API_KEY
param safetyCultureApiKey = ''

// Built and pushed by the CI/CD pipeline before this deployment runs -
// see infra/Dockerfile
param containerImage = 'acrocustcprd001.azurecr.io/stc-pipeline:latest'

// Daily at 02:00 UTC - adjust once real run duration is known
param cronSchedule = '0 2 * * *'
