variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
  default     = "staging"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.40.0.0/16"
}

variable "backend_image" {
  description = "ECR image URI for backend, e.g. 123.dkr.ecr.us-east-1.amazonaws.com/a1fp-backend:latest"
  type        = string
}

variable "frontend_image" {
  description = "ECR image URI for frontend"
  type        = string
}

variable "backend_cpu"    { default = 1024 }
variable "backend_memory" { default = 2048 }
variable "backend_desired_count" { default = 2 }
variable "backend_max_count"     { default = 8 }

variable "frontend_cpu"    { default = 256 }
variable "frontend_memory" { default = 512 }
variable "frontend_desired_count" { default = 2 }

variable "domain_name"      { type = string, default = "" }
variable "acm_certificate_arn" { type = string, default = "" }

variable "mongo_uri_secret_arn" {
  description = "SecretsManager ARN holding MongoDB Atlas connection string"
  type        = string
}

variable "jwt_secret_arn" {
  description = "SecretsManager ARN holding JWT signing key"
  type        = string
}

variable "integration_fernet_key_arn" {
  description = "SecretsManager ARN for integration credential encryption key"
  type        = string
}
