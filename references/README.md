# Local reference pack

Place your own consistent, reviewed images here. No reference artwork is supplied or scraped.

- `naruto/front.png`, `naruto/three-quarter.png`; optionally `side.png`, `action.png`.
- `omniman/front.png`, `omniman/three-quarter.png`; optionally `side.png`, `action.png`.
- `style/style-01.png`: the desired stylized 3D comic/anime look.
- `arena/rooftop.png`: the same intact moonlit rooftop for every shot.

JPEG and WebP are also accepted. Each image must be at least 256 × 256. Use at most four images per character, and at most four style/arena images combined. Use the same costume/version across every character view.

Run `wws golden-references outputs/golden_sequence --directory references`, inspect the three boards in the output's `references/packed/` folder, then run `wws golden-references outputs/golden_sequence --approve`. The pipeline hashes originals and boards; changed references require a new golden project to retain prior approvals and paid provenance.

See `docs/golden-sequence.md` for the full workflow. Do not place credentials in this directory.
