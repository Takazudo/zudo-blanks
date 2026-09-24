# Fabrication Review Notes

This is a curated summary of the incoming geometry screening. The machine-readable source evidence remains in fabrication-review.json. The checks use Revision 5 geometry and do not run KiCad, generate release CAM, or establish factory acceptance.

The incoming review identifies 64 Kumiko apertures that do not admit the assumed 1.0 mm round router: 8 in standard Kumiko and 56 in wide Kumiko. Wide Kumiko also has a local material ligament about 0.1166 mm wide between two top-layer openings. The report and resources/manufacturing-review contain the layer IDs, coordinates, SVG/PNG marks, and issue table.

These are process-dependent observations, not an automatic instruction to enlarge or close any feature. Check the actual fabricator's tool and capability rules before choosing a local art change. Other narrow features and physical strength also require process and prototype review.

The source report explicitly separates planar connectivity and offset checks from minimum cut width, mechanical strength, actual router paths, native KiCad checks, and factory review. None of those can be concluded from the geometric checks alone.
