-- DogBrain: a small companion AI so every animation shows up in play: follows the nearest player (walks when
-- close, runs to catch up, stands idle beside you and hops now and then), wanders around its spawn when nobody is
-- near, and jumps over low obstacles in its way. Replace it with your own AI any time: DogController only looks at
-- the Humanoid's speed and jump state. Set the model attribute DogAI = false to switch this off.

local Players = game:GetService("Players")

local model = script.Parent
local humanoid = model:WaitForChild("Humanoid") :: Humanoid
local root = model:WaitForChild("HumanoidRootPart") :: BasePart

-- 1 = the size the clips were made for (HumanoidRootPart 0.62 m long at 4.5 studs/m)
local scale = root.Size.Z / (0.62 * 4.5)
local WALK_SPEED = 5 * scale
local RUN_SPEED = 15 * scale
local NEAR = 6 * scale -- stop this far from the player
local FAR = 20 * scale -- run beyond this
local SIGHT = 120 -- notice players within this many studs
local WANDER_RADIUS = 30 * scale

pcall(function()
	root:SetNetworkOwner(nil) -- the server moves the dog; nobody's client gets authority over it
end)

local home = root.Position
local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Exclude

local function groundOffset()
	return humanoid.HipHeight + root.Size.Y / 2 -- root centre to the ground
end

local jumping = false
local function cueJump()
	if jumping or humanoid.FloorMaterial == Enum.Material.Air then
		return
	end
	jumping = true
	model:SetAttribute("JumpCue", (model:GetAttribute("JumpCue") or 0) + 1) -- clients play the crouch
	task.wait(0.22)
	humanoid.Jump = true
	task.delay(0.8, function()
		jumping = false
	end)
end

-- a low obstacle straight ahead that the jump can clear?
local function obstacleAhead()
	local filter = { model }
	for _, p in Players:GetPlayers() do
		if p.Character then
			table.insert(filter, p.Character)
		end
	end
	params.FilterDescendantsInstances = filter
	local fwd = root.CFrame.LookVector
	local feet = root.Position - Vector3.yAxis * (groundOffset() - 0.4 * scale)
	local hit = workspace:Raycast(feet, fwd * 3.5 * scale, params)
	if not hit or hit.Normal.Y > 0.6 then
		return false -- nothing, or just a slope
	end
	local maxUp = humanoid.JumpHeight * 0.9
	local top = workspace:Raycast(hit.Position + fwd * 0.5 + Vector3.yAxis * (maxUp + 0.4 * scale),
		-Vector3.yAxis * (maxUp + 0.4 * scale), params)
	return top ~= nil -- found a top below the jump height
end

local function nearestPlayer()
	local best, bestD = nil, SIGHT
	for _, p in Players:GetPlayers() do
		local c = p.Character
		local hrp = c and c:FindFirstChild("HumanoidRootPart")
		local h = c and c:FindFirstChildOfClass("Humanoid")
		if hrp and h and h.Health > 0 then
			local d = (hrp.Position - root.Position).Magnitude
			if d < bestD then
				best, bestD = hrp, d
			end
		end
	end
	return best, bestD
end

local nextHop = os.clock() + 8
local wanderGoal, wanderUntil = nil, 0

while model.Parent and humanoid.Health > 0 do
	if model:GetAttribute("DogAI") == false then
		task.wait(0.5)
		continue
	end
	local target, dist = nearestPlayer()
	if target then
		wanderGoal = nil
		if dist > NEAR then
			humanoid.WalkSpeed = dist > FAR and RUN_SPEED or WALK_SPEED
			local dir = (target.Position - root.Position) * Vector3.new(1, 0, 1)
			humanoid:MoveTo(target.Position - dir.Unit * NEAR * 0.7)
			if obstacleAhead() then
				task.spawn(cueJump)
			end
		else
			humanoid:Move(Vector3.zero) -- stand beside the player
			-- face them
			local look = (target.Position - root.Position) * Vector3.new(1, 0, 1)
			if look.Magnitude > 0.1 and root.CFrame.LookVector:Dot(look.Unit) < 0.8 then
				humanoid.WalkSpeed = WALK_SPEED
				humanoid:MoveTo(root.Position + look.Unit * 0.5)
			end
			if os.clock() > nextHop then
				nextHop = os.clock() + math.random(6, 12)
				task.spawn(cueJump) -- a happy hop
			end
		end
	else
		-- wander around home with idle pauses
		if not wanderGoal and os.clock() > wanderUntil then
			local a = math.random() * math.pi * 2
			local r = math.random() * WANDER_RADIUS
			wanderGoal = home + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r)
			humanoid.WalkSpeed = WALK_SPEED
		end
		if wanderGoal then
			humanoid:MoveTo(wanderGoal)
			if obstacleAhead() then
				task.spawn(cueJump)
			end
			if ((wanderGoal - root.Position) * Vector3.new(1, 0, 1)).Magnitude < 2 * scale then
				wanderGoal = nil
				wanderUntil = os.clock() + math.random(2, 6)
				humanoid:Move(Vector3.zero)
			end
		end
	end
	task.wait(0.15)
end
