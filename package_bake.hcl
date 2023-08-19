variable "VERSION" {
  default = ""
}

variable "REGISTRY_IMAGE" {
  default = ""
}

// group "default" {
//   targets = ["package-armv7", "package-arm64"]
// }

target "default" {
  dockerfile = "Dockerfile"
  args = {
  }
  platforms = ["linux/arm/v7","linux/arm64"]
  tags = ["${REGISTRY_IMAGE}:${VERSION}"]
}

// target "package-armv7" {
//   inherits = ["default"]
//   platforms = ["linux/arm/v7"]
//   tags = ["${REGISTRY_IMAGE}:${VERSION}-armv7"]
// }

// target "package-arm64" {
//   inherits = ["default"]
//   platforms = ["linux/arm64"]
//   tags = ["${REGISTRY_IMAGE}:${VERSION}-arm64"]
// }