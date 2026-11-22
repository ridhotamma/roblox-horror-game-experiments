--!strict
-- RoofToggle: hides / shows ClassicHouse roofs for the local player only (put in StarterPlayerScripts).
--
-- Modes, cycled with R (keyboard), Y (gamepad) or the on-screen button on touch devices:
--   Auto   - a house's roof hides while you stand inside it (default)
--   Hidden - all house roofs hidden (top-down / cutaway view)
--   Shown  - roofs always visible
-- A house is any model tagged "ClassicHouse" (HouseSetup.lua adds the tag and the InteriorZone part).
-- Its roof is every BasePart whose name starts with "RoofGroup" (roof, gables, chimney, ceiling, ceiling lights).
-- Hidden roof parts also stop blocking the camera (CanQuery off locally) so the camera can look down inside.

local CollectionService = game:GetService("CollectionService")
local ContextActionService = game:GetService("ContextActionService")
local Players = game:GetService("Players")

local MODES = { "Auto", "Hidden", "Shown" }
local CHECK_INTERVAL = 0.15

type House = { model: Model, zone: BasePart?, roof: { BasePart }, canQuery: { [BasePart]: boolean }, hidden: boolean }

local player = Players.LocalPlayer
local modeIndex = 1
local houses: { [Model]: House } = {}

local function collectRoof(model: Model): { BasePart }
	local roof = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and string.sub(d.Name, 1, 9) == "RoofGroup" then
			table.insert(roof, d)
		end
	end
	return roof
end

local function setHidden(h: House, hidden: boolean)
	if h.hidden == hidden then return end
	h.hidden = hidden
	for _, p in h.roof do
		p.LocalTransparencyModifier = if hidden then 1 else 0
		if hidden then
			h.canQuery[p] = p.CanQuery
			p.CanQuery = false
		else
			p.CanQuery = if h.canQuery[p] == nil then true else h.canQuery[p]
		end
	end
end

local function addHouse(inst: Instance)
	if not inst:IsA("Model") or houses[inst] then return end
	local zone = inst:FindFirstChild("InteriorZone", true)
	houses[inst] = {
		model = inst,
		zone = if zone and zone:IsA("BasePart") then zone else nil,
		roof = collectRoof(inst),
		canQuery = {},
		hidden = false,
	}
end

local function removeHouse(inst: Instance)
	local h = houses[inst :: Model]
	if h then
		setHidden(h, false)
		houses[inst :: Model] = nil
	end
end

local function inside(zone: BasePart?, pos: Vector3): boolean
	if not zone then return false end
	local p = zone.CFrame:PointToObjectSpace(pos)
	local half = zone.Size / 2
	return math.abs(p.X) <= half.X and math.abs(p.Z) <= half.Z and p.Y >= -half.Y - 1 and p.Y <= half.Y
end

local function update()
	local mode = MODES[modeIndex]
	local character = player.Character
	local rootPart = character and character:FindFirstChild("HumanoidRootPart")
	local pos = if rootPart and rootPart:IsA("BasePart") then rootPart.Position else nil
	for _, h in houses do
		local hide = mode == "Hidden" or (mode == "Auto" and pos ~= nil and inside(h.zone, pos))
		setHidden(h, hide)
	end
end

local function onAction(_: string, state: Enum.UserInputState): Enum.ContextActionResult
	if state == Enum.UserInputState.Begin then
		modeIndex = modeIndex % #MODES + 1
		ContextActionService:SetTitle("ToggleRoof", "Roof: " .. MODES[modeIndex])
		update()
	end
	return Enum.ContextActionResult.Sink
end

for _, inst in CollectionService:GetTagged("ClassicHouse") do
	addHouse(inst)
end
CollectionService:GetInstanceAddedSignal("ClassicHouse"):Connect(addHouse)
CollectionService:GetInstanceRemovedSignal("ClassicHouse"):Connect(removeHouse)

ContextActionService:BindAction("ToggleRoof", onAction, true, Enum.KeyCode.R, Enum.KeyCode.ButtonY)
ContextActionService:SetTitle("ToggleRoof", "Roof: " .. MODES[modeIndex])
ContextActionService:SetPosition("ToggleRoof", UDim2.new(1, -150, 0, 20))

while true do
	update()
	task.wait(CHECK_INTERVAL)
end
