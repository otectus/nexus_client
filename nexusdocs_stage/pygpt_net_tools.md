# Section: tools

Path: src/pygpt_net/tools

## Bugs / Risks
- Media player screenshot capture is TODO (tools/media_player/tool.py), leaving advertised functionality incomplete.
- Option command widget support is TODO (ui/widget/option/cmd.py) and impacts tool configuration UX.

## Optimizations
- Run tool operations (file IO, web requests, index scans) in background threads by default.
- Cache tool capability metadata to avoid repeated UI rebuilds.

## Enhancements
- Add consistent tool permission prompts for filesystem, network, and subprocess usage.
- Provide tool lifecycle hooks (init/cleanup) to reduce resource leaks.

## Additional Functions
- Add a tool registry exporter to list installed tools and their dependencies.
