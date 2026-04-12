# astrbot src

This directory will hold import-safe front-end shell packages.

Planned package root:

- `jw_astrbot_shell`

Reason:

- the top-level `astrbot/` folder is an ownership folder
- it must not be used directly as the long-term Python package root because it
  conflicts with the external AstrBot runtime package
