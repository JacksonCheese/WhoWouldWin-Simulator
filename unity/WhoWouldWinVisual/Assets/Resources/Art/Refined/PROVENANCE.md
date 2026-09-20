# Refined hybrid presentation assets

Created for this project with the built-in image_gen tool in September 2026, then imported/sliced in Unity. No downloaded character sprites, internet asset packs or voice recordings were used.

- ninja-atlas.png: textured original ninja proxy; 11 imported body/expression parts.
- titan-atlas.png: textured original flying-hero proxy; 12 imported body/expression parts.
- skyline-atlas.png: painted city background and textured rooftop foreground.

Full generation prompts: docs/art-generation-prompts.json at the repository root. Original source PNGs and alpha are retained unchanged. Unity texture metadata contains slice regions; RefinedArtInstaller.cs can rebuild those slices. These are generated development proxies, not canonical licensed Naruto/Omni-Man production sprite packs. The earlier procedural vector proxies remain available as a fallback.
