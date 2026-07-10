# ComfyUI workflows

Saved ComfyUI graph exports (`*.json`) submitted via [`core/comfy_client.py`](../core/comfy_client.py).

## LTX-Video (AI b-roll, Pillar 6 slot 1)

1. Run ComfyUI (`ComfyUI/` is cloned here) with the LTX-Video custom node
   (`ComfyUI/custom_nodes/ComfyUI-LTXVideo`).
2. Build one graph in the UI: **text prompt → LTXVideo node → video output**.
3. Export it here as `ltx_broll.json`.
4. Submit it with a per-beat prompt swapped in:

   ```python
   import json
   from core.comfy_client import generate
   wf = json.load(open("workflows/ltx_broll.json"))
   # set the positive-prompt node's text to your scene-beat prompt, then:
   result = generate(prompt="neon city street at night", workflow=wf)
   ```

`generate()` fails open (returns a non-ok `ProviderResult`) until a workflow is supplied
and ComfyUI is reachable at `COMFYUI_URL`, so the render always falls back to stock B-roll.

`*.json` here is gitignored (graphs can be large / machine-specific); this README and any
committed template stay.
