-- DogController: animates this Dog on the local client from its Humanoid (speed and jump state).
-- A Script with RunContext = Client inside the Dog model (DogSetup puts it there). Bone.Transform is not replicated,
-- so every client runs its own copy; the server only moves the Humanoid (DogBrain, or your own AI).
--
-- Model attribute "JumpCue": bump it (any new value) ~0.2 s before setting Humanoid.Jump to get the crouch
-- anticipation; jumps without a cue start at the push-off.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local CULL_DISTANCE = 250 -- studs from the camera; farther dogs keep their last pose

local model = script.Parent
local kit = ReplicatedStorage:WaitForChild("DogKit")
local DogAnimator = require(kit:WaitForChild("DogAnimator"))
local DogAnimations = require(kit:WaitForChild("DogAnimations"))

local humanoid = model:WaitForChild("Humanoid") :: Humanoid
local root = model:WaitForChild("HumanoidRootPart") :: BasePart
-- the skeleton streams in with its MeshPart (DogSetup makes the model Atomic); wait for the last bone we need
local function hasBones()
	local n = 0
	for _, d in model:GetDescendants() do
		if d:IsA("Bone") then
			n += 1
		end
	end
	return n >= #DogAnimations.order
end
while not hasBones() do
	model.DescendantAdded:Wait()
end

local anim = DogAnimator.new(model, DogAnimations)

local State = Enum.HumanoidStateType
humanoid.StateChanged:Connect(function(_old, new)
	if new == State.Jumping then
		anim:Jump()
	elseif new == State.Freefall then
		anim:Fall() -- only acts when walking off a ledge; a jump is already in the air poses
	elseif new == State.Landed or new == State.Running or new == State.RunningNoPhysics then
		anim:Land()
	end
end)

model:GetAttributeChangedSignal("JumpCue"):Connect(function()
	anim:Crouch()
end)

local conn
conn = RunService.RenderStepped:Connect(function(dt)
	if not model.Parent or not root.Parent then
		conn:Disconnect()
		return
	end
	local cam = workspace.CurrentCamera
	if cam and (cam.CFrame.Position - root.Position).Magnitude > CULL_DISTANCE then
		return
	end
	local v = root.AssemblyLinearVelocity
	anim:SetLocomotion(Vector3.new(v.X, 0, v.Z).Magnitude)
	anim:Step(math.min(dt, 0.1))
end)

model.Destroying:Connect(function()
	conn:Disconnect()
end)
