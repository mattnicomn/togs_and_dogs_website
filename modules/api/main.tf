resource "aws_api_gateway_rest_api" "main" {
  name        = "${var.name_prefix}-api"
  description = "Togs and Dogs Pet Sitting API"
  tags        = var.tags
}

resource "aws_api_gateway_authorizer" "cognito" {
  name          = "CognitoAuthorizer"
  type          = "COGNITO_USER_POOLS"
  rest_api_id   = aws_api_gateway_rest_api.main.id
  provider_arns = [var.user_pool_arn]
}

resource "aws_api_gateway_resource" "requests" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "requests"
}

# Public Intake POST /requests
resource "aws_api_gateway_method" "post_requests" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.requests.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "intake_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.requests.id
  http_method = aws_api_gateway_method.post_requests.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.intake_handler_invoke_arn
}

# Admin /admin path
resource "aws_api_gateway_resource" "admin" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "admin"
}

resource "aws_api_gateway_resource" "admin_requests" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "requests"
}

# Admin GET /admin/requests
resource "aws_api_gateway_method" "get_admin_requests" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_requests.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "admin_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_requests.id
  http_method = aws_api_gateway_method.get_admin_requests.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# Admin POST /admin/requests (Archive/Delete)
resource "aws_api_gateway_method" "post_admin_requests" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_requests.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_requests_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_requests.id
  http_method = aws_api_gateway_method.post_admin_requests.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# Admin POST /admin/review
resource "aws_api_gateway_resource" "admin_review" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "review"
}

resource "aws_api_gateway_method" "post_admin_review" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_review.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "review_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_review.id
  http_method = aws_api_gateway_method.post_admin_review.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.review_handler_invoke_arn
}

# Admin POST /admin/assign
resource "aws_api_gateway_resource" "admin_assign" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "assign"
}

resource "aws_api_gateway_method" "post_admin_assign" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_assign.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "assign_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_assign.id
  http_method = aws_api_gateway_method.post_admin_assign.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.assign_handler_invoke_arn
}

# Admin /admin/auth path
resource "aws_api_gateway_resource" "admin_auth" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "auth"
}

resource "aws_api_gateway_resource" "admin_auth_google" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_auth.id
  path_part   = "google"
}

# Admin GET /admin/auth/google
resource "aws_api_gateway_method" "get_google_auth" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_auth_google.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "google_auth_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_auth_google.id
  http_method = aws_api_gateway_method.get_google_auth.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.google_auth_handler_invoke_arn
}

resource "aws_api_gateway_resource" "admin_auth_callback" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_auth.id
  path_part   = "callback"
}

# Admin GET /admin/auth/callback
resource "aws_api_gateway_method" "get_google_callback" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_auth_callback.id
  http_method   = "GET"
  authorization = "NONE" # Validated by OAuth state in DB
}

resource "aws_api_gateway_integration" "google_callback_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_auth_callback.id
  http_method = aws_api_gateway_method.get_google_callback.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.google_auth_handler_invoke_arn
}
resource "aws_api_gateway_resource" "admin_auth_status" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_auth.id
  path_part   = "status"
}

# Admin GET /admin/auth/status
resource "aws_api_gateway_method" "get_google_status" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_auth_status.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "google_status_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_auth_status.id
  http_method = aws_api_gateway_method.get_google_status.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.google_auth_handler_invoke_arn
}

# ------------------------------------------------------------------------------
# Pets / Care Cards
# ------------------------------------------------------------------------------

resource "aws_api_gateway_resource" "admin_pets" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "pets"
}

# Admin POST /admin/pets (Create Pet)
resource "aws_api_gateway_method" "post_pet" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_pets.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_pet_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_pets.id
  http_method = aws_api_gateway_method.post_pet.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.pet_handler_invoke_arn
}

resource "aws_api_gateway_resource" "admin_pet_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_pets.id
  path_part   = "{petId}"
}

# Admin GET /admin/pets/{petId}
resource "aws_api_gateway_method" "get_pet" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_pet_id.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_pet_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_pet_id.id
  http_method = aws_api_gateway_method.get_pet.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.pet_handler_invoke_arn
}

# Admin PUT /admin/pets/{petId} (Update Pet)
resource "aws_api_gateway_method" "put_pet" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_pet_id.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "put_pet_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_pet_id.id
  http_method = aws_api_gateway_method.put_pet.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.pet_handler_invoke_arn
}

# ------------------------------------------------------------------------------
# Cancellation & Change Management
# ------------------------------------------------------------------------------

# Client /client path (parent for customer-facing endpoints)
resource "aws_api_gateway_resource" "client" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "client"
}

# Customer POST /client/cancel
resource "aws_api_gateway_resource" "client_cancel" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.client.id
  path_part   = "cancel"
}

resource "aws_api_gateway_method" "post_client_cancel" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.client_cancel.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_client_cancel_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.client_cancel.id
  http_method = aws_api_gateway_method.post_client_cancel.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.cancellation_handler_invoke_arn
}

# Client /client/requests
resource "aws_api_gateway_resource" "client_requests" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.client.id
  path_part   = "requests"
}

resource "aws_api_gateway_method" "get_client_requests" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.client_requests.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_client_requests_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.client_requests.id
  http_method = aws_api_gateway_method.get_client_requests.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_method" "post_client_requests" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.client_requests.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_client_requests_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.client_requests.id
  http_method = aws_api_gateway_method.post_client_requests.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.intake_handler_invoke_arn
}

# Client /client/pets
resource "aws_api_gateway_resource" "client_pets" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.client.id
  path_part   = "pets"
}

resource "aws_api_gateway_method" "get_client_pets" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.client_pets.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_client_pets_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.client_pets.id
  http_method = aws_api_gateway_method.get_client_pets.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.pet_handler_invoke_arn
}

# Admin GET /admin/staff
resource "aws_api_gateway_resource" "admin_staff" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "staff"
}

resource "aws_api_gateway_method" "get_admin_staff" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_admin_staff_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff.id
  http_method = aws_api_gateway_method.get_admin_staff.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_method" "post_admin_staff" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_staff_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff.id
  http_method = aws_api_gateway_method.post_admin_staff.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# Admin /admin/staff/{staff_id}
resource "aws_api_gateway_resource" "admin_staff_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_staff.id
  path_part   = "{staff_id}"
}

resource "aws_api_gateway_method" "patch_admin_staff_id" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff_id.id
  http_method   = "PATCH"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "patch_admin_staff_id_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff_id.id
  http_method = aws_api_gateway_method.patch_admin_staff_id.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_method" "delete_admin_staff_id" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff_id.id
  http_method   = "DELETE"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "delete_admin_staff_id_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff_id.id
  http_method = aws_api_gateway_method.delete_admin_staff_id.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# --- Phase 3 Onboarding Routes ---

# POST /admin/staff/onboard
resource "aws_api_gateway_resource" "admin_staff_onboard" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_staff.id
  path_part   = "onboard"
}

resource "aws_api_gateway_method" "post_admin_staff_onboard" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff_onboard.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_staff_onboard_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff_onboard.id
  http_method = aws_api_gateway_method.post_admin_staff_onboard.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# POST /admin/staff/{staff_id}/link-cognito
resource "aws_api_gateway_resource" "admin_staff_link" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_staff_id.id
  path_part   = "link-cognito"
}

resource "aws_api_gateway_method" "post_admin_staff_link" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff_link.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_staff_link_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff_link.id
  http_method = aws_api_gateway_method.post_admin_staff_link.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# POST /admin/staff/{staff_id}/resend-invite
resource "aws_api_gateway_resource" "admin_staff_resend" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_staff_id.id
  path_part   = "resend-invite"
}

resource "aws_api_gateway_method" "post_admin_staff_resend" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_staff_resend.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_staff_resend_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_staff_resend.id
  http_method = aws_api_gateway_method.post_admin_staff_resend.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}



# --- Phase 5A Client Profile Routes ---

resource "aws_api_gateway_resource" "admin_clients" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "clients"
}

resource "aws_api_gateway_method" "get_admin_clients" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_clients.id
  http_method   = "GET"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "get_admin_clients_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_clients.id
  http_method = aws_api_gateway_method.get_admin_clients.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_method" "post_admin_clients" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_clients.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_clients_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_clients.id
  http_method = aws_api_gateway_method.post_admin_clients.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_resource" "admin_client_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_clients.id
  path_part   = "{client_id}"
}

resource "aws_api_gateway_method" "patch_admin_client_id" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_client_id.id
  http_method   = "PATCH"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "patch_admin_client_id_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_client_id.id
  http_method = aws_api_gateway_method.patch_admin_client_id.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

resource "aws_api_gateway_resource" "admin_client_disable" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_client_id.id
  path_part   = "disable"
}

resource "aws_api_gateway_method" "post_admin_client_disable" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_client_disable.id
  http_method   = "POST"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "post_admin_client_disable_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_client_disable.id
  http_method = aws_api_gateway_method.post_admin_client_disable.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.admin_handler_invoke_arn
}

# Admin PUT /admin/cancel/decision


resource "aws_api_gateway_resource" "admin_cancel" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin.id
  path_part   = "cancel"
}

resource "aws_api_gateway_resource" "admin_cancel_decision" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.admin_cancel.id
  path_part   = "decision"
}

resource "aws_api_gateway_method" "put_admin_cancel" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.admin_cancel_decision.id
  http_method   = "PUT"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
}

resource "aws_api_gateway_integration" "put_admin_cancel_lambda" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = aws_api_gateway_resource.admin_cancel_decision.id
  http_method = aws_api_gateway_method.put_admin_cancel.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.cancellation_handler_invoke_arn
}

# ------------------------------------------------------------------------------
# CORS / OPTIONS
# ------------------------------------------------------------------------------

locals {
  cors_resources = {
    "requests" : aws_api_gateway_resource.requests.id,
    "admin_requests" : aws_api_gateway_resource.admin_requests.id,
    "admin_review" : aws_api_gateway_resource.admin_review.id,
    "admin_assign" : aws_api_gateway_resource.admin_assign.id,
    "admin_auth" : aws_api_gateway_resource.admin_auth.id,
    "admin_auth_google" : aws_api_gateway_resource.admin_auth_google.id,
    "admin_auth_callback" : aws_api_gateway_resource.admin_auth_callback.id,
    "admin_auth_status" : aws_api_gateway_resource.admin_auth_status.id,
    "admin_pets" : aws_api_gateway_resource.admin_pets.id,
    "admin_pet_id" : aws_api_gateway_resource.admin_pet_id.id,
    "client_cancel" : aws_api_gateway_resource.client_cancel.id,
    "admin_cancel_decision" : aws_api_gateway_resource.admin_cancel_decision.id,
    "admin_staff" : aws_api_gateway_resource.admin_staff.id,
    "admin_staff_id" : aws_api_gateway_resource.admin_staff_id.id,
    "admin_staff_onboard" : aws_api_gateway_resource.admin_staff_onboard.id,
    "admin_staff_link" : aws_api_gateway_resource.admin_staff_link.id,
    "admin_staff_resend" : aws_api_gateway_resource.admin_staff_resend.id,
    "admin_clients" : aws_api_gateway_resource.admin_clients.id,
    "admin_client_id" : aws_api_gateway_resource.admin_client_id.id,
    "admin_client_disable" : aws_api_gateway_resource.admin_client_disable.id,
    "client_requests" : aws_api_gateway_resource.client_requests.id,
    "client_pets" : aws_api_gateway_resource.client_pets.id
  }



}

resource "aws_api_gateway_method" "options" {
  for_each      = local.cors_resources
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = each.value
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_mock" {
  for_each    = local.cors_resources
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "options_200" {
  for_each    = local.cors_resources
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_200" {
  for_each    = local.cors_resources
  rest_api_id = aws_api_gateway_rest_api.main.id
  resource_id = each.value
  http_method = aws_api_gateway_method.options[each.key].http_method
  status_code = aws_api_gateway_method_response.options_200[each.key].status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'" # Replaced by Lambda response Origin reflecting for dynamic whitelist, but static default safe for MOCK
  }

  depends_on = [aws_api_gateway_integration.options_mock]
}

# ------------------------------------------------------------------------------
# Gateway Responses (Global CORS for errors)
# ------------------------------------------------------------------------------

resource "aws_api_gateway_gateway_response" "unauthorized" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
  }

  response_templates = {
    "application/json" = "{\"message\":$context.error.messageString}"
  }
}

resource "aws_api_gateway_gateway_response" "missing_auth_token" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  response_type = "MISSING_AUTHENTICATION_TOKEN"
  status_code   = "403"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
  }

  response_templates = {
    "application/json" = "{\"message\":$context.error.messageString}"
  }
}

resource "aws_api_gateway_deployment" "main" {
  depends_on = [
    aws_api_gateway_integration.intake_lambda,
    aws_api_gateway_integration.admin_lambda,
    aws_api_gateway_integration.post_admin_requests_lambda,
    aws_api_gateway_integration.review_lambda,
    aws_api_gateway_integration.assign_lambda,
    aws_api_gateway_integration.google_auth_lambda,
    aws_api_gateway_integration.google_callback_lambda,
    aws_api_gateway_integration.google_status_lambda,
    aws_api_gateway_integration.post_pet_lambda,
    aws_api_gateway_integration.get_pet_lambda,
    aws_api_gateway_integration.put_pet_lambda,
    aws_api_gateway_integration.post_client_cancel_lambda,
    aws_api_gateway_integration.put_admin_cancel_lambda,
    aws_api_gateway_integration.get_admin_staff_lambda,
    aws_api_gateway_integration.post_admin_staff_lambda,
    aws_api_gateway_integration.patch_admin_staff_id_lambda,
    aws_api_gateway_integration.delete_admin_staff_id_lambda,
    aws_api_gateway_integration_response.options_200,


    aws_api_gateway_gateway_response.unauthorized,
    aws_api_gateway_gateway_response.missing_auth_token
  ]

  rest_api_id = aws_api_gateway_rest_api.main.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.requests,
      aws_api_gateway_resource.admin,
      aws_api_gateway_resource.admin_requests,
      aws_api_gateway_resource.admin_review,
      aws_api_gateway_resource.admin_assign,
      aws_api_gateway_resource.admin_auth,
      aws_api_gateway_resource.admin_auth_google,
      aws_api_gateway_resource.admin_auth_callback,
      aws_api_gateway_resource.admin_auth_status,
      aws_api_gateway_resource.admin_pets,
      aws_api_gateway_resource.admin_pet_id,
      aws_api_gateway_resource.client_cancel,
      aws_api_gateway_resource.client_requests,
      aws_api_gateway_resource.client_pets,
      aws_api_gateway_resource.admin_cancel_decision,
      aws_api_gateway_resource.admin_staff,
      aws_api_gateway_resource.admin_staff_id,
      aws_api_gateway_method.post_admin_requests,
      aws_api_gateway_method.get_client_requests,
      aws_api_gateway_method.post_client_requests,
      aws_api_gateway_method.get_client_pets,


      aws_api_gateway_method.options,
      aws_api_gateway_integration.options_mock,
      aws_api_gateway_method_response.options_200,
      aws_api_gateway_integration_response.options_200,
      aws_api_gateway_gateway_response.unauthorized,
      aws_api_gateway_gateway_response.missing_auth_token
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment
}
