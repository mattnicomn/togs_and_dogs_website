locals {
  # Mandatry tagging standard
  common_tags = {
    Company      = "USMissionHero"
    Project      = "TogsAndDogs"
    Environment  = var.environment
    ManagedBy    = "terraform"
    Repo         = "togs_and_dogs_website"
    Client       = "TogAndDogs"
    Application  = "PetScheduling"
    CostCenter   = "ClientBillable"
    BillingModel = "PassThrough"
  }

  # Helper for resource naming
  name_prefix = "${var.project_name}-${var.environment}"

  # Phase 3A: Notification Configuration
  notification_env_vars = {
    NOTIFICATIONS_ENABLED                = "true"
    NOTIFICATION_DRY_RUN                 = "false"
    NOTIFICATION_EMAIL_FROM              = "support@usmissionhero.com"
    NOTIFICATION_EMAIL_FROM_NAME         = "Tog & Dogs Support"
    NOTIFICATION_ADMIN_EMAIL             = "mbn@usmissionhero.com"
    NOTIFICATION_ROUTE_MODE              = "event_based"
    NOTIFICATION_PORTAL_URL              = "https://toganddogs.usmissionhero.com"
    NOTIFICATION_TEST_RECIPIENT_OVERRIDE = "" # Live traffic
    NOTIFY_ADMIN_ON_REQUEST_RECEIVED     = "true"
    NOTIFY_CLIENT_ON_APPROVAL            = "true"
    NOTIFY_CLIENT_ON_SCHEDULED           = "true"
    NOTIFY_STAFF_ON_ASSIGNMENT           = "true"
    NOTIFY_CLIENT_ON_CANCELLED           = "true"
    NOTIFY_STAFF_ON_CANCELLED            = "true"
    NOTIFY_ADMIN_ON_FAILED_DELIVERY      = "true"
    NOTIFICATION_MODE                    = "external_provider"
    NOTIFICATION_PROVIDER                = "postmark"
    POSTMARK_SERVER_TOKEN_SECRET_NAME    = module.secrets.postmark_token_arn
    POSTMARK_MESSAGE_STREAM              = "outbound"
    NOTIFICATION_REPLY_TO                = "support@usmissionhero.com"
    SES_SANDBOX_ALLOWED_RECIPIENTS       = "mbn@usmissionhero.com"
    # Release 6H: Configurable protected admin accounts
    PROTECTED_ADMIN_EMAILS = "admin@toganddogs.com,mbn@usmissionhero.com,support@usmissionhero.com"
    PROTECTED_ADMIN_SUBS   = "74b86488-1011-7029-bb6d-dad984e1463c"

    # Release 7C: Push notification controls disabled until mobile app readiness
    PUSH_ENABLED  = "false"
    PUSH_DRY_RUN  = "true"
    PUSH_PROVIDER = "expo"
  }
}
