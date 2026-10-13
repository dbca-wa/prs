# docker-bake.hcl — reproducible, multi-arch build config.
# Build (local single-platform): docker buildx bake
# Build + push (multi-arch):      docker buildx bake --push
# Override at runtime:            TAG=v2 REGISTRY=ghcr.io/me docker buildx bake
# Override a Dockerfile ARG:      docker buildx bake --set app.args.PYTHON_VERSION=3.13-debian13-dev

variable "TAG" {
  default = "latest"
}

variable "TYPESENSE_VERSION" {
  default = "30.2"
}

variable "REGISTRY" {
  default = "ghcr.io/dbca-wa"
}

variable "PLATFORMS" {
  default = "linux/amd64,linux/arm64"
}

group "default" {
  targets = ["app"]
}
group "all" {
  targets = ["app", "typesense"]
}

target "app" {
  context    = "."
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/prs:${TAG}"]
  platforms  = split(",", PLATFORMS)
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
  attest     = ["type=provenance,mode=max", "type=sbom"]
}

target "typesense" {
  context    = "."
  dockerfile = "Dockerfile.typesense"
  tags       = [
    "${REGISTRY}/typesense:${TAG}",
    "${REGISTRY}/typesense:${TYPESENSE_VERSION}",
  ]
  platforms  = split(",", PLATFORMS)
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
  attest     = ["type=provenance,mode=max", "type=sbom"]
}
