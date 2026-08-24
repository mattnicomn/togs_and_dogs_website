variables {
  resources = {
    pets = {
      parent_key = "root"
      path_part  = "pets"
    }
  }
  authorizers = {
    cognito = {
      type                = "COGNITO_USER_POOLS"
      identity_source     = "method.request.header.Authorization"
      provider_references = ["arn:aws:cognito-idp:us-east-1:111122223333:userpool/test"]
    }
  }
  methods = {
    get_pets = {
      resource_key   = "pets"
      http_method    = "GET"
      authorization  = "COGNITO_USER_POOLS"
      authorizer_key = "cognito"
    }
  }
  integrations = {
    get_pets = {
      method_key              = "get_pets"
      type                    = "AWS_PROXY"
      integration_http_method = "POST"
      uri                     = "arn:aws:apigateway:us-east-1:lambda:path/functions/test/invocations"
    }
  }
  cors = {
    resource_keys = ["pets"]
    method        = {}
    integration = {
      request_templates = {
        "application/json" = "{\"statusCode\": 200}"
      }
    }
    method_response = {
      status_code = "200"
      response_models = {
        "application/json" = "Empty"
      }
      response_parameters = {
        "method.response.header.Access-Control-Allow-Origin" = true
      }
    }
    integration_response = {
      status_code = "200"
      response_parameters = {
        "method.response.header.Access-Control-Allow-Origin" = "'*'"
      }
    }
  }
  gateway_responses = {
    unauthorized = {
      response_type = "UNAUTHORIZED"
      status_code   = "401"
    }
  }
}

run "baseline" {
  command = plan

  assert {
    condition     = length(output.sha1) == 40
    error_message = "The semantic fingerprint must be a SHA-1 digest."
  }
}

run "null_and_empty_are_equivalent" {
  command = plan

  variables {
    authorizers = {
      cognito = {
        type                = "COGNITO_USER_POOLS"
        identity_source     = "method.request.header.Authorization"
        provider_references = ["arn:aws:cognito-idp:us-east-1:111122223333:userpool/test"]
        result_ttl_seconds  = null
      }
    }
    methods = {
      get_pets = {
        resource_key          = "pets"
        http_method           = "GET"
        authorization         = "COGNITO_USER_POOLS"
        authorizer_key        = "cognito"
        api_key_required      = null
        authorization_scopes  = null
        operation_name        = null
        request_models        = null
        request_parameters    = null
        request_validator_key = null
      }
    }
    integrations = {
      get_pets = {
        method_key                     = "get_pets"
        type                           = "AWS_PROXY"
        integration_http_method        = "POST"
        uri                            = "arn:aws:apigateway:us-east-1:lambda:path/functions/test/invocations"
        connection_type                = null
        connection_reference           = null
        credentials_reference          = null
        request_parameters             = null
        request_templates              = null
        passthrough_behavior           = null
        cache_key_parameters           = null
        cache_namespace                = null
        content_handling               = null
        timeout_milliseconds           = null
        tls_insecure_skip_verification = null
      }
    }
    cors = {
      resource_keys = ["pets"]
      method = {
        authorizer_key       = null
        authorization_scopes = null
        operation_name       = null
        request_models       = null
        request_parameters   = null
      }
      integration = {
        integration_http_method = null
        uri                     = null
        request_parameters      = null
        request_templates = {
          "application/json" = "{\"statusCode\": 200}"
        }
        cache_key_parameters = null
        cache_namespace      = null
        content_handling     = null
      }
      method_response = {
        status_code = "200"
        response_models = {
          "application/json" = "Empty"
        }
        response_parameters = {
          "method.response.header.Access-Control-Allow-Origin" = true
        }
      }
      integration_response = {
        status_code        = "200"
        content_handling   = null
        response_templates = null
        selection_pattern  = null
        response_parameters = {
          "method.response.header.Access-Control-Allow-Origin" = "'*'"
        }
      }
    }
  }

  assert {
    condition     = output.sha1 == run.baseline.sha1
    error_message = "Semantically absent null, empty map/list, and empty-string values must canonicalize identically."
  }
}

run "route_addition_changes_fingerprint" {
  command = plan

  variables {
    resources = {
      pets = {
        parent_key = "root"
        path_part  = "pets"
      }
      pet_id = {
        parent_key = "pets"
        path_part  = "{petId}"
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Adding an API path must change the fingerprint."
  }
}

run "http_method_changes_fingerprint" {
  command = plan

  variables {
    methods = {
      get_pets = {
        resource_key   = "pets"
        http_method    = "POST"
        authorization  = "COGNITO_USER_POOLS"
        authorizer_key = "cognito"
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Changing an HTTP method must change the fingerprint."
  }
}

run "authorization_changes_fingerprint" {
  command = plan

  variables {
    methods = {
      get_pets = {
        resource_key  = "pets"
        http_method   = "GET"
        authorization = "NONE"
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Changing authorization semantics must change the fingerprint."
  }
}

run "integration_target_changes_fingerprint" {
  command = plan

  variables {
    integrations = {
      get_pets = {
        method_key              = "get_pets"
        type                    = "AWS_PROXY"
        integration_http_method = "POST"
        uri                     = "arn:aws:apigateway:us-east-1:lambda:path/functions/changed/invocations"
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Changing an integration target must change the fingerprint."
  }
}

run "request_mapping_changes_fingerprint" {
  command = plan

  variables {
    integrations = {
      get_pets = {
        method_key              = "get_pets"
        type                    = "AWS_PROXY"
        integration_http_method = "POST"
        uri                     = "arn:aws:apigateway:us-east-1:lambda:path/functions/test/invocations"
        request_parameters = {
          "integration.request.header.X-Tenant" = "method.request.header.X-Tenant"
        }
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Changing a request mapping must change the fingerprint."
  }
}

run "cors_response_changes_fingerprint" {
  command = plan

  variables {
    cors = {
      resource_keys = ["pets"]
      method        = {}
      integration = {
        request_templates = {
          "application/json" = "{\"statusCode\": 200}"
        }
      }
      method_response = {
        status_code = "200"
        response_models = {
          "application/json" = "Empty"
        }
        response_parameters = {
          "method.response.header.Access-Control-Allow-Origin" = true
        }
      }
      integration_response = {
        status_code = "200"
        response_parameters = {
          "method.response.header.Access-Control-Allow-Origin" = "'https://example.test'"
        }
      }
    }
  }

  assert {
    condition     = output.sha1 != run.baseline.sha1
    error_message = "Changing CORS response behavior must change the fingerprint."
  }
}
