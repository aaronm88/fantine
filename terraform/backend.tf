terraform {
  backend "s3" {
    endpoint                    = "https://fantine-bucket.nyc3.digitaloceanspaces.com"
    bucket                      = "fantine-bucket"
    key                         = "terraform/fantine/dev/state.tfstate"
    region                      = "us-east-1"
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style            = true
    access_key                  = "DO801PDT7VMHU4TUK8QY"
    secret_key                  = "GlXR28EAyw1HhW0rbqTPO2rSzDxSzMbRpcf65PePNU8"
  }
}
