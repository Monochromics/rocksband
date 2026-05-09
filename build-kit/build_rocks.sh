#!/bin/bash
set -e

echo "Orchestrating builds across all subdirectories..."

# Iterate through every subdirectory
for dir in */ ; do
    # Skip if it's not a valid directory
    [ -d "$dir" ] || continue
    
    # Strip the trailing slash
    dir_name="${dir%/}"
    
    # Look for an mp3 file inside the directory
    mp3_file=$(ls "$dir_name"/*.mp3 2>/dev/null | head -n 1)
    
    if [ -n "$mp3_file" ]; then
        # Get just the filename (e.g. snare-1.mp3) instead of the path
        file_basename=$(basename "$mp3_file")
        rock_name="${dir_name}-rock"
        
        echo "================================================="
        echo "Processing directory: $dir_name"
        
        # Generate the rockcraft.yaml from the template in the root folder, and place it in the subdirectory
        sed "s/{{ROCK_NAME}}/$rock_name/g; s/{{FILE_NAME}}/$file_basename/g" rockcraft.yaml.template > "$dir_name/rockcraft.yaml"
        
        echo "✔ Generated $dir_name/rockcraft.yaml"
        
        if [ "$1" == "--pack" ]; then
            echo "Packing $rock_name..."
            (cd "$dir_name" && rockcraft pack)
            
            # Find the generated rock file
            rock_file=$(ls "$dir_name"/*.rock | head -n 1)
            
            echo "Importing into Podman..."
            rockcraft.skopeo --insecure-policy copy "oci-archive:$rock_file" "containers-storage:localhost/$dir_name:1.0"
            echo "✔ Successfully loaded localhost/$dir_name:1.0"
        fi
    fi
done

echo ""
echo "Done!"
if [ "$1" != "--pack" ]; then
    echo "Run './build_rocks.sh --pack' to automatically pack and import all rocks."
fi
