import bpy
import os
from datetime import datetime
import tempfile

class GDTBuilder:
    def __init__(self, existing_content=None):
        self.images = []
        self.materials = []
        self.models = []
        if existing_content:
            self.parse_existing_content(existing_content)
    
    def parse_existing_content(self, content):
        lines = content.splitlines()
        i = 0
        total_lines = len(lines)
        
        while i < total_lines:
            line = lines[i].strip()
            i += 1
            
            if not line or line == "{" or line == "}":
                continue
                
            if '"i_' in line and 'image.gdf' in line:
                name = line.split('"i_')[1].split('"')[0]
                current_data = {'name': name}
                
                while i < total_lines and "}" not in lines[i].strip():
                    inner_line = lines[i].strip()
                    i += 1
                    
                    if '"baseImage"' in inner_line:
                        current_data['path'] = inner_line.split('"')[3]
                
                i += 1
                self.images.append(current_data)
                
            elif line.startswith('"') and 'material.gdf' in line:
                name = line.split('"')[1]
                current_data = {'name': name}
                
                while i < total_lines and "}" not in lines[i].strip():
                    inner_line = lines[i].strip()
                    i += 1
                    
                    if '"colorMap"' in inner_line:
                        current_data['image'] = inner_line.split('"')[3].replace('i_', '')
                
                i += 1
                self.materials.append(current_data)
                
            elif line.startswith('"') and 'xmodel.gdf' in line:
                name = line.split('"')[1]
                current_data = {'name': name}
                
                while i < total_lines and "}" not in lines[i].strip():
                    inner_line = lines[i].strip()
                    i += 1
                    
                    if '"filename"' in inner_line:
                        current_data['path'] = inner_line.split('"')[3]
                    elif '"skinOverride"' in inner_line:
                        current_data['material'] = inner_line.split('"')[3]
                
                i += 1
                self.models.append(current_data)
    
    def add_image(self, name, rel_path):
        self.images.append({
            'name': name,
            'path': rel_path
        })
        
    def add_material(self, name, image_name):
        self.materials.append({
            'name': name,
            'image': image_name
        })
        
    def add_model(self, name, rel_path, material_name):
        rel_path = rel_path.replace('/', '\\\\').replace('\\', '\\\\')
        
        original_name = name
        counter = 1
        while any(model['name'] == name for model in self.models):
            name = f"{original_name}_{counter}"
            counter += 1
            
        self.models.append({
            'name': name,
            'path': rel_path,
            'material': material_name
        })
        
    def build_gdt_content(self):
        gdt_content = "{\n"
        
        for img in self.images:
            gdt_content += f'''    "i_{img['name']}" ( "image.gdf" )
    {{
        "baseImage" "{img['path']}"
        "colorMap" "1"
        "colorSRGB" "1"
        "compressionMethod" "compressed high color"
        "semantic" "diffuseMap"
        "type" "image"
    }}\n\n'''

        for mat in self.materials:
            gdt_content += f'''    "{mat['name']}" ( "material.gdf" )
    {{
        "colorMap" "i_{mat['image']}"
        "materialType" "lit"
        "template" "material.template"
    }}\n\n'''

        for model in self.models:
            gdt_content += f'''    "{model['name']}" ( "xmodel.gdf" )
    {{
        "filename" "{model['path']}"
        "type" "rigid"
        "skinOverride" "{model['material']}\\r\\n"
    }}\n\n'''

        gdt_content += "}"
        return gdt_content

def generate_unique_name(mesh_name, base_name):
    timestamp = datetime.now().strftime("%H%M%S")
    clean_mesh = "".join(c for c in mesh_name if c.isalnum() or c == '_')
    clean_base = "".join(c for c in base_name if c.isalnum() or c == '_')
    clean_name = f"{clean_mesh}_{clean_base}"
    clean_name = clean_name.replace('.', '_')
    return f"{clean_name}_{timestamp}"

def clean_material_names(obj):
    used_names = set()
    mesh_name = obj.name
    for mat_slot in obj.material_slots:
        if mat_slot.material:
            base_name = mat_slot.material.name
            unique_name = generate_unique_name(mesh_name, base_name)
            while unique_name in used_names:
                unique_name = generate_unique_name(mesh_name, base_name)
            used_names.add(unique_name)
            mat_slot.material.name = unique_name[:60]

def export_model_with_textures(obj):
    selected_meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
    if not selected_meshes:
        print("No mesh objects selected!")
        return
        
    bpy.ops.object.select_all(action='INVERT')
    bpy.ops.object.delete()
    
    for o in selected_meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = selected_meshes[0]
    
    if len(selected_meshes) > 1:
        bpy.ops.object.join()
    
    obj = bpy.context.active_object
    
    blend_file_path = bpy.data.filepath
    if blend_file_path:
        blend_parent = os.path.dirname(os.path.dirname(blend_file_path))
        base_folder = os.path.dirname(blend_file_path)
        blend_root_name = os.path.basename(base_folder)
    else:
        base_folder = os.path.join(os.path.expanduser("~"), "Desktop")
        blend_parent = base_folder
        blend_root_name = "desktop"
    
    export_name = obj.name.replace('.', '_')
    export_folder = os.path.join(base_folder, f"{export_name}_export")
    
    try:
        os.makedirs(export_folder, exist_ok=True)
    except Exception as e:
        print(f"Failed to create export folder: {e}")
        return

    source_data_path = os.path.join(blend_parent, "source_data")
    try:
        os.makedirs(source_data_path, exist_ok=True)
    except Exception as e:
        print(f"Failed to create source_data folder: {e}")
        return

    clean_material_names(obj)

    gdt_path = os.path.join(source_data_path, "indiana_jones.gdt")
    
    existing_content = None
    if os.path.exists(gdt_path):
        try:
            with open(gdt_path, 'r') as src_file:
                existing_content = src_file.read()
        except Exception as e:
            print(f"Warning: Could not read existing GDT file: {e}")
    
    gdt_builder = GDTBuilder(existing_content)
    
    if existing_content:
        print(f"Loaded from existing GDT: {len(gdt_builder.images)} images, {len(gdt_builder.materials)} materials, {len(gdt_builder.models)} models")
    
    processed_images = set()
    has_valid_materials = False

    for mat_slot in obj.material_slots:
        if not mat_slot.material:
            continue
            
        mat = mat_slot.material
        if not mat.use_nodes:
            continue
            
        has_valid_materials = True
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                img = node.image
                if img.name not in processed_images:
                    img_path = bpy.path.abspath(img.filepath)
                    if os.path.exists(img_path):
                        new_name = f"{mat.name}_diffuse.png"
                        new_path = os.path.join(export_folder, new_name)
                        img.save_render(new_path)
                        
                        rel_image_path = os.path.join(
                            blend_root_name,
                            os.path.basename(export_folder),
                            new_name
                        )
                        
                        gdt_builder.add_image(mat.name, rel_image_path)
                        gdt_builder.add_material(mat.name, mat.name)
                        processed_images.add(img.name)
    
    if not has_valid_materials:
        default_mat_name = f"{export_name}_default"
        img = bpy.data.images.new(name=f"{default_mat_name}_tex", width=64, height=64)
        img.pixels = [0.0, 0.0, 0.0, 1.0] * (64 * 64)
        new_name = f"{default_mat_name}.png"
        img_path = os.path.join(export_folder, new_name)
        img.filepath_raw = img_path
        img.file_format = 'PNG'
        img.save()
        
        rel_image_path = os.path.join(
            blend_root_name,
            os.path.basename(export_folder),
            new_name
        )
        
        gdt_builder.add_image(default_mat_name, rel_image_path)
        gdt_builder.add_material(default_mat_name, default_mat_name)
        main_mat = default_mat_name
    else:
        main_mat = obj.material_slots[0].material.name if obj.material_slots[0].material else "default"

    model_path = os.path.join(export_folder, f"{export_name}.xmodel_bin")
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    
    bpy.ops.export_scene.xmodel(
        filepath=model_path,
        check_existing=True,
        target_format='XMODEL_BIN',
        version='7',
        use_selection=True,
        global_scale=0.39
    )

    rel_path = os.path.relpath(model_path, source_data_path).replace('/', '\\')
    gdt_builder.add_model(export_name, rel_path, main_mat)

    unique_images = {img['name']: img for img in gdt_builder.images}
    unique_materials = {mat['name']: mat for mat in gdt_builder.materials}
    
    unique_models = {}
    for model in gdt_builder.models:
        if model['name'] not in unique_models:
            unique_models[model['name']] = model
    
    gdt_builder.images = list(unique_images.values())
    gdt_builder.materials = list(unique_materials.values())
    gdt_builder.models = list(unique_models.values())
    
    print(f"Writing to GDT: {len(gdt_builder.images)} images, {len(gdt_builder.materials)} materials, {len(gdt_builder.models)} models")
    
    with open(gdt_path, 'w') as f:
        f.write(gdt_builder.build_gdt_content())

    if existing_content:
        print(f"Export completed to: {export_folder}")
        print(f"Model appended to existing GDT file: {gdt_path}")
    else:
        print(f"Export completed to: {export_folder}")
        print(f"New GDT file created: {gdt_path}")

if __name__ == "__main__":
    obj = None
    if bpy.context.selected_objects:
        obj = bpy.context.active_object
        export_model_with_textures(obj)
    else:
        print("Please select at least one mesh object!")
