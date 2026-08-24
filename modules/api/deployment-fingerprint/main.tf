variable "resources" {
  description = "API resource path semantics keyed by stable configuration identity."
  type = map(object({
    parent_key = string
    path_part  = string
  }))
  default = {}
}

variable "authorizers" {
  description = "API authorizer semantics without provider-generated identifiers."
  type = map(object({
    type                = string
    identity_source     = optional(string, "")
    provider_references = optional(set(string), [])
    result_ttl_seconds  = optional(number, 300)
  }))
  default = {}
}

variable "methods" {
  description = "API method semantics keyed by stable configuration identity."
  type = map(object({
    resource_key          = string
    http_method           = string
    authorization         = string
    authorizer_key        = optional(string, "")
    api_key_required      = optional(bool, false)
    authorization_scopes  = optional(set(string), [])
    operation_name        = optional(string, "")
    request_models        = optional(map(string), {})
    request_parameters    = optional(map(bool), {})
    request_validator_key = optional(string, "")
  }))
  default = {}
}

variable "integrations" {
  description = "API integration semantics keyed by stable configuration identity."
  type = map(object({
    method_key                     = string
    type                           = string
    integration_http_method        = optional(string, "")
    uri                            = optional(string, "")
    connection_type                = optional(string, "INTERNET")
    connection_reference           = optional(string, "")
    credentials_reference          = optional(string, "")
    request_parameters             = optional(map(string), {})
    request_templates              = optional(map(string), {})
    passthrough_behavior           = optional(string, "WHEN_NO_MATCH")
    cache_key_parameters           = optional(set(string), [])
    cache_namespace                = optional(string, "")
    content_handling               = optional(string, "")
    timeout_milliseconds           = optional(number, 29000)
    tls_insecure_skip_verification = optional(bool, false)
  }))
  default = {}
}

variable "method_responses" {
  description = "API method-response semantics keyed by stable configuration identity."
  type = map(object({
    method_key          = string
    status_code         = string
    response_models     = optional(map(string), {})
    response_parameters = optional(map(bool), {})
  }))
  default = {}
}

variable "integration_responses" {
  description = "API integration-response semantics keyed by stable configuration identity."
  type = map(object({
    method_key          = string
    status_code         = string
    content_handling    = optional(string, "")
    response_parameters = optional(map(string), {})
    response_templates  = optional(map(string), {})
    selection_pattern   = optional(string, "")
  }))
  default = {}
}

variable "cors" {
  description = "Shared MOCK OPTIONS and response behavior for CORS-enabled resources."
  type = object({
    resource_keys = optional(set(string), [])
    method = object({
      http_method          = optional(string, "OPTIONS")
      authorization        = optional(string, "NONE")
      authorizer_key       = optional(string, "")
      api_key_required     = optional(bool, false)
      authorization_scopes = optional(set(string), [])
      operation_name       = optional(string, "")
      request_models       = optional(map(string), {})
      request_parameters   = optional(map(bool), {})
    })
    integration = object({
      type                           = optional(string, "MOCK")
      integration_http_method        = optional(string, "")
      uri                            = optional(string, "")
      request_parameters             = optional(map(string), {})
      request_templates              = optional(map(string), {})
      passthrough_behavior           = optional(string, "WHEN_NO_MATCH")
      cache_key_parameters           = optional(set(string), [])
      cache_namespace                = optional(string, "")
      content_handling               = optional(string, "")
      timeout_milliseconds           = optional(number, 29000)
      tls_insecure_skip_verification = optional(bool, false)
    })
    method_response = object({
      status_code         = string
      response_models     = optional(map(string), {})
      response_parameters = optional(map(bool), {})
    })
    integration_response = object({
      status_code         = string
      content_handling    = optional(string, "")
      response_parameters = optional(map(string), {})
      response_templates  = optional(map(string), {})
      selection_pattern   = optional(string, "")
    })
  })
  default = {
    method               = {}
    integration          = {}
    method_response      = { status_code = "200" }
    integration_response = { status_code = "200" }
  }
}

variable "gateway_responses" {
  description = "Gateway-generated response semantics keyed by stable configuration identity."
  type = map(object({
    response_type       = string
    status_code         = optional(string, "")
    response_parameters = optional(map(string), {})
    response_templates  = optional(map(string), {})
  }))
  default = {}
}

locals {
  canonical = {
    resources = { for key in sort(keys(var.resources)) : key => var.resources[key] }
    authorizers = {
      for key in sort(keys(var.authorizers)) : key => merge(var.authorizers[key], {
        provider_references = sort(tolist(var.authorizers[key].provider_references))
      })
    }
    methods = {
      for key in sort(keys(var.methods)) : key => merge(var.methods[key], {
        authorization_scopes = sort(tolist(var.methods[key].authorization_scopes))
      })
    }
    integrations = {
      for key in sort(keys(var.integrations)) : key => merge(var.integrations[key], {
        cache_key_parameters = sort(tolist(var.integrations[key].cache_key_parameters))
      })
    }
    method_responses      = { for key in sort(keys(var.method_responses)) : key => var.method_responses[key] }
    integration_responses = { for key in sort(keys(var.integration_responses)) : key => var.integration_responses[key] }
    cors = {
      resource_keys = sort(tolist(var.cors.resource_keys))
      method = merge(var.cors.method, {
        authorization_scopes = sort(tolist(var.cors.method.authorization_scopes))
      })
      integration = merge(var.cors.integration, {
        cache_key_parameters = sort(tolist(var.cors.integration.cache_key_parameters))
      })
      method_response      = var.cors.method_response
      integration_response = var.cors.integration_response
    }
    gateway_responses = { for key in sort(keys(var.gateway_responses)) : key => var.gateway_responses[key] }
  }
}

output "canonical_json" {
  description = "Canonical JSON used as the sole deployment-fingerprint input."
  value       = jsonencode(local.canonical)
}

output "sha1" {
  description = "Deterministic semantic API deployment fingerprint."
  value       = sha1(jsonencode(local.canonical))
}
