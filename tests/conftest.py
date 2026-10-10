# -*- coding: utf-8 -*-
"""pytest configuration for UTF-8 support on Windows."""

import sys
import codecs

# Force UTF-8 encoding for stdout/stderr
if sys.stdout.encoding != 'utf-8':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Set default encoding
if hasattr(sys, 'setdefaultencoding'):
    sys.setdefaultencoding('utf-8')