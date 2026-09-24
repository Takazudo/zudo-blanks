# Export Artwork Review Notes

This is a curated summary of the incoming exported-art screening. The machine-readable evidence remains in export-art-review.json. The checks measure generated copper and mask polygons; they are not KiCad DRC or CAM approval.

The Revision 5 export candidate uses a 0.35 mm mask-opening clearance and a 0.30 mm copper clearance from edges and drilled features, with 0.05 mm of copper under the mask. This adaptation can remove visible gold from the approved preview. The largest reported reductions include roughly 25% on full-gold Spider layers and 19.3% on the Woven Maze top.

The screening also reports very narrow gaps between separate copper and mask polygons, including examples below 0.01 mm. The affected pairs and coordinates are recorded in the JSON evidence and resources/manufacturing-review/artwork-gap-review.csv. Review each shape and the actual process before changing artwork.

These metrics do not establish quoted price reductions or fabricator capability. The selected export rules and current drawings still require local KiCad, CAM-viewer, and fabricator review.
