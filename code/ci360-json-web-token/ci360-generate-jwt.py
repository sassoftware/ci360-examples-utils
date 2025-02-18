import base64
import jwt

# Find the tenant ID and client secret in the user interface for 
# SAS Customer Intelligence 360.

tenantId = 'replaceThisWithTenantId'
secret = 'replaceThisWithClientSecret'

# Encode the client secret in base64
encodedSecret = base64.b64encode(bytes(secret, 'utf-8'))

# Generate the token
token = jwt.encode({'clientID': tenantId}, encodedSecret, algorithm='HS256')

# Print the result
print('\nJWT token: ', token)