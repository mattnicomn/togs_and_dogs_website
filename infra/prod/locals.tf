locals {
  # Mandatry tagging standard
  common_tags = {
    Environment  = var.environment
    ManagedBy    = "terraform"
    Repo         = "togs_and_dogs_website"
    Client       = "TogAndDogs"
    Application  = "PetScheduling"
    CostCenter   = "ClientBillable"
    BillingModel = "Direct"
  }

  # Helper for resource naming
  name_prefix = "${var.project_name}-${var.environment}"
}
