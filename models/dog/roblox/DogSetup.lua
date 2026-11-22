-- DogSetup: turns the imported Dog mesh into a walking, animated NPC. Paste into Studio's command bar.
--
-- 1. File > Import 3D > models/dog/out/Dog.roblox.fbx (Scale Unit: Stud). Keep "Rig" options at their defaults.
--    You get a Model with a skinned MeshPart and the DogRig bones (DogRoot, Hips, Spine, ... Tail3) inside it.
-- 2. Drag models/dog/roblox/DogKit.rbxmx into Studio (it lands in Workspace).
-- 3. Select the imported Model, paste this whole file into the command bar (View > Command Bar), press Enter.
-- 4. Play: the dog follows you (walks, runs to catch up, idles beside you, hops), or wanders on its own.
--
-- What it does (safe to run again on the same model):
--  - puts the dog upright, facing its nose along the model's LookVector, and rescales it to 5.7 studs nose to tail tip
--    (4.5 studs per metre, the scale of the ClassicHouse) if the importer brought it in at another size
--  - adds an invisible HumanoidRootPart + Humanoid (R15 HipHeight, JumpHeight 3.2) and welds the mesh to it
--  - moves DogKit to ReplicatedStorage; puts DogController (client) and DogBrain (server) into the dog

local DOG_HIPS_TO_HEAD_M = 0.6783 -- Blender distance between the Hips and Head bone heads
local STUDS_PER_METRE = 4.5

local model = game.Selection:Get()[1]
if model and not model:IsA("Model") then
	model = model:FindFirstAncestorOfClass("Model")
end
assert(model and model:IsA("Model"), "Select the imported Dog model first")

local function bone(name)
	for _, d in model:GetDescendants() do
		if d:IsA("Bone") and d.Name == name then
			return d
		end
	end
	error(("[DogSetup] no bone named %s inside %s: is this the imported Dog.roblox.fbx?"):format(name, model:GetFullName()))
end

local rootBone, hipsBone, headBone = bone("DogRoot"), bone("Hips"), bone("Head")

-- 1. scale -------------------------------------------------------------------------------------------------
local target = DOG_HIPS_TO_HEAD_M * STUDS_PER_METRE
local actual = (headBone.WorldPosition - hipsBone.WorldPosition).Magnitude
if math.abs(actual / target - 1) > 0.02 then
	model:ScaleTo(model:GetScale() * target / actual)
	print(("[DogSetup] rescaled: Hips-Head was %.2f studs, now %.2f"):format(actual, target))
end
local k = STUDS_PER_METRE -- studs per Blender metre from here on

-- 2. upright, nose along the pivot's LookVector ----------------------------------------------------------------
local function frame()
	local pRoot, pHips, pHead = rootBone.WorldPosition, hipsBone.WorldPosition, headBone.WorldPosition
	local fwd0 = (pHead - pHips).Unit
	local up = (pHips - pRoot)
	up = (up - fwd0 * up:Dot(fwd0)).Unit -- DogRoot is on the ground under the body
	local fwd = (fwd0 - up * fwd0:Dot(up)).Unit
	return pRoot, up, fwd
end
local pRoot, up, fwd = frame()
if up.Y < 0.999 then
	local current = CFrame.fromMatrix(pRoot, fwd:Cross(up), up, -fwd)
	local flat = Vector3.new(fwd.X, 0, fwd.Z)
	flat = flat.Magnitude > 1e-3 and flat.Unit or Vector3.new(0, 0, -1)
	local wanted = CFrame.lookAt(pRoot, pRoot + flat)
	model:PivotTo(wanted * current:Inverse() * model:GetPivot())
	pRoot, up, fwd = frame()
	print("[DogSetup] stood the dog upright")
end

-- 3. HumanoidRootPart + Humanoid ----------------------------------------------------------------------------
for _, d in model:GetDescendants() do
	if d:IsA("WeldConstraint") and d.Name == "DogWeld" then
		d:Destroy() -- re-run: unweld first, or moving the root part below would drag the mesh along
	end
end
local hrp = model:FindFirstChild("HumanoidRootPart")
if not hrp then
	hrp = Instance.new("Part")
	hrp.Name = "HumanoidRootPart"
	hrp.Parent = model
end
-- the body box: 0.26 m wide, 0.30 m tall, 0.62 m long, centred 0.45 m up, 0.02 m behind DogRoot
hrp.Size = Vector3.new(0.26 * k, 0.30 * k, 0.62 * k)
local centre = pRoot + Vector3.yAxis * (0.45 * k) - fwd * (0.02 * k)
hrp.CFrame = CFrame.lookAt(centre, centre + fwd)
hrp.Transparency = 1
hrp.CanCollide = true
hrp.CanTouch = true
hrp.CanQuery = true
hrp.Anchored = false
hrp.Massless = false
hrp.CastShadow = false
hrp.TopSurface = Enum.SurfaceType.Smooth
hrp.BottomSurface = Enum.SurfaceType.Smooth

for _, p in model:GetDescendants() do
	if p:IsA("BasePart") and p ~= hrp then
		p.Anchored = false
		p.CanCollide = false
		p.CanTouch = false
		p.Massless = true
		pcall(function()
			(p :: any).CollisionFidelity = Enum.CollisionFidelity.Box
		end)
		local w = p:FindFirstChild("DogWeld")
		if not w then
			w = Instance.new("WeldConstraint")
			w.Name = "DogWeld"
			w.Parent = p
		end
		w.Part0 = hrp
		w.Part1 = p
		if p:IsA("MeshPart") and p.TextureID == "" and not p:FindFirstChildOfClass("SurfaceAppearance") then
			warn(("[DogSetup] %s has no texture: upload models/dog/textures/dog_palette.png and set its TextureID")
				:format(p:GetFullName()))
		end
	end
end
for _, d in model:GetDescendants() do
	if d:IsA("AnimationController") then
		d:Destroy() -- DogController drives the bones directly
	end
end

local hum = model:FindFirstChildOfClass("Humanoid") or Instance.new("Humanoid")
hum.RigType = Enum.HumanoidRigType.R15
hum.HipHeight = (0.45 - 0.15) * k -- ground to the bottom of the HumanoidRootPart
hum.UseJumpPower = false
hum.JumpHeight = 0.7 * k
hum.WalkSpeed = 5
hum.MaxSlopeAngle = 50
hum.AutoRotate = true
hum.BreakJointsOnDeath = false
hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
hum.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
hum.Parent = model

model.PrimaryPart = hrp
model.WorldPivot = CFrame.lookAt(pRoot, pRoot + fwd) -- on the ground between the paws: drop it anywhere
pcall(function()
	model.ModelStreamingMode = Enum.ModelStreamingMode.Atomic -- bones and mesh stream in together
end)
if model.Name == "Model" or model.Name == "Dog.roblox" then
	model.Name = "Dog"
end

-- 4. scripts --------------------------------------------------------------------------------------------------
local RS = game:GetService("ReplicatedStorage")
local kit = RS:FindFirstChild("DogKit")
for _, place in { workspace, game:GetService("ServerStorage"), game:GetService("StarterPack") } do
	local found = place:FindFirstChild("DogKit")
	if found then
		if kit and kit ~= found then
			kit:Destroy() -- a newer kit was dragged in: it replaces the old one
		end
		kit = found
	end
end
assert(kit, "[DogSetup] drag models/dog/roblox/DogKit.rbxmx into Studio first")
kit.Parent = RS
for _, name in { "DogController", "DogBrain" } do
	local old = model:FindFirstChild(name)
	if old then
		old:Destroy()
	end
	local s = kit:FindFirstChild(name):Clone()
	s.Parent = model
	s.Enabled = true
	s.RunContext = name == "DogController" and Enum.RunContext.Client or Enum.RunContext.Server
end
for _, s in kit:GetChildren() do
	if s:IsA("Script") then
		s.Enabled = false -- the kit's own copies never run (a Client script would run even in ReplicatedStorage)
	end
end

print(("[DogSetup] ready: %s, %.1f studs at the withers, HipHeight %.2f. Press Play."):format(model:GetFullName(),
	0.56 * k, hum.HipHeight))
