--!strict
-- HouseDoors: hinged, openable doors for the imported ClassicHouse model.
--
-- Setup: import out/ClassicHouse.roblox.glb, run out/ClassicHouse.roblox.lua once (collision + LOD),
-- then put this Script inside the imported ClassicHouse model.
--
-- Each door is the MeshParts whose names start with its prefix ("FrontDoor", "FrontDoorPanel",
-- "FrontDoorStatic1" ...). They are anchored and rotated together about the hinge with TweenService.
--
-- Attributes on the main door part (FrontDoor / BackDoor), editable in Studio or from other scripts:
--   Open       (bool)   true = open. Set it from a script to open/close the door (e.g. a scare slam).
--   Locked     (bool)   the prompt only rattles the door.
--   OpenAngle  (number) degrees; both doors swing inward (front +90, back -90).
--   HingeSide  (number) -1 or 1: which local X edge is the hinge. Flip it if a door swings on the wrong edge.
-- Optional Sounds inside the main door part: "Creak" (plays on open), "Slam" (on close), "Rattle" (locked).

local TweenService = game:GetService("TweenService")

type DoorConfig = { prefix: string, width: number, hingeZ: number, openAngle: number, label: string }

-- Sizes in model metres (classic_house.json); the script measures the import scale from the door width.
local DOORS: { DoorConfig } = {
	{ prefix = "FrontDoor", width = 0.93, hingeZ = -0.025, openAngle = 90, label = "Front door" },
	{ prefix = "BackDoor", width = 0.89, hingeZ = 0.025, openAngle = -90, label = "Back door" },
}
local OPEN_INFO = TweenInfo.new(1.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local CLOSE_INFO = TweenInfo.new(0.45, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
local RATTLE_INFO = TweenInfo.new(0.06, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, 3, true)

local house = script.Parent :: Instance
assert(house, "put HouseDoors inside the imported ClassicHouse model")

local function playSound(main: BasePart, name: string)
	local s = main:FindFirstChild(name)
	if s and s:IsA("Sound") then
		s:Play()
	end
end

local function setupDoor(cfg: DoorConfig)
	local main = house:FindFirstChild(cfg.prefix, true)
	if not (main and main:IsA("BasePart")) then
		warn(`[HouseDoors] no part named {cfg.prefix} under {house:GetFullName()}`)
		return
	end

	-- Every piece of this door (slab, panels, knobs) moves with the main part.
	local pieces: { BasePart } = {}
	for _, d in house:GetDescendants() do
		if d:IsA("BasePart") and string.sub(d.Name, 1, #cfg.prefix) == cfg.prefix then
			d.Anchored = true
			table.insert(pieces, d)
		end
	end

	if main:GetAttribute("OpenAngle") == nil then main:SetAttribute("OpenAngle", cfg.openAngle) end
	if main:GetAttribute("HingeSide") == nil then main:SetAttribute("HingeSide", -1) end
	if main:GetAttribute("Locked") == nil then main:SetAttribute("Locked", false) end
	main:SetAttribute("Open", false)

	local closedCFrame = main.CFrame
	local hinge: CFrame
	local offsets: { [BasePart]: CFrame } = {}
	local function computeHinge()
		local side = main:GetAttribute("HingeSide") :: number
		local scale = main.Size.X / cfg.width
		-- hinge line: the jamb-side edge of the slab, on its inside face
		hinge = closedCFrame * CFrame.new(side * main.Size.X / 2, 0, -side * cfg.hingeZ * scale)
		for _, p in pieces do
			offsets[p] = hinge:ToObjectSpace(p.CFrame)
		end
	end
	computeHinge()

	local angle = Instance.new("NumberValue")
	angle.Name = "DoorAngle"
	angle.Parent = main
	angle.Changed:Connect(function(a: number)
		local h = hinge * CFrame.Angles(0, math.rad(a), 0)
		for p, off in offsets do
			p.CFrame = h * off
		end
	end)

	local prompt = Instance.new("ProximityPrompt")
	prompt.ObjectText = cfg.label
	prompt.ActionText = "Open"
	prompt.MaxActivationDistance = 8
	prompt.RequiresLineOfSight = false
	prompt.Parent = main

	local isOpen = false
	local tween: Tween? = nil

	local function setOpen(open: boolean)
		if open == isOpen then return end
		isOpen = open
		main:SetAttribute("Open", open)
		prompt.ActionText = if open then "Close" else "Open"
		if tween then tween:Cancel() end
		local target = if open then main:GetAttribute("OpenAngle") :: number else 0
		local t = TweenService:Create(angle, if open then OPEN_INFO else CLOSE_INFO, { Value = target })
		tween = t
		if open then
			playSound(main, "Creak")
		else
			t.Completed:Connect(function(state)
				if state == Enum.PlaybackState.Completed then playSound(main, "Slam") end
			end)
		end
		t:Play()
	end

	prompt.Triggered:Connect(function()
		if main:GetAttribute("Locked") and not isOpen then
			playSound(main, "Rattle")
			local dir = math.sign(main:GetAttribute("OpenAngle") :: number)
			TweenService:Create(angle, RATTLE_INFO, { Value = 1.5 * dir }):Play()
			return
		end
		setOpen(not isOpen)
	end)

	-- Other scripts drive the door by setting the attribute: door:SetAttribute("Open", false) slams it.
	main:GetAttributeChangedSignal("Open"):Connect(function()
		setOpen(main:GetAttribute("Open") == true)
	end)
	main:GetAttributeChangedSignal("Locked"):Connect(function()
		prompt.ActionText = if main:GetAttribute("Locked") and not isOpen then "Locked" else (if isOpen then "Close" else "Open")
	end)
	-- Flipping HingeSide in Studio while the door is closed re-measures the hinge.
	main:GetAttributeChangedSignal("HingeSide"):Connect(function()
		if not isOpen and angle.Value == 0 then computeHinge() end
	end)
end

for _, cfg in DOORS do
	setupDoor(cfg)
end
