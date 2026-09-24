# Documentation Overlay Source

src/content/docs and zfb.config.ts are curated English source pages for a future documentation-site migration. The site framework, installed packages, and public asset tree are not part of this import.

The MDX pages link to image, review, and preview assets by their expected public URL. Their source files are retained once under artwork-resources/pcb-art/resources. During a separate site migration, materialize the reviewed images and generated preview HTML into that site's public/assets/pcb-art directory. Do not commit duplicate preview HTML or a second copy of the original resource images into this source bundle.

This task did not initialize, configure, or build the repository documentation site.
