# Schema Comparison for SAS Customer Intelligence 360

This script downloads the JSON schema files for the Unified Data Model (UDM) and generates
a list of differences between the schemas.

## Prerequisites

Make sure that you have completed these prerequisites:

1. This script requires Python 3.10 or later and the packages PyJWT and requests.
2. You must have an access point in SAS Customer Intelligence 360.
3. Create an access point in SAS Customer Intelligence 360.
   1. From the user interface, navigate to **General Settings** > **External Access** > **Access Points**.
   2. Create a new access point if one does not exist.
   3. Get the following information from the access point:

      ```cmd
       External gateway address: e.g. https://extapigwservice-<server>/marketingGateway  
       Name: ci360_agent  
       Tenant ID: abc123-ci360-tenant-id-xyz  
       Client secret: ABC123ci360clientSecretXYZ
      ```

4. In this repository, edit the dsccnfg/config.txt file to complete this information:

   ```cmd
   agentName = <your agent name>
   tenantId  = <your tenant id>
   secret    = <your secret>
   baseUrl   = https://extapigwservice-<server>/marketingGateway/discoverService/dataDownload/eventData/
   ```

## Using the Script

You can run the script through the command line, like these examples

```cmd
  python ci360_schemas.py                  # download and compare the files
  python ci360_schemas.py --download-only  # skip compare and download the schema files
  python ci360_schemas.py --compare-only   # compare schema files based on local copies
  python ci360_schemas.py --csv-only       # export JSON schemas to CSV files
```
