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
}
