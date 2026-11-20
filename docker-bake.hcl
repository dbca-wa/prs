# docker-bake.hcl — reproducible, multi-arch build config.
# Build (local single-platform): docker buildx bake
# Build + push (multi-arch):      docker buildx bake --push
# Override at runtime:            IMAGE=ghcr.io/me TAG=v2 docker buildx bake
# Override a Dockerfile ARG:      docker buildx bake --set app.args.PYTHON_VERSION=3.13-debian13-dev

variable "IMAGE" {
  description = "Fully-qualified image name, without the tag. Overridden by the IMAGE environment variable (multi-build.yml sets it from github.repository, so forks push to their own namespace)."
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

variable "TYPESENSE_IMAGE" {
  description = "Fully-qualified Typesense image name, without the tag."
  default     = "ghcr.io/dbca-wa/typesense"
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
# `cache-to` publishes BuildKit's layer cache as a manifest tagged
# `${CACHE_TAG}` in the same repository. It is not a runnable image.
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
    "${TYPESENSE_IMAGE}:${TAG}",
    "${TYPESENSE_IMAGE}:${TYPESENSE_VERSION}",
  ]
  platforms  = PLATFORMS
  attest     = ["type=provenance,mode=max", "type=sbom"]
  cache-from = ["type=registry,ref=${TYPESENSE_IMAGE}:${CACHE_TAG}"]
  cache-to   = ["type=registry,ref=${TYPESENSE_IMAGE}:${CACHE_TAG},mode=max,ignore-error=true"]
}

# CI-only: reuses the GHCR registry cache (`${CACHE_TAG}`, shared with release
# builds) rather than the GitHub Actions cache, so a `mode=max` cache export is
# not limited by the ~10 GB repo-wide Actions cache budget.
# Requires the builder to be logged in to the registry (multi-build.yml does
# this before the bake step) with push access to the package.
# Also always refreshes base images so any scheduled rebuild picks up upstream
# security fixes.
# Note that CI sets the image tags in multi-build.yml via set: ci.tags=...
# The `tags` attribute is inherited from `app`, and buildx bake APPENDS `+=`
# assignments to inherited list values, so CI must also override `IMAGE`
# (via env) or the inherited upstream tag would be pushed as well.
target "ci" {
  inherits = ["app"]
  pull     = true
}
