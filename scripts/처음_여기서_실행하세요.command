#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
xattr -cr "$DIR/인플루언서시딩기.app" 2>/dev/null
open "$DIR/인플루언서시딩기.app"
