#!/bin/bash
set -eu
printf '%s\n' 'Bulk public access is disabled. Keep agents private; expose only the authenticated UI through reviewed ingress.' >&2
exit 1
