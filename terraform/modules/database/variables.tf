variable "pgbouncer_subnet_id" {
  type = "string"
}

variable "lb_subnet_ids" {
  type = "list"
}

variable "vpc_id" {
  type = "string"
}

variable "deployment_stage" {
  type = "string"
}

variable "db_username" {
  type = "string"
}

variable "db_password" {
  type = "string"
}

variable "db_instance_count" {
  type = "string"
  default = 2
}

variable "preferred_maintenance_window" {
  type = "string"
}

// AWS RDS Cluster instance

variable "aws_rds_cluster_instance_class" {
  type = "string"
}

variable "aws_rds_cluster_instance_engine_version" {
  type = "string"
}

variable "aws_rds_db_cluster_parameter_group_name" {
  type = "string"
}

variable "default_tags" {
  type = "map"
}