# footprints/ - Shared KiCad Footprint Library

## File Organization

**Footprints (PCB physical pads):**
- **KiCad source files**: `/footprints/kicad/*.kicad_mod` (individual footprint files)
- **SVG exports**: `/footprints/images/*.svg` (intermediate)
- **Documentation SVGs**: `/doc/docs/_fragments/footprints/*.svg` (final destination)

## Exporting SVG Files for Documentation (Manual Workflow)

When footprints are added or updated, export SVGs manually for documentation:

**Quick workflow:**
```bash
# 1. Create .pretty directory if needed
cd footprints/kicad
mkdir -p zudo-blanks.pretty
cp *.kicad_mod zudo-blanks.pretty/

# 2. Export SVGs using KiCad CLI
kicad-cli fp export svg zudo-blanks.pretty -o ../images --black-and-white

# 3. Clean SVG files (remove REF** text)
python3 ../scripts/clean-svg-refs.py ../images/

# 4. Copy to documentation
cp ../images/*.svg ../../doc/docs/_fragments/footprints/
```
