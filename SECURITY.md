# Security policy

Please report security issues privately to the repository owner rather than
opening a public issue. Include the affected version, reproduction steps, and
the impact you observed.

Maya Python plugins execute with the current user's filesystem permissions.
Review downloaded plugin files before loading them, and install dependencies
only from their official sources.
