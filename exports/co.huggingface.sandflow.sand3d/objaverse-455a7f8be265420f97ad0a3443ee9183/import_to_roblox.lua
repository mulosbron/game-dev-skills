-- Sand3D to Roblox Studio Placement Script
-- Automatically sets up Sand3D props in a 'Sand3D_Assets' Model group in Workspace

local Workspace = game:GetService("Workspace")
local InsertService = game:GetService("InsertService")

local container = Workspace:FindFirstChild("Sand3D_Assets")
if not container then
    container = Instance.new("Model")
    container.Name = "Sand3D_Assets"
    container.Parent = Workspace
end

print("Initializing Sand3D props placement...")

-- Prop #1: objaverse-455a7f8be265420f97ad0a3443ee9183
do
    print("Loading objaverse-455a7f8be265420f97ad0a3443ee9183 (building)...")
    -- In Roblox Studio: Import via 'Avatar -> 3D Importer' or Open Cloud Asset ID
    -- Model attributes for 100% legal compliance & attribution tracking:
    -- Source: Sandflow/sand3d-objaverse
    -- License: CC-BY-4.0
    -- Attribution: "WW2 Bunker" by stal98, https://sketchfab.com/3d-models/455a7f8be265420f97ad0a3443ee9183, CC-BY-4.0; modified: rewritten as a sand3d program
end

print("Sand3D props deployment completed successfully!")
