#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

black ./custom_components/
