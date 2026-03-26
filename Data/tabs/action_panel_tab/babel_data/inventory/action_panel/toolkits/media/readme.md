Setup
bash

# Save the script as texture_tool.py
chmod +x texture_tool.py

# Install dependencies
pip install Pillow numpy scikit-image scikit-learn opencv-python

# Or minimal install
pip install Pillow numpy

Usage Examples
bash

# Show comprehensive help
./texture_tool.py -h

# List available workflows
./texture_tool.py --workflows --list

# List with details
./texture_tool.py --workflows --list --details

# List stored images
./texture_tool.py --images --list

# List images in specific directory
./texture_tool.py --images --list --dir ./my_textures

# Profile an image
./texture_tool.py --image sprite_sheet.png --profile

# Cut image into 4x4 grid
./texture_tool.py --image collage.png --cut grid --rows 4 --cols 4

# Cut using contour detection
./texture_tool.py --image character.png --cut contour --threshold 150

# Cut using manual positions
./texture_tool.py --image sprites.png --cut manual --positions "[(0,0,32,32),(32,0,64,32)]"

# Classify texture type
./texture_tool.py --image material.png --classify

# Store image in collection
./texture_tool.py --image new_texture.png --store --category materials

# Remove image from storage
./texture_tool.py --remove /path/to/stored/image.png

# Run sprite extraction workflow
./texture_tool.py --workflow sprite_extraction --image spritesheet.png --run

# Run with custom parameters
./texture_tool.py --workflow grid_cutting --image atlas.png --run --params rows=8,cols=8

# View saved profiles for an image
./texture_tool.py --image textured.png --view-profile

Features

    Multiple Workflows: Pre-defined workflows for common tasks

    Texture Profiling: Color, edge, and texture analysis

    Smart Cutting: Grid, contour, color-based, and alpha-based cutting

    Storage System: Organized storage of images and profiles

    Classification: Automatic texture type classification

    CLI Interface: Full argparse-based command-line interface

    Batch Operations: Process multiple images

    Preview System: HTML preview generation (extensible)

The tool is completely self-contained and uses only open-source libraries available on Ubuntu/Xubuntu. It can be extended with additional strategies or integrated into shell scripts for pipeline processing.
