# Section: data

Path: src/pygpt_net/data

## Bugs / Risks
- Large bundled JS/CSS assets are treated as internal sources; verify third-party license compliance and update cadence for highlight.js assets.

## Optimizations
- Reduce resource module size by trimming unused icons/fonts and regenerating QRCs with only active assets.
- Prefer minified assets and lazy-load optional UI themes to reduce startup cost.

## Enhancements
- Add an asset manifest with hashes to detect stale or mismatched packaged resources.
- Separate vendor assets from first-party assets for clearer maintenance and updates.

## Additional Functions
- Add a resource validation command that checks for missing QRC entries and mismatched file references.
