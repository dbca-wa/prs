# docker-bake.hcl — reproducible, multi-arch build config.
# Build (local single-platform): docker buildx bake
# Build + push (multi-arch):      docker buildx bake --push
# Override at runtime:            TAG=v2 REGISTRY=ghcr.io/me docker buildx bake
# Override a Dockerfile ARG:      docker buildx bake --set app.args.PYTHON_VERSION=3.13-debian13-dev

variable "IMAGE" {
  description = "Fully-qualified image name, without the tag."
  default     = "ghcr.io/dbca-wa/prs"
}

variable "TAG" {
  description = "Tag applied by the app/ci build targets."
  default     = "latest"
}

variable "LOCAL_TAG" {
  description = "Tag for a local development image."
  default     = "dev"
}

variable "PLATFORMS" {
  description = "Platforms used by the multi-arch targets."
  type        = list(string)
  default     = ["linux/amd64", "linux/arm64"]
}

variable "TYPESENSE_VERSION" {
  default = "30.2"
}

variable "CACHE_TAG" {
  description = "Tag holding the registry build cache (must differ from image tags)."
  default     = "buildcache"
}

# Default build only targets PRS, not Typesense.
group "default" {
  targets = ["app"]
}

group "all" {
  targets = ["app", "typesense"]
}

# What to build. Exporter, cache and attestation policy belong to the targets
# that consume this, so local builds don't inherit CI-only behaviour.
target "_base" {
  context    = "."
  dockerfile = "Dockerfile"
}

# Local development: native platform, loaded into Docker, tagged :dev (default).
# No `platforms`: BuildKit builds for the builder's host platform,
# so the image always matches the machine running the build.
target "local" {
  inherits = ["_base"]
  tags     = ["${IMAGE}:${LOCAL_TAG}"]
  output   = ["type=docker"]
}

# Multi-arch image for the registry (manual release build & push or CI).
# Push-only target.
target "app" {
  inherits   = ["_base"]
  tags       = ["${IMAGE}:${TAG}"]
  platforms  = PLATFORMS
  attest     = ["type=provenance,mode=max", "type=sbom"]
  cache-from = ["type=registry,ref=${IMAGE}:${CACHE_TAG}"]
  cache-to   = ["type=registry,ref=${IMAGE}:${CACHE_TAG},mode=max,ignore-error=true"]
}

target "typesense" {
  context    = "."
  dockerfile = "Dockerfile.typesense"
  tags       = [
    "ghcr.io/dbca-wa/typesense:${TAG}",
    "ghcr.io/dbca-wa/typesense:${TYPESENSE_VERSION}",
  ]
  platforms  = PLATFORMS
  attest     = ["type=provenance,mode=max", "type=sbom"]
  cache-from = ["type=registry,ref=ghcr.io/dbca-wa/typesense:${CACHE_TAG}"]
  cache-to   = ["type=registry,ref=ghcr.io/dbca-wa/typesense:${CACHE_TAG},mode=max,ignore-error=true"]
}

# CI-only: GitHub Actions cache, and always refresh base images so any
# scheduled rebuild picks up upstream security fixes.
# Note that CI overrides tags in multi-build.yml via set: ci.tags=...
target "ci" {
  inherits   = ["app"]
  cache-from = ["type=gha"]
  cache-to   = ["type=gha,mode=max"]
  pull       = true
}
