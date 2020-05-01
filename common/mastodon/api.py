# See https://docs.joinmastodon.org/methods/accounts/

# returns user info
# retruns the same info as verify account credentials
# GET
ACCOUNT = '/api/v1/accounts/:id'

# returns user info if valid, 401 if invalid
# GET
VERIFY_ACCOUNT_CREDENTIALS = '/api/v1/accounts/verify_credentials'

# obtain token
# GET
OAUTH_TOKEN = '/oauth/token'

# obatin auth code
# GET
OAUTH_AUTHORIZE = '/oauth/authorize'

# revoke token
# POST
REVOKE_TOKEN = '/oauth/revoke'