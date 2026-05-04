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
    NOTIFICATIONS_ENABLED      = "false"
    NOTIFICATION_DRY_RUN       = "true"
    NOTIFICATION_EMAIL_FROM    = "notifications@toganddogs.usmissionhero.com"
    NOTIFICATION_ADMIN_EMAIL   = "mbn@usmissionhero.com"
    NOTIFICATION_ROUTE_MODE    = "event_based"
    # Individual notification flags can also be added here if needed to override defaults
  }
}
