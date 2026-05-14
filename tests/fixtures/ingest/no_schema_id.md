# Документ без схемы

This document deliberately lacks the "Target Schema ID:" header and should trigger an E_NO_SCHEMA_ID error during processing.

The pipeline should detect this and skip the file gracefully in batch mode.
